import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testrun.settings')

# Create the Celery app
app = Celery('testrun')

# Load settings from Django settings (namespace='CELERY' means all celery-related settings should have a `CELERY_` prefix)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()