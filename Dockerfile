FROM python:3.11-slim

# Set environment variables
ENV DBT_PROFILES_DIR=/app/dbt/
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

# Copy the rest of the application code
COPY . .

# Fail the build rather than the browser. pyarrow hard-requires numpy>=2 but
# declares no numpy dependency, so an unconstrained resolver will happily
# produce an image that only breaks once Streamlit calls st.data_editor.
# Deliberately provider-agnostic: the LLM client differs per branch.
RUN python -c "import pandas, duckdb, streamlit, pyarrow, numpy"

# Add build argument for development mode
ARG DEVELOPMENT_MODE=false

# Conditional user setup for development
RUN if [ "$DEVELOPMENT_MODE" = "true" ]; then \
        groupadd --gid 1000 vscode && \
        useradd --uid 1000 --gid 1000 -m vscode && \
        chown -R vscode:vscode /app; \
    fi

# Expose port 8080 for Cloud Run (and 8501 for local Streamlit)
EXPOSE 8080 8501

# Use an entrypoint script to determine how to run the app
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]