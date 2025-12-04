import dlt
from pyspark.sql.functions import col, expr

# --------------------------------------------------------------------
# Config – update this to your actual source table name
# --------------------------------------------------------------------
SOURCE_TABLE = "src_db.customers"   # e.g. "my_db.customer_src"

# --------------------------------------------------------------------
# 1) Read CDF from the source Delta table
#    (assumes CDF is already enabled on SOURCE_TABLE)
# --------------------------------------------------------------------
@dlt.table(
    name="customers_cdf_raw",
    comment="Streaming CDF feed from the source customers table"
)
def customers_cdf_raw():
    return (
        spark.readStream
            .format("delta")
            .option("readChangeFeed", "true")
            # pick ONE of these; startingVersion is usually easiest
            .option("startingVersion", 0)  
            # .option("startingTimestamp", "2024-01-01T00:00:00Z")
            .table(SOURCE_TABLE)
    )

# --------------------------------------------------------------------
# 2) Apply changes into the target DLT table
#    - CUSTOMER_ID is the business key
#    - LOAD_TIMESTAMP defines ordering of changes
#    - DELETE_FLAG (or CDF delete) treated as delete
# --------------------------------------------------------------------
dlt.apply_changes(
    target="customers",                 # name of the resulting DLT table
    source="customers_cdf_raw",         # the streaming CDF table above
    keys=["CUSTOMER_ID"],
    sequence_by=col("LOAD_TIMESTAMP"),

    # Treat either hard deletes from CDF or DELETE_FLAG=true as deletes
    apply_as_deletes=expr(
        "_change_type = 'delete' OR DELETE_FLAG = true"
    ),

    # Drop technical columns from the final table
    except_column_list=[
        "DELETE_FLAG",
        "LOAD_TIMESTAMP",
        "_change_type",
        "_commit_version",
        "_commit_timestamp",
        "_commit_user"
    ],

    # SCD1-style table (latest state only). Change to "2" for SCD2.
    stored_as_scd_type="1"
)
