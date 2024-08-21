install_requirements:
	pip install -r requirements.txt

load_data:
	python loading/llm_earnings.py && python loading/cities.py && python loading/forex.py && python loading/costofliving.py

dbt_init:
	cd dbt && dbt deps && dbt seed && cd ..

dbt_run:
	cd dbt && dbt build --target prod && cd ..

streamlit:
	streamlit run data_viz/streamlit_app.py

init: load_data dbt_init dbt_run streamlit

dev:
	docker run -v ./.env:/app/.env myapp:latest