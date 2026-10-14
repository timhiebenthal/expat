install_requirements:
	uv sync

test:
	uv run pytest tests -v

# The formatter was declared as a dev dependency but nothing ran it: it was only
# reachable from a VS Code extension. Scoped to pipeline/ (the live SQL); dbt/ is
# dead until cutover.
fmt:
	uv run sqlfmt pipeline

run_tests_docker:
	docker build -t local_image \
		--build-arg APP_UID=$(shell id -u) --build-arg APP_GID=$(shell id -g) . \
		&& docker run --rm --env-file .env local_image uv run pytest tests -v

streamlit_app:
	uv run streamlit run streamlit/Home.py

local_build:
	docker build -t local_image \
		--build-arg APP_UID=$(shell id -u) --build-arg APP_GID=$(shell id -g) .

# The container runs as your uid, so everything it writes through the ./database
# mount stays yours. Without this, a root container leaves dwh.duckdb owned by
# root and the next `make streamlit_app` dies with "Permission denied".
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
	--set-env-vars NEBIUS_API_KEY=${NEBIUS_API_KEY} \

gcloud_delete:
	gcloud run services delete expat-streamlit-app