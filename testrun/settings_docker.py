from testrun.settings import *
import os

# Override database settings for Docker
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DATABASE_NAME', 'testrun_db'),
        'USER': os.environ.get('DATABASE_USER', 'postgres'),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DATABASE_HOST', 'db'),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'prefer',
        }
    }
}

# Disable DO Spaces for local Docker testing
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'mediafiles')

# Fix the Redis URL for Docker networking
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'

# Make sure DEBUG is set correctly
DEBUG = os.environ.get('DEBUG', '0') == '1'

# Allow all hosts in Docker for simplicity
ALLOWED_HOSTS = ['*']
