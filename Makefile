install_requirements:
	pip install -r requirements.txt

dbt_run:
	cd dbt && dbt build

load_data:
	python loading/cities.py && python loading/forex.py && python loading/costofliving.py

streamlit:
	streamlit run data_viz/app.py