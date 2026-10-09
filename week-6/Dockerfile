# Multi-Stage / Lightweight Production Dockerfile
FROM python:3.12-slim

# System metadata
LABEL maintainer="ZYROO AI/ML Internship Team"
LABEL description="AI Document Intelligence & Workflow Platform"

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ZYROO_STORAGE_DIR=/app/storage
ENV ZYROO_DB_FILE=/app/workflow_repository.db

WORKDIR /app

# Install system dependencies: tesseract-ocr, image libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app/

# Create storage directories
RUN mkdir -p /app/storage/invoices /app/storage/resumes /app/storage/contracts /app/storage/other

# Expose Streamlit (8501) and FastAPI (8000)
EXPOSE 8501 8000

# Default entrypoint: Start Streamlit UI
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
