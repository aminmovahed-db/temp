def _validate_timestamp_for_dlt(self, timestamp_value) -> str:
        """
        Validate that timestamp value is in DLT-compatible format for startingTimestamp/modifiedAfter.
        
        Format: YYYY-MM-DD HH:mm:ss.microseconds UTC+00
        Pattern: ^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}\\.\\d{6} UTC\\+\\d{1,2}$
        
        Args:
            timestamp_value: Timestamp value from database (could be string or None)
            
        Returns:
            Timestamp string if compliant, or "" if None
            
        Raises:
            ValueError: If timestamp is not None and doesn't match the required format
        """
        if timestamp_value is None:
            return ""
        
        # Convert to string if not already
        timestamp_str = str(timestamp_value).strip()
        
        # Check if it matches the DLT format pattern
        # Pattern: YYYY-MM-DD HH:mm:ss.microseconds UTC+offset
        if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6} UTC\+\d{1,2}$', timestamp_str):
            return timestamp_str
        else:
            error_msg = (
                f"Timestamp '{timestamp_str}' is not in DLT-compatible format. "
                f"Expected format: YYYY-MM-DD HH:mm:ss.microseconds UTC+00 "
                f"(e.g., '2024-01-15 10:30:45.123456 UTC+00')"
            )
            self.logger.error(error_msg)
            raise ValueError(error_msg)