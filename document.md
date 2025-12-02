# MCT Configuration Behaviour – `ignore_data` and `read_after_timestamp`

## Overview

This page describes the behaviour of the new **Multi-Cloud Targeting (MCT)** configuration that has been introduced to both the **bronze pipeline** and the **DLT framework**.

The configuration drives two key behaviours:

* An internal boolean parameter **`ignore_data`**, which controls whether data is ingested when a pipeline runs.
* An optional per-pipeline **`read_after_timestamp`**, which controls the lower bound for ingestion across file-based and Delta-based pipelines.

At a high level:

* A global **MCT JSON config** defines **primary** and **standby** clouds and an optional **global** `ignore_data_override`.
* The **DLT framework** also reads pipeline-level controls from a **Unity Catalog Delta table**.
* An internal `ignore_data` flag is computed using a clear precedence order.
* When `ignore_data = true`, the framework prevents any records from being ingested while still creating or updating DLT tables.
* `read_after_timestamp` allows operators to centrally advance ingestion boundaries without changing pipeline code.
* Underlying data for standby environments is typically synchronised via the **data_replication framework (deep clone)**.

---

## Configuration Structure

The MCT configuration is composed of **two layers**:

1. **Global MCT configuration (JSON)** – shared by the bronze pipeline and the DLT framework.
2. **Per-pipeline controls (Unity Catalog Delta table)** – used by the DLT framework for pipeline-level overrides.

### 1. Global MCT configuration (JSON)

The primary MCT configuration is stored in a JSON object (for example, `mct_config.json`) and contains the cloud-role information and an optional global override:

* **`primary_cloud`**: The cloud considered the primary execution environment (for example, `"AWS"`, `"Azure"`).
* **`standby_cloud`**: The cloud considered the standby/secondary environment.
* **`ignore_data_override`** (optional, global): A top-level boolean flag that explicitly controls whether data should be ignored across the framework when no pipeline-level override is provided.

This JSON is used by both the **bronze pipeline** and the **DLT framework** to derive the internal `ignore_data` flag when a pipeline-level override is not present.

### 2. Per-pipeline controls (Unity Catalog Delta table – DLT only)

For the DLT framework, pipeline-specific controls are stored in a Unity Catalog Delta table:

* **Table:** `operations.orchestration_lakehouse.mct_config`
* **Key:** `pipeline_id` (one row per pipeline).
* **Columns per pipeline:**

  * **`ignore_data`** – optional boolean flag that acts as a *pipeline-level* override for `ignore_data`.
  * **`read_after_timestamp`** – optional ingestion boundary used to control where the pipeline starts reading data from.

These per-pipeline values integrate into the precedence rules for `ignore_data` and also drive the effective `read_after_timestamp` used by the DLT framework.

---

## Internal Parameter: `ignore_data`

An internal boolean parameter called **`ignore_data`** is introduced within the framework. This parameter is not directly exposed as user configuration, but is computed from the MCT configuration as follows:

* **Default:** `ignore_data = false`.
* When set to **`true`**, the framework:

  * Applies a **filter in front of the source views** to prevent any data from being ingested.
  * Ensures that when the pipeline runs, **no records are read from the sources**.
  * Still allows **DLT tables to be created or updated** (for example, new tables, schema changes) with **zero rows**.

This design supports scenarios where **table structure and metadata** must be deployed or updated in a standby cloud, while **data is synchronised separately** using the **data_replication framework (deep clone)**.

---

## Precedence Rules for `ignore_data`

The value of the internal `ignore_data` parameter is determined by a clear **precedence order**.

For any pipeline:

1. **Pipeline-level override** – highest precedence

   * **Bronze pipeline:** pipeline-level `ignore_data_override` from the pipeline’s own configuration (if defined).
   * **DLT framework:** `ignore_data` from `operations.orchestration_lakehouse.mct_config` for the corresponding `pipeline_id` (if populated).
2. **Global `ignore_data_override`** from the MCT JSON – second precedence.
3. **Cloud-role based logic** (derived cloud vs `standby_cloud`) – fallback.
4. **Default:** `ignore_data = false`.

More explicitly:

1. If a **pipeline-level override** exists (either in pipeline config or the UC table), its value (`true` or `false`) is used directly for `ignore_data`. No further checks are made.
2. If no pipeline-level override exists, but a **global `ignore_data_override`** is defined in the MCT JSON, its value is used.
3. If neither override is defined, the framework determines the **derived cloud** (the cloud where the framework is currently running) and compares it with `standby_cloud`:

   * If **derived cloud == standby_cloud** → `ignore_data = true`.
   * Otherwise → `ignore_data = false`.

In short, precedence is:

1. Pipeline-level override (if present).
2. Global override (if present).
3. Cloud-role logic (derived cloud vs standby cloud).
4. Default `false`.

