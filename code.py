def _init_mct_config(self):
    """Initialize Multi-Cloud Targeting (MCT) configuration and set ignore_data flag."""
    mct_config = self.pipeline_config.get("mct_config", None)

    # ------------------------------------------------------------
    # CASE 1 — No mct_config: use pipeline override only
    # ------------------------------------------------------------
    if not mct_config:
        pipeline_override = (self.pipeline_details.get("ignore_data_override", "") or "").strip().lower()

        if pipeline_override == "true":
            self.ignore_data = True
        else:
            self.ignore_data = False

        self.logger.info(
            "MCT config not found, using pipeline override only -> ignore_data = %s",
            self.ignore_data,
        )
        return

    # ------------------------------------------------------------
    # Extract primary / standby from config
    # ------------------------------------------------------------
    primary = (mct_config.get("primary_cloud") or "").strip().lower()
    standby = (mct_config.get("standby_cloud") or "").strip().lower()

    # ------------------------------------------------------------
    # Pipeline override (string)
    # ------------------------------------------------------------
    pipeline_override_raw = (self.pipeline_details.get("ignore_data_override", "") or "").strip().lower()

    # ------------------------------------------------------------
    # Cloud-specific overrides (strings)
    # ignore_data_override_primary
    # ignore_data_override_standby
    # ------------------------------------------------------------
    global_override_primary_raw = (mct_config.get("ignore_data_override_primary", "") or "").strip().lower()
    global_override_standby_raw = (mct_config.get("ignore_data_override_standby", "") or "").strip().lower()

    # ------------------------------------------------------------
    # Determine derived cloud from hostname
    # ------------------------------------------------------------
    derived_cloud = "unknown"
    if self.workspace_host:
        parsed = urlparse(self.workspace_host)
        hostname = parsed.hostname.lower() if parsed.hostname else None

        if hostname:
            if hostname == "cloud.databricks.com" or hostname.endswith(".cloud.databricks.com"):
                derived_cloud = "aws"
            elif hostname == "azuredatabricks.net" or hostname.endswith(".azuredatabricks.net"):
                derived_cloud = "azure"

    # ------------------------------------------------------------
    # Log configuration details
    # ------------------------------------------------------------
    self.logger.info("MCT Configuration:")
    self.logger.info("  Workspace Host: %s", self.workspace_host)
    self.logger.info("  Derived Cloud Provider: %s", derived_cloud)
    self.logger.info("  Primary: %s", primary)
    self.logger.info("  Standby: %s", standby)
    self.logger.info("  Pipeline Override: %s", pipeline_override_raw)
    self.logger.info("  Global Override (Primary): %s", global_override_primary_raw)
    self.logger.info("  Global Override (Standby): %s", global_override_standby_raw)

    # ------------------------------------------------------------
    # PRECEDENCE 1 — Pipeline override
    # ------------------------------------------------------------
    if pipeline_override_raw in ("true", "false"):
        self.ignore_data = pipeline_override_raw == "true"
        self.logger.info("Pipeline override applied -> ignore_data = %s", self.ignore_data)
        return

    # ------------------------------------------------------------
    # PRECEDENCE 2 — Cloud-specific global override
    # ------------------------------------------------------------

    # Running in primary cloud
    if derived_cloud == primary and global_override_primary_raw in ("true", "false"):
        self.ignore_data = global_override_primary_raw == "true"
        self.logger.info(
            "Global primary override applied (value=%s) -> ignore_data = %s",
            global_override_primary_raw,
            self.ignore_data,
        )
        return

    # Running in standby cloud
    if derived_cloud == standby and global_override_standby_raw in ("true", "false"):
        self.ignore_data = global_override_standby_raw == "true"
        self.logger.info(
            "Global standby override applied (value=%s) -> ignore_data = %s",
            global_override_standby_raw,
            self.ignore_data,
        )
        return

    # ------------------------------------------------------------
    # PRECEDENCE 3 — Derived logic (fallback)
    # ignore = True ONLY when in standby environment
    # ------------------------------------------------------------
    if derived_cloud == primary:
        self.ignore_data = False
        self.logger.info("Derived rule: cloud == primary -> ignore_data = False")

    elif derived_cloud == standby:
        self.ignore_data = True
        self.logger.info("Derived rule: cloud == standby -> ignore_data = True")

    else:
        self.ignore_data = False
        self.logger.info("Derived rule: cloud does not match primary/standby -> ignore_data = False (default)")
