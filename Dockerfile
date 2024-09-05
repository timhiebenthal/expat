# Use an official Python runtime as a parent image
FROM python:3.11

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
COPY . /app

# Set environment variables
ENV DBT_PROFILES_DIR=/app/dbt/
ENV DUCKDB_LOCATION=/app/database/dwh.duckdb

# Install Node.js
RUN apt-get update && apt-get install -y curl sudo
RUN curl -sL https://deb.nodesource.com/setup_20.x | bash -
RUN apt-get install -y nodejs

# Install python requirements
RUN pip install -r requirements.txt

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