---

## Pipeline-Level Controls from Unity Catalog (DLT Framework)

In the DLT framework, pipeline-level controls for `ignore_data` and `read_after_timestamp` are derived from the Unity Catalog Delta table `operations.orchestration_lakehouse.mct_config`.

* **Table:** `operations.orchestration_lakehouse.mct_config`.
* **Key:** `pipeline_id` (one row per pipeline).
* **Columns per pipeline:**

  * `ignore_data` – optional boolean flag that provides a pipeline-level override for the internal `ignore_data` parameter.
  * `read_after_timestamp` – optional timestamp boundary that controls where ingestion should start from.

### `read_after_timestamp` format and behaviour

* The `read_after_timestamp` value **must** be provided in the exact format used in the table, for example:

  ```text
  2026-01-01 00:00:00.000001 UTC+00
  ```

  Pattern:

  ```text
  YYYY-MM-DD HH:MM:SS.ffffff UTC+HH
  ```

* At runtime, the framework resolves an **effective** `read_after_timestamp` for each pipeline as follows:

  * If a value is present in `operations.orchestration_lakehouse.mct_config` for the corresponding `pipeline_id`, it is first validated for format.
  * If there is already a `read_after_timestamp` defined in the data flow spec (for example via `cloudFiles.modifiedAfter` or `startingTimestamp`), the framework compares the two values.

    * If the value in the Unity Catalog table is **newer (later)** than the existing value in the data flow spec, it **replaces** the spec value and becomes the new effective boundary.
    * If it is **older**, the existing spec value is retained.
  * If there is **no value** in the spec, the table value is used as-is.

* The resulting effective `read_after_timestamp` is applied **consistently to both file-based and Delta-based pipelines**, ensuring a single control point for advancing the ingestion boundary.

This design allows operators to centrally manage per-pipeline ingestion cut-over points via a single Unity Catalog table, without modifying the underlying DLT pipeline code or data flow specifications.

---

## Behaviour When `ignore_data = true`

When the resolved `ignore_data` value is **true**:

* A filter (for example, `WHERE 1=0` or an equivalent `WHERE false` predicate) is placed in front of all **source views** in the pipeline.
* The pipeline runs normally from a **control and orchestration** perspective:

  * DLT tables are created if they do not exist.
  * Schema and metadata changes are applied.
  * Pipeline dependencies and transformations are still validated.
* However, **no records are ingested** into the target tables.
* The **data_replication framework (deep clone)** is responsible for synchronising the underlying data into those tables.

This is especially useful for:

* **Standby environments** (for example, DR or cross-cloud failover setups) where table definitions need to be in sync, but data is replicated via deep clone.
* **Cutover scenarios**, where you want to create/refresh target tables and schemas first, then populate data later.

---

## Behaviour When `ignore_data = false`

When the resolved `ignore_data` value is **false**:

* No additional filter is applied to the source views.
* The pipeline executes **normal ingestion** behaviour:

  * Source data is read as usual.
  * Transformations and business logic run end to end.
  * Target tables are updated with ingested records.

This is the default and typical behaviour in the **primary cloud** (and any environment where overrides are not forcing ignore behaviour).

---

## Example Scenarios

### 1. Standby cloud with no overrides

**Inputs**

* `derived_cloud = "Azure"`.
* `standby_cloud = "Azure"` in the global MCT JSON.
* No pipeline-level or global `ignore_data_override` specified.

**Result**

* `ignore_data = true` (because the framework is running in the standby cloud).

**Behaviour**

* DLT tables are created/updated with zero rows.
* Data is populated via the data_replication framework (deep clone).

---

### 2. Primary cloud with no overrides

**Inputs**

* `derived_cloud = "AWS"`.
* `primary_cloud = "AWS"`, `standby_cloud = "Azure"`.
* No pipeline-level or global `ignore_data_override`.

**Result**

* `ignore_data = false` (because the framework is not running in the standby cloud).

**Behaviour**

* Normal ingestion: data flows from sources into bronze and downstream tables.

---

### 3. Global override forces ignore

**Inputs**

* Global `ignore_data_override = true` in the MCT JSON.
* No pipeline-level override.
* Any cloud (primary or standby).

**Result**

* `ignore_data = true` (global override takes precedence over cloud role).

**Behaviour**

* No data ingestion; all DLT tables are created/updated empty.

---

### 4. Pipeline-level override forces ingestion

**Inputs**

* For a given `pipeline_id`, `ignore_data = false` in `operations.orchestration_lakehouse.mct_config`.
* Global `ignore_data_override = true` in the MCT JSON.
* `derived_cloud = standby_cloud`.

**Result**

* `ignore_data = false` (pipeline-level override is highest precedence).

