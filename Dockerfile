# Use the official Python 3.11 slim image as the base
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies required for Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt to install dependencies
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the BUCDB folder into the container
COPY BUCDB /app/BUCDB

# Expose the port the Flask app will run on
EXPOSE 8000

# Set environment variables
ENV TOKENIZERS_PARALLELISM=false
ENV FLASK_ENV=production

# Command to run the Flask app, assuming app.py is in src/
CMD ["python", "src/app.py"]