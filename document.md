# MCT Configuration Behaviour – `ignore_data` Logic

## Overview

This page describes the behaviour of the new **MCT configuration** that has been introduced to both the **bronze pipeline** and the **DLT framework**. The configuration controls an internal parameter called `ignore_data`, which determines whether data is ingested when the pipeline runs.

At a high level:

* A new **`mct_config`**** JSON** defines **primary** and **standby** clouds and optional overrides.
* An internal boolean parameter **`ignore_data`** is derived from this configuration.
* When `ignore_data = true`, the framework prevents any records from being ingested while still creating or updating DLT tables.
* This enables **schema and object deployment** to proceed, while the actual data is synchronised separately via the **data_replication framework (deep clone)**.

---

## Configuration Structure

The MCT configuration is composed of **two layers**:

1. **Global MCT configuration (JSON)** – shared by the bronze pipeline and the DLT framework
2. **Per-pipeline controls (Unity Catalog Delta table)** – used by the DLT framework for pipeline-level overrides

### 1. Global MCT configuration (JSON)

The primary MCT configuration is stored in a JSON object (for example, `mct_config.json`) and contains the **cloud role** information and an optional **global override**:

* **`primary_cloud`**: The cloud considered the primary execution environment (e.g. `"AWS"`, `"Azure"`).
* **`standby_cloud`**: The cloud considered the standby/secondary environment.
* **`ignore_data_override` (optional, global)**: A top-level boolean flag that explicitly controls whether data should be ignored across the framework when no pipeline-level override is provided.

This JSON is used by both **bronze_pipeline** and **DLT framework** to derive the internal `ignore_data` flag when a pipeline-level override is not present.

### 2. Per-pipeline controls (Unity Catalog Delta table)

For the DLT framework, pipeline-specific controls are stored in a Unity Catalog Delta table:

* **Table:** `operations.orchestration_lakehouse.mct_config`
* **Key:** `pipeline_id` (one row per pipeline)
* **Columns per pipeline:**

  * `ignore_data` – optional boolean flag that acts as a *pipeline-level* override for `ignore_data`.
  * `read_after_timestamp` – optional ingestion boundary used to control where the pipeline starts reading data from.

These per-pipeline values integrate into the precedence rules for `ignore_data` and also drive the effective `read_after_timestamp` used by the DLT framework.

---

## Internal Parameter: ignore_data

An internal boolean parameter called ignore_data is introduced wit not directly exposed as user configuration, but is computed from the `mct_config` as follows:

* **Default:** `ignore_data = false`.
* When set to **true**, the framework:

  * Applies a **filter in front of the source views** to prevent any data from being ingested.
  * Ensures that when the pipeline runs, **no records are read from the sources**.
  * Still allows **DLT tables to be created or updated** (e.g. new tables, schema changes) with **zero rows**.

This design supports scenarios where **table structure and metadata** must be deployed or updated in a standby cloud, while **data is synchronised separately** using the **data_replication framework (deep clone)**.

---

## Precedence Rules for `ignore_data`

The value of the internal `ignore_data` parameter is determined by a clear **precedence order**:

1. **Pipeline-level ************************`ignore_data_override`************************ (highest precedence)**

   * If the **optional pipeline-level** `ignore_data_override` is present (either `true` or `false`), its value is used **directly**.
   * In this case, the framework **does not** consult global overrides or cloud role (primary/standby).

2. **Global ************************`ignore_data_override`************************ (second precedence)**

   * If no pipeline-level override is specified, the framework checks the **global** `ignore_data_override` value in the `mct_config` JSON (if present).
   * If it is specified (either `true` or `false`), its value is assigned to `ignore_data`.

3. **Derived cloud vs. standby cloud (fallback logic)**

   * If neither pipeline-level nor global `ignore_data_override` is specified, the framework falls back to cloud-role-based logic.
   * The framework determines the **derived cloud** (the cloud where the framework is currently running), for example by inspecting the workspace host.
   * It then compares this derived cloud with the **`standby_cloud`** defined in `mct_config`:

     * If **derived cloud == standby cloud** → `ignore_data = true`.
     * Otherwise → `ignore_data = false`.

In summary, the precedence order is:

1. **Pipeline-level override** (if present)
2. **Global override** (if present)
3. **Cloud role logic** (derived cloud vs standby cloud)
4. **Default:** `ignore_data = false`.

---

## Behaviour When `ignore_data = true`

When the resolved `ignore_data` value is **true**:

* A filter (e.g. `WHERE 1=0` or equivalent) is placed in front of all **source views** in the pipeline.
* The pipeline runs normally from a **control and orchestration** perspective:

  * DLT tables are created if they do not exist.
  * Schema and metadata changes are applied.
  * Pipeline dependencies and transformations are still validated.
