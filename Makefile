install_requirements:
	uv sync

test:
	uv run pytest tests -v

# The formatter was declared as a dev dependency but nothing ran it: it was only
# reachable from a VS Code extension. Scoped to pipeline/ (the live SQL); dbt/ is
# dead until cutover.
fmt:
	uv run sqlfmt pipeline

# Reuses the image local_build produces rather than building its own copy.
run_tests_docker: local_build
	docker run --rm --env-file .env local_image uv run pytest tests -v

streamlit_app:
	uv run streamlit run streamlit/Home.py

# Re-tagging local_image orphans the previous build as a dangling <none> image
# that nothing removes, so repeated builds quietly pile up a few GB each. Keep
# the old image's ID, build, then drop it once the new image is tagged. If a
# container still runs the old image docker refuses the removal, which is fine -
# it goes when that container does.
local_build:
	@old=$$(docker image inspect --format '{{.Id}}' local_image 2>/dev/null || true); \
	docker build -t local_image \
		--build-arg APP_UID=$(shell id -u) --build-arg APP_GID=$(shell id -g) . && \
	if [ -n "$$old" ]; then docker image rm "$$old" >/dev/null 2>&1 || true; fi

# The container runs as your uid, so everything it writes through the ./database
# mount stays yours. Without this, a root container leaves dwh.duckdb owned by
# root and the next `make streamlit_app` dies with "Permission denied".
local_deploy:
	docker rm -f expat-app 2>/dev/null || true
	docker run -d --name expat-app -p 8080:8080 --env-file .env \
		-v $(PWD)/database:/app/database local_image

local_stop:
	docker rm -f expat-app

# Reclaim disk from what the local targets leave behind: the dangling <none>
# images the builds orphan, this project's stopped container, and the build
# cache (dropping the cache makes the next build slower but frees the most).
# Tagged images (local_image, hermes-*), running containers and volumes are
# left untouched.
docker_prune:
	-docker rm -f expat-app
	docker image prune -f
	docker builder prune -f

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