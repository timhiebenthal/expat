# Use an official Python runtime as a parent image
FROM python:3.12

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

# Install poetry
RUN pip install -r requirements.txt

# Run app.py when the container launches
# CMD ["python", "app.py"]