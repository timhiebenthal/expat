import yaml
import utils
import dlt

pipeline = utils.define_dlt_pipeline("raw_cities")

# Load currencies from config.yml
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

    pipeline.run(
        data=config['cities'],
        table_name="cities",
        write_disposition="replace",
        primary_key="name",
    )

