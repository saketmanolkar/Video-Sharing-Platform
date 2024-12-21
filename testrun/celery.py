import os
from celery import Celery

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testrun.settings')

# Create celery app
app = Celery('testrun')

# Load celery config from django settings (CELERY_ prefixed settings)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()