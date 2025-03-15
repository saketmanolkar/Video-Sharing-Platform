from django.core.management.base import BaseCommand
from users.models import UserSession
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Cleanup old stray sessions'

    def handle(self, *args, **kwargs):
        # Define the cutoff time
        cutoff_time = timezone.now()
        
        # Find stray sessions 
        stray_sessions = UserSession.objects.filter(
            end_time__isnull=True,
            start_time__lt=cutoff_time
        )
        
        # Close them
        closed_count = stray_sessions.update(
            end_time=timezone.now(),
            activity_log={'closed_reason': 'auto_closed_by_cleanup'}
        )
        
        self.stdout.write(f"Closed {closed_count} old stray sessions.")