* However, **no records are ingested** into the target tables.
* The **data_replication framework (deep clone)** is responsible for synchronising the underlying data into those tables.

This is especially useful for:

* **Standby environments** (e.g. DR or cross-cloud failover setups) where table definitions need to be in sync, but data is replicated via deep clone.
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

### 1. Standby Cloud with No Overrides

* `derived_cloud = "Azure"`
* `standby_cloud = "Azure"` in `mct_config`
* No pipeline-level or global `ignore_data_override` specified

**Result:**
`ignore_data = true` (because the framework is running in the standby cloud)

**Behaviour:**
DLT tables are created/updated with zero rows, and data is populated via deep clone.

---

### 2. Primary Cloud with No Overrides

* `derived_cloud = "AWS"`
* `primary_cloud = "AWS"`, `standby_cloud = "Azure"`
* No pipeline-level or global `ignore_data_override`

**Result:**
`ignore_data = false` (because the framework is not running in the standby cloud)

**Behaviour:**
Normal ingestion: data flows from sources into bronze and downstream tables.

---

### 3. Global Override Forces Ignore

* Global `ignore_data_override = true` in `mct_config`
* No pipeline-level override
* Any cloud (primary or standby)

**Result:**
`ignore_data = true` (global override takes precedence over cloud role)

**Behaviour:**
No data ingestion; all DLT tables are created/updated empty.

---

### 4. Pipeline-Level Override Forces Ingestion

* Pipeline-level `ignore_data_override = false` for `bronze_pipeline`
* Global `ignore_data_override = true`
* `derived_cloud = standby_cloud`

**Result:**
`ignore_data = false` (pipeline-level override is highest precedence)

**Behaviour:**
`bronze_pipeline` ingests data as normal, even though globally and by cloud role it would otherwise ignore data.

---

## Pipeline-Level Controls from Unity Catalog (DLT Framework)

In the DLT framework, pipeline-level controls for `ignore_data` and `read_after_timestamp` are also derived from a **Unity Catalog Delta table**.

* **Table location:** `operations.orchestration_lakehouse.mct_config`
* **Key:** `pipeline_id` (one row per pipeline)
* **Columns per pipeline:**

  * `ignore_data` – optional boolean flag that provides a *pipeline-level* override for the internal `ignore_data` parameter described above.
  * `read_after_timestamp` – optional timestamp boundary that controls where ingestion should start from.

### `read_after_timestamp` format and behaviour

* The `read_after_timestamp` value **must** be provided in the exact format shown below:

  * Example: `2026-01-01 00:00:00.000001 UTC+00`
  * Pattern: `YYYY-MM-DD HH:MM:SS.ffffff UTC+HH`
* At runtime, the framework resolves an **effective** `read_after_timestamp` for each pipeline as follows:

  * If a value is present in `operations.orchestration_lakehouse.mct_config` for the corresponding `pipeline_id`, it is validated for format.
  * If there is already a `read_after_timestamp` defined in the data flow spec, the framework compares the two values.
  * If the value in the Unity Catalog table is **newer (later)** than the existing value in the data flow spec, it **replaces** the spec value and becomes the new effective boundary.
  * If it is older, the existing spec value is retained.
  * If there is no value in the spec, the table value is used as-is.
* The resulting effective `read_after_timestamp` is applied **consistently to both file-based and Delta-based pipelines**, ensuring a single control point for advancing the ingestion boundary.

This design allows operators to centrally manage per-pipeline ingestion cut-over points via a single Unity Catalog table, without modifying the underlying DLT pipeline code or data flow specifications.

---

## Operational Notes

* The `ignore_data` behaviour is **evaluated at pipeline start** based on the current `mct_config` and the cloud where the framework is running.
* Changes to `mct_config` (e.g. toggling overrides) will take effect on subsequent pipeline runs.
* For cutover patterns:

  * Set `ignore_data` (via appropriate override) to **true** in the standby environment while deep clone replication is establishing the data.
  * During planned cutover, switch the relevant override(s) to **false** to start ingesting live data through the pipelines.

---

## Summary

The new MCT configuration introduces a flexible, cloud-aware mechanism to control whether pipelines ingest data or only deploy table structures:

* **`ignore_data`** is the core internal flag controlling ingestion behaviour.
* **Pipeline-level** and **global** overrides provide explicit control when needed.
* **Cloud role logic** (primary vs standby) ensures sensible defaults when overrides are not set.
* This design supports robust **multi-cloud**, **DR**, and **cutover** scenarios while keeping the framework behaviour predictable and easy to reason about.