**Behaviour**

* That pipeline ingests data as normal, even though globally and by cloud role it would otherwise ignore data.

---

### 5. File-based pipeline – `read_after_timestamp` overrides `cloudFiles.modifiedAfter`

**Inputs**

* Pipeline is file-based (for example, Auto Loader with `cloudFiles`).

* Reader options in the data flow spec include:

  ```text
  cloudFiles.modifiedAfter = 2025-01-01T00:00:00Z
  ```

* Unity Catalog table `operations.orchestration_lakehouse.mct_config` has, for this `pipeline_id`:

  * `ignore_data = false`.
  * `read_after_timestamp = 2025-02-01 00:00:00.000001 UTC+00`.

**Resolution**

* The framework converts and compares the two timestamps.
* `2025-02-01 00:00:00.000001 UTC+00` is **newer** than `2025-01-01T00:00:00Z`.
* Therefore, the UC value **replaces** the spec value and becomes the effective ingestion boundary.

**Effective behaviour**

* The pipeline runs with an updated reader option equivalent to:

  ```text
  cloudFiles.modifiedAfter = 2025-02-01T00:00:00.000001Z
  ```

* Only files with modification time strictly after `2025-02-01 00:00:00.000001 UTC+00` are considered for ingestion.

* The original `cloudFiles.modifiedAfter` value in the spec is effectively ignored.

---

### 6. Delta pipeline – `read_after_timestamp` does not override newer `startingTimestamp`

**Inputs**

* Pipeline is Delta-based.

* Reader options in the data flow spec include:

  ```text
  startingTimestamp = 2025-03-01T00:00:00Z
  ```

* Unity Catalog table `operations.orchestration_lakehouse.mct_config` has, for this `pipeline_id`:

  * `ignore_data = false`.
  * `read_after_timestamp = 2025-02-01 00:00:00.000001 UTC+00`.

**Resolution**

* The framework converts and compares the two timestamps.
* `2025-02-01 00:00:00.000001 UTC+00` is **older** than `2025-03-01T00:00:00Z`.
* Because the existing `startingTimestamp` in the spec is **newer**, it is retained as the effective boundary.

**Effective behaviour**

* The pipeline continues to use:

  ```text
  startingTimestamp = 2025-03-01T00:00:00Z
  ```

* Only Delta changes after `2025-03-01T00:00:00Z` are ingested.

* The `read_after_timestamp` value from the UC table is ignored in this case.

---

### 7. Pipeline with no timestamp in spec – UC table provides the boundary

**Inputs**

* Pipeline (file-based or Delta-based) has **no** `cloudFiles.modifiedAfter` / `startingTimestamp` in the data flow spec.
* Unity Catalog table `operations.orchestration_lakehouse.mct_config` has, for this `pipeline_id`:

  * `ignore_data = false`.
  * `read_after_timestamp = 2026-01-01 00:00:00.000001 UTC+00`.

**Resolution**

* There is no existing boundary in the spec to compare.
* The UC value is taken **as-is** as the effective ingestion boundary.

**Effective behaviour**

* For file-based pipelines, the framework injects:

  ```text
  cloudFiles.modifiedAfter = 2026-01-01T00:00:00.000001Z
  ```

* For Delta-based pipelines, the framework injects:

  ```text
  startingTimestamp = 2026-01-01T00:00:00.000001Z
  ```

* In both cases, ingestion only starts from data strictly after `2026-01-01 00:00:00.000001 UTC+00`.

---

## Operational Notes

* The `ignore_data` behaviour is **evaluated at pipeline start** based on the current MCT configuration (JSON + UC table) and the cloud where the framework is running.
* Changes to the MCT JSON or the UC table (for example, toggling overrides or updating `read_after_timestamp`) take effect on **subsequent pipeline runs**.
* For cutover patterns:

  * Set `ignore_data` (via the appropriate override) to **true** in the standby environment while deep-clone replication is establishing the data.
  * During planned cutover, switch the relevant override(s) to **false** to start ingesting live data through the pipelines.
  * Optionally use `read_after_timestamp` to advance ingestion boundaries in a controlled way.

---

## Summary

The new MCT configuration introduces a flexible, cloud-aware mechanism to control whether pipelines ingest data or only deploy table structures:

* **`ignore_data`** is the core internal flag controlling ingestion behaviour.
* **Pipeline-level** and **global** overrides provide explicit control when needed.
* **Cloud-role logic** (primary vs standby) ensures sensible defaults when overrides are not set.
* The Unity Catalog table `operations.orchestration_lakehouse.mct_config` allows centralised per-pipeline control of both `ignore_data` and `read_after_timestamp`.
* This design supports robust **multi-cloud**, **DR**, and **cutover** scenarios while keeping framework behaviour predictable and easy to reason about.
