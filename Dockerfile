# Use an official Python runtime as a parent image
FROM python:3.9-slim

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

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel

# Install essential Django packages first
RUN pip install Django==4.2.17 \
    djangorestframework==3.15.2 \
    djangorestframework-simplejwt==5.3.1 \
    django-celery-results==2.5.1 \
    django-cors-headers==4.6.0 \
    django-debug-toolbar==5.0.1 \
    django-ckeditor-5==0.2.17 \
    django-redis==5.4.0 \
    django-storages==1.14.5 \
    google-generativeai==0.6.0 \
    whitenoise==6.2.0 \
    celery==5.4.0 \
    redis==5.2.1 \
    gunicorn \
    psycopg2==2.9.10 \
    python-dotenv==1.0.1

# Install necessary dependencies for TTS
RUN pip install numpy==1.23.5 && \
    pip install torch==2.0.0 torchaudio==2.0.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install git+https://github.com/coqui-ai/TTS.git@v0.13.0

# Fix protobuf version conflict
RUN pip uninstall -y protobuf google-api-core
RUN pip install protobuf==3.20.0 google-api-core==2.8.0

# Create a simple script to test the TTS module structure
RUN echo "import TTS; print(dir(TTS)); print('TTS modules available:', [m for m in dir(TTS) if not m.startswith('__')])" > /tmp/test_tts.py && \
    python /tmp/test_tts.py

# # Create the compatibility layer directly in the Dockerfile
# RUN echo "# Create compatibility layer for different TTS versions" > /app/tts_patch.py && \
#     echo "import sys" >> /app/tts_patch.py && \
#     echo "import importlib.util" >> /app/tts_patch.py && \
#     echo "# Check if TTS.api module exists" >> /app/tts_patch.py && \
#     echo "if importlib.util.find_spec('TTS.api') is None:" >> /app/tts_patch.py && \
#     echo "    print('Creating TTS.api compatibility layer')" >> /app/tts_patch.py && \
#     echo "    # If TTS.api doesn't exist, create it" >> /app/tts_patch.py && \
#     echo "    import TTS" >> /app/tts_patch.py && \
#     echo "    import types" >> /app/tts_patch.py && \
#     echo "    # Create the api module" >> /app/tts_patch.py && \
#     echo "    TTS.api = types.ModuleType('TTS.api')" >> /app/tts_patch.py && \
#     echo "    sys.modules['TTS.api'] = TTS.api" >> /app/tts_patch.py && \
#     echo "    # Create the TTS module" >> /app/tts_patch.py && \
#     echo "    from TTS.utils.synthesizer import Synthesizer" >> /app/tts_patch.py && \
#     echo "    TTS.api.TTS = Synthesizer" >> /app/tts_patch.py && \
#     echo "    print('TTS compatibility layer created successfully')" >> /app/tts_patch.py && \
#     echo "else:" >> /app/tts_patch.py && \
#     echo "    print('Using existing TTS.api module')" >> /app/tts_patch.py && \
#     echo "" >> /app/tts_patch.py

# Copy requirements.txt
COPY ./requirements.txt /app/

# Filter out problematic packages from requirements
RUN grep -v -E 'anaconda|conda|clyent|navigator|daal4py|mkl|TBB|numpy|TTS' requirements.txt > requirements_filtered.txt && \
    pip install -r requirements_filtered.txt || true

# Ensure NumPy is at the correct version after all installations
RUN pip install --force-reinstall numpy==1.23.5

# Fix critical dependency issues
RUN pip install boto3==1.37.6 botocore==1.37.6 django-storages==1.14.5 --no-cache-dir

# Install pydub
RUN pip install pydub==0.25.1

# Copy entrypoint.sh
COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy project code
COPY . /app/

# Set up SSL certificate directory
RUN mkdir -p /app/cert/
COPY ./cert/ca-certificate.crt /app/cert/
RUN chmod 644 /app/cert/ca-certificate.crt

# Create the NumPy patch for TTS
COPY ./tts_numpy_patch.py /app/
RUN echo '#!/bin/bash' > /wrapper.sh && \
    echo 'python /app/tts_numpy_patch.py' >> /wrapper.sh && \
    echo 'exec /entrypoint.sh "$@"' >> /wrapper.sh && \
    chmod +x /wrapper.sh

# Use the wrapper script as entrypoint
ENTRYPOINT ["/wrapper.sh"]

# Command to run the service
CMD ["gunicorn", "testrun.wsgi:application", "--bind", "0.0.0.0:8000"]

