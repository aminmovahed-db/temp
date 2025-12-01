import re
from datetime import datetime

def _validate_timestamp_for_dlt(self, timestamp_value):
    """
    Validate that the timestamp value is in DLT-compatible UTC format.

    Accepted input format ONLY:
      YYYY-MM-DD HH:MM:SS.ffffff UTC+H
      YYYY-MM-DD HH:MM:SS.ffffff UTC+HH

    Returned value ALWAYS normalised to:
      YYYY-MM-DD HH:MM:SS.ffffff UTC+HHMM

    Example:
      Input:  "2024-01-01 00:00:00.000001 UTC+5"
      Output: "2024-01-01 00:00:00.000001 UTC+0500"
    """

    if timestamp_value is None:
        return ""

    timestamp_str = str(timestamp_value).strip()

    # --- Step 1: Regex validation (strict structure) ---
    pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6} UTC\+\d{1,2}$"
    if not re.match(pattern, timestamp_str):
        error_msg = (
            f"Invalid timestamp format: '{timestamp_str}'. Allowed format:\n"
            "  YYYY-MM-DD HH:MM:SS.ffffff UTC+H\n"
            "  YYYY-MM-DD HH:MM:SS.ffffff UTC+HH\n"
            "Example:\n"
            "  2024-01-01 00:00:00.000001 UTC+00\n"
        )
        self.logger.error(error_msg)
        raise ValueError(error_msg)

    # --- Step 2: Normalise timezone (UTC+H → UTC+HHMM) ---
    # Converts:
    #   UTC+5  → UTC+0500
    #   UTC+11 → UTC+1100
    #   UTC+00 → UTC+0000
    ts_norm = re.sub(
        r"UTC\+(\d{1,2})$",
        lambda m: f"UTC+{int(m.group(1)):02d}00",
        timestamp_str,
    )

    # --- Step 3: Validate datetime correctness ---
    try:
        datetime.strptime(ts_norm, "%Y-%m-%d %H:%M:%S.%f UTC%z")
    except ValueError as ex:
        error_msg = (
            f"Invalid timestamp: '{timestamp_str}'. "
            "Timestamp structure was correct, but datetime parsing failed. "
            f"Error: {ex}"
        )
        self.logger.error(error_msg)
        raise ValueError(error_msg)

    # --- Step 4: Return normalised string ---
    return ts_norm
