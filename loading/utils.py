import dlt

DATABASE_LOCATION = "database/dwh.duckdb"

def define_dlt_pipeline(schema_name):
    return dlt.pipeline(
        pipeline_name="dwh",
        destination=dlt.destinations.duckdb(credentials=DATABASE_LOCATION),
        dataset_name=schema_name,
    )