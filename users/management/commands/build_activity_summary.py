from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from users.models import UserSession, UserActivitySummary
from users.services.user_analytics_service import UserAnalyticsService

User = get_user_model()

class Command(BaseCommand):
    help = 'Builds the denormalized activity summary table from UserSession data'

    def handle(self, *args, **kwargs):
        # Clear existing summaries
        self.stdout.write('Clearing existing summaries...')
        UserActivitySummary.objects.all().delete()

        # Get all users with sessions
        users = User.objects.filter(usersession__isnull=False).distinct()
        total_users = users.count()
        
        self.stdout.write(f'Processing {total_users} users...')

        analytics_service = UserAnalyticsService()

        for index, user in enumerate(users, 1):
            try:
                # Get analytics data using existing service
                analytics = analytics_service.get_user_analytics(user)
                time_stats = analytics['time_stats']
                
                # Get profile visits
                profile_visits = UserAnalyticsService.get_profile_visits_count(user)
                
                # Get last session
                last_session = UserSession.objects.filter(
                    user=user,
                    end_time__isnull=False
                ).order_by('-end_time').first()

                # Create summary
                UserActivitySummary.objects.create(
                    user=user,
                    total_sessions=time_stats['session_count'],
                    total_profile_visits=profile_visits,
                    total_time_spent=time_stats['total_time'],
                    avg_session_length=time_stats['avg_session'],
                    last_session_date=last_session.end_time if last_session else None
                )

                if index % 50 == 0:  # Progress update every 50 users
                    self.stdout.write(f'Processed {index}/{total_users} users')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing user {user.id}: {str(e)}')
                )
                continue

        self.stdout.write(self.style.SUCCESS('Successfully built activity summaries'))
