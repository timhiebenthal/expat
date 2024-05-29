# Use an official Python runtime as a parent image
FROM python:3.12

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

ENV DBT_PROFILES_DIR=/workspaces/expat/dbt/

# Install Node.js
RUN apt-get update && apt-get install -y curl
RUN curl -sL https://deb.nodesource.com/setup_20.x | bash -
RUN apt-get install -y nodejs


RUN pip install -r requirements.txt

# Expose port 8501 for Streamlit
EXPOSE 8501

# Run Streamlit app
# CMD ["streamlit", "run", "your_streamlit_app.py"]