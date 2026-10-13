install_requirements:
	uv sync

test:
	uv run pytest tests -v

run_tests_docker:
	docker build -t local_image . && docker run --rm --env-file .env local_image uv run pytest tests -v

load_data:
	uv run python loading/llm_earnings.py && uv run python loading/forex.py && uv run python loading/costofliving.py

dbt_init:
	uv run dbt deps --profiles-dir ./dbt --project-dir ./dbt && uv run dbt seed --profiles-dir ./dbt --project-dir ./dbt

dbt_run:
	uv run dbt build --target prod --profiles-dir ./dbt --project-dir ./dbt

streamlit_app:
	uv run streamlit run streamlit/Home.py

init: load_data dbt_init dbt_run streamlit_app


local_build:
	docker build -t local_image .

local_deploy:
	docker rm -f expat-app 2>/dev/null || true
	docker run -d --name expat-app -p 8080:8080 --env-file .env \
		-v $(PWD)/database:/app/database local_image

local_stop:
	docker rm -f expat-app

gcloud_build:
	gcloud builds submit --tag gcr.io/expat-analytics/streamlit-app:latest --region europe-west1

gcloud_deploy:
	gcloud run deploy expat-streamlit-app \
	--image gcr.io/expat-analytics/streamlit-app:latest \
	--max-instances 2 \
	--concurrency 2 \
	--region europe-west3 \
	--allow-unauthenticated \
	--set-env-vars ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY} \

gcloud_delete:
	gcloud run services delete expat-streamlit-app