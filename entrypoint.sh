#!/bin/bash

if [ "$DEVELOPMENT_MODE" = "true" ]; then
    # Development mode: don't start any services, just keep the container running
    exec tail -f /dev/null
else
    # Production mode: start Streamlit
    exec streamlit run --server.port 8080 --server.address 0.0.0.0 /app/streamlit/Home.py
fi