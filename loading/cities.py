import yaml
import utils
import dlt
import logging

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)


pipeline = utils.define_dlt_pipeline("raw_cities")


if __name__ == "__main__":
    print("__________")
    logging.info(f"Executing {__file__} ... \n")
    logging.info("Load cities data from config.yml to DuckDB")

    config = utils.load_config()

    # incremental syncing would be an overkill for these few rows
    pipeline.run(
        data=config["cities"], table_name="cities", write_disposition="replace"
    )

    logging.info(f"Loading successful for {len(config['cities']):,d} cities.\n")
