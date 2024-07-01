install_requirements:
	pip install -r requirements.txt

dbt_run:
	cd dbt && dbt run

load_data:
	cd loading && python cities.py && python forex.py && python costofliving.py

streamlit:
	streamlit run data_viz/app.py

dev:
	docker run -v ./.env:/app/.env myapp:latest