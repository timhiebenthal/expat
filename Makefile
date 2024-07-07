install_requirements:
	pip install -r requirements.txt

dbt_run:
	cd dbt && dbt build --target prod

load_data:
	python loading/llm_earnings.py && python loading/cities.py && python loading/forex.py && python loading/costofliving.py

streamlit:
	streamlit run data_viz/streamlit_app.py

dev:
	docker run -v ./.env:/app/.env myapp:latest