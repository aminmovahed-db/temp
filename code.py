def validate_timestamp(ts: str) -> str:
    """
    Valid formats:
      - 2024-01-01T00:00:00Z
      - 2024-01-01 00:00:00
      - 2024-01-01 00:00:00 UTC+00
    Raises ValueError on invalid input.
    """

    if not ts or not isinstance(ts, str):
        raise ValueError("Timestamp cannot be empty")

    ts = ts.strip()

    # 1. ISO format (handles Z → +00:00)
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return ts
    except ValueError:
        pass

    # 2. SQL format (no timezone)
    try:
        datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return ts
    except ValueError:
        pass

    # 3. SQL + UTC offset
    if "UTC" in ts:
        # Normalize: UTC+00 → UTC+0000
        ts_norm = re.sub(
            r"UTC([+-]\d{1,2})$",
            lambda m: f"UTC{int(m.group(1)): +03d}00".replace(" ", ""),
            ts
        )
        try:
            datetime.strptime(ts_norm, "%Y-%m-%d %H:%M:%S UTC%z")
            return ts
        except ValueError:
            pass

    # If nothing matched → error
    raise ValueError(
        f"Invalid timestamp format: '{ts}'. Allowed formats:\n"
        "  - 2024-01-01T00:00:00Z\n"
        "  - 2024-01-01 00:00:00\n"
        "  - 2024-01-01 00:00:00 UTC+00"
    )