import yaml
import utils
import dlt
import logging

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)


pipeline = utils.define_dlt_pipeline("raw_cities")

# Load currencies from config.yml
with open('config.yml', 'r') as file:
    logging.info(">>>>>>>>>>>>>>>>> Loading cities from config.yml\n")
    config = yaml.safe_load(file)

    pipeline.run(
        data=config['cities'],
        table_name="cities",
        write_disposition="replace",
        primary_key="name",
    )

