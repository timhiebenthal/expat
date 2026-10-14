FROM python:3.11-slim

# Set environment variables
ENV DUCKDB_LOCATION=/app/database/dwh.duckdb

# Set the working directory
WORKDIR /app

# Install Node.js & git
RUN apt-get update && apt-get install -y curl sudo
RUN curl -sL https://deb.nodesource.com/setup_20.x | bash -
RUN apt-get install -y nodejs
RUN apt-get install -y git
RUN apt-get install -y build-essential

# Install dependencies with uv, locked. Copied on their own so the (slow)
# dependency layer is cached independently of the application source.
COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# The pinned Bruin CLI. It is a Go binary, not a PyPI package, so it is
# curl-installed rather than coming from uv, and -b puts it in /usr/local/bin
# where the non-root app user can execute it. Placed after the dependency layer
# so a source change does not re-download it.
RUN curl -LsSf https://getbruin.com/install/cli | sh -s -- -b /usr/local/bin v0.11.778
# Fail the build rather than the first pipeline run if the CLI is not executable
# by the user the image drops to later.
RUN bruin version

# Copy the rest of the application code
COPY . .

# Fail the build rather than the browser. pyarrow hard-requires numpy>=2 but
# declares no numpy dependency, so an unconstrained resolver will happily
# produce an image that only breaks once Streamlit calls st.data_editor.
# Deliberately provider-agnostic: the LLM client differs per branch.
RUN python -c "import pandas, duckdb, streamlit, pyarrow, numpy"

# Add build argument for development mode
ARG DEVELOPMENT_MODE=false

# Run as an ordinary user, not root.
#
# The container writes database/dwh.duckdb through the ./database bind mount, so
# a root process leaves the warehouse owned by root:root on the host and the next
# `make streamlit_app` fails with "Permission denied". Matching the host uid keeps
# every file the container creates writable by the host user.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid ${APP_GID} app \
    && useradd --uid ${APP_UID} --gid ${APP_GID} -m app \
    && chown -R ${APP_UID}:${APP_GID} /app

# Expose port 8080 for Cloud Run (and 8501 for local Streamlit)
EXPOSE 8080 8501

# Use an entrypoint script to determine how to run the app
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Drop root only once every build step that needs it is done, so the image's own
# files stay root-owned and only runtime writes land as the app user.
USER app

ENTRYPOINT ["/entrypoint.sh"]