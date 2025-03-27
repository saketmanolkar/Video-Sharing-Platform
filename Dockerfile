# Use an official Python runtime as a parent image
FROM python:3.9-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Remove AVX2 flags which don't work on ARM
ENV MAKEFLAGS="-j$(nproc)"
# Set ARM-compatible compiler flags
ENV CFLAGS="-O3"
# Ensure NumPy is properly linked
ENV PYTHONPATH=/usr/local/lib/python3.9/site-packages
# Ensure we can find libraries
ENV LD_LIBRARY_PATH=/usr/local/lib

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    ffmpeg \
    libsndfile1 \
    libpq-dev \
    git \
    curl \
    grep \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Split dependencies into smaller groups to reduce memory usage
# Core dependencies first
COPY requirements.txt /app/
RUN grep -v -E 'anaconda|conda|clyent|navigator|daal4py|mkl|TBB|numpy|TTS|torch|tensorflow' requirements.txt > core_requirements.txt && \
    pip install --no-cache-dir -r core_requirements.txt || echo "Some core packages failed to install"

# Install Django and web-related packages
RUN pip install --no-cache-dir \
    Django==4.2.17 \
    djangorestframework==3.15.2 \
    djangorestframework-simplejwt==5.3.1 \
    django-celery-results==2.5.1 \
    django-cors-headers==4.6.0 \
    django-debug-toolbar==5.0.1 \
    django-ckeditor-5==0.2.17 \
    django-redis==5.4.0 \
    django-storages==1.14.5 \
    whitenoise==6.2.0 \
    gunicorn \
    python-dotenv==1.0.1

# Database and caching dependencies
RUN pip install --no-cache-dir \
    psycopg2==2.9.10 \
    celery==5.4.0 \
    redis==5.2.1 \
    boto3==1.37.6 \
    botocore==1.37.6

# Install numpy first, as many packages depend on it
RUN pip install --no-cache-dir numpy==1.23.5

# Install ML dependencies
RUN pip install --no-cache-dir google-generativeai==0.6.0

# Install PyTorch separately (large package)
RUN pip install --no-cache-dir torch==2.0.0 torchaudio==2.0.1 --index-url https://download.pytorch.org/whl/cpu

# Install TTS as the final step
RUN pip install --no-cache-dir git+https://github.com/coqui-ai/TTS.git@v0.13.0

# Fix protobuf version conflicts
RUN pip uninstall -y protobuf google-api-core && \
    pip install --no-cache-dir protobuf==3.20.0 google-api-core==2.8.0

# Additional utilities
RUN pip install --no-cache-dir pydub==0.25.1

# Channels and Daphne
RUN pip install --no-cache-dir channels==4.0.0 channels-redis==4.0.0 daphne==4.0.0

# Create a new, clean image for the runtime environment
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/usr/local/lib/python3.9/site-packages
ENV LD_LIBRARY_PATH=/usr/local/lib

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project files
COPY . /app/

# Set up SSL certificate directory
RUN mkdir -p /app/cert/
COPY ./cert/ca-certificate.crt /app/cert/
RUN chmod 644 /app/cert/ca-certificate.crt

# Copy and prepare entrypoint script
COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
COPY ./tts_numpy_patch.py /app/
RUN echo '#!/bin/bash' > /wrapper.sh && \
    echo 'python /app/tts_numpy_patch.py' >> /wrapper.sh && \
    echo 'exec /entrypoint.sh "$@"' >> /wrapper.sh && \
    chmod +x /wrapper.sh

# Use the wrapper script as entrypoint
ENTRYPOINT ["/wrapper.sh"]

# Command to run the service
CMD ["gunicorn", "testrun.wsgi:application", "--bind", "0.0.0.0:8000"]

