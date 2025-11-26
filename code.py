from datetime import datetime

def update_reader_option_if_newer(
    source_details: SourceDetailsCloudFiles,
    option_name: str,
    new_value: str
) -> None:
    """
    Update a timestamp-based reader option only if new_value is newer.
    Assumes timestamps are already validated via _validate_timestamp_for_dlt.
    """

    existing_value = source_details.readerOptions.get(option_name)

    # If option does not exist, set it directly
    if not existing_value:
        source_details.add_reader_options({option_name: new_value})
        return

    # Parse timestamps (safe because of your validator)
    fmt = "%Y-%m-%d %H:%M:%S.%f UTC%z"
    existing_dt = datetime.strptime(existing_value, fmt)
    new_dt = datetime.strptime(new_value, fmt)

    # Compare and update if needed
    if new_dt > existing_dt:
        source_details.add_reader_options({option_name: new_value})