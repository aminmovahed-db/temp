from pyspark.sql.utils import AnalysisException

def _get_mct_config_table(self, pipeline_id: str):
    """Query the mct_config table to get the ignore_data and read_after_timestamp
    values for the pipeline."""
    if not pipeline_id:
        self.logger.info(
            "Pipeline ID not available, skipping mct_config lookup"
        )
        return ("", "")

    try:
        # OPTIONAL: you can drop this block if you rely purely on AnalysisException
        if not self.spark.catalog.tableExists(MCT_CONFIG_TABLE):
            self.logger.info(
                "mct_config table '%s' does not exist, returning empty strings",
                MCT_CONFIG_TABLE,
            )
            return ("", "")

        escaped_pipeline_id = pipeline_id.replace("'", "''")
        query = f"""
            SELECT ignore_data, read_after_timestamp
            FROM {MCT_CONFIG_TABLE}
            WHERE pipeline_id = '{escaped_pipeline_id}'
        """

        self.logger.info(
            "Querying mct_config table '%s' for pipeline_id '%s'",
            MCT_CONFIG_TABLE,
            pipeline_id,
        )

        try:
            # This is the bit you wanted to protect
            result_df = self.spark.sql(query)
        except AnalysisException as ae:
            # Check Databricks error class
            error_class = getattr(ae, "errorClass", None)
            if error_class is None and hasattr(ae, "getErrorClass"):
                error_class = ae.getErrorClass()

            if (
                error_class == "TABLE_OR_VIEW_NOT_FOUND"
                or "TABLE_OR_VIEW_NOT_FOUND" in str(ae)
            ):
                self.logger.info(
                    "mct_config table or view '%s' not found "
                    "(TABLE_OR_VIEW_NOT_FOUND); returning empty strings "
                    "for pipeline_id '%s'",
                    MCT_CONFIG_TABLE,
                    pipeline_id,
                )
                return ("", "")
            # Different AnalysisException → re-raise so outer except handles it
            raise

        rows = result_df.collect()
        if rows and len(rows) > 0:
            ignore_data_value = rows[0][0]
            read_after_timestamp_value = rows[0][1]

            ignore_data_str = "" if ignore_data_value is None else str(ignore_data_value)
            read_after_timestamp_str = self._validate_timestamp_for_dlt(
                read_after_timestamp_value
            )

            self.logger.info(
                "Found ignore_data='%s', read_after_timestamp='%s' for pipeline_id '%s'",
                ignore_data_str,
                read_after_timestamp_str,
                pipeline_id,
            )
            return (ignore_data_str, read_after_timestamp_str)
        else:
            self.logger.info(
                "No matching record found in mct_config table '%s' for pipeline_id '%s'; "
                "returning empty strings",
                MCT_CONFIG_TABLE,
                pipeline_id,
            )
            return ("", "")

    except Exception as e:
        self.logger.warning(
            "Error querying mct_config table '%s' for pipeline_id '%s': %s. "
            "Returning empty strings.",
            MCT_CONFIG_TABLE,
            pipeline_id,
            str(e),
        )
        return ("", "")
