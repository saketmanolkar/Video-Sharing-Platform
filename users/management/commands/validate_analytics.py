from django.core.management.base import BaseCommand
from users.models import UserActivitySummary, UserSession
from users.services.user_analytics_service import UserAnalyticsService
from users.services.follow_services import FollowService

class Command(BaseCommand):
    help = 'Validates UserActivitySummary data against direct calculations'

    def handle(self, *args, **options):
        self.stdout.write('Starting validation...')
        
        # Get first 4 summaries
        summaries = UserActivitySummary.objects.all()[:4]
        follow_service = FollowService()
        
        for summary in summaries:
            self.stdout.write(f"\n=== Validating {summary.user.username}'s Data ===")
            
            # Get direct calculations using UserAnalyticsService
            analytics = UserAnalyticsService.get_user_analytics(summary.user)
            profile_visits = UserAnalyticsService.get_profile_visits_count(summary.user)
            
            # Get direct follower counts using model relationships
            followers_count = summary.user.followers_set.count()
            following_count = summary.user.following_set.count()
            
            # Compare values
            self.stdout.write("\nTime Stats Comparison:")
            self.stdout.write(f"Total Sessions - Summary: {summary.total_sessions} | Direct: {analytics['time_stats']['session_count']}")
            self.stdout.write(f"Total Time - Summary: {summary.total_time_spent:.1f} | Direct: {analytics['time_stats']['total_time']:.1f}")
            self.stdout.write(f"Avg Session - Summary: {summary.avg_session_length:.1f} | Direct: {analytics['time_stats']['avg_session']:.1f}")
            self.stdout.write(f"Profile Visits - Summary: {summary.total_profile_visits} | Direct: {profile_visits}")
            self.stdout.write(f"Total Followers - Summary: {summary.total_followers} | Direct: {followers_count}")
            self.stdout.write(f"Total Following - Summary: {summary.total_following} | Direct: {following_count}")
            
            # Calculate differences
            session_diff = abs(summary.total_sessions - analytics['time_stats']['session_count'])
            time_diff = abs(summary.total_time_spent - analytics['time_stats']['total_time'])
            avg_diff = abs(summary.avg_session_length - analytics['time_stats']['avg_session'])
            visits_diff = abs(summary.total_profile_visits - profile_visits)
            followers_diff = abs(summary.total_followers - followers_count)
            following_diff = abs(summary.total_following - following_count)
            
            self.stdout.write("\nDiscrepancies:")
            if any([session_diff, time_diff > 0.1, avg_diff > 0.1, visits_diff, followers_diff, following_diff]):
                self.stdout.write(self.style.WARNING(f"⚠️  Sessions Difference: {session_diff}"))
                self.stdout.write(self.style.WARNING(f"⚠️  Total Time Difference: {time_diff:.1f}"))
                self.stdout.write(self.style.WARNING(f"⚠️  Avg Session Difference: {avg_diff:.1f}"))
                self.stdout.write(self.style.WARNING(f"⚠️  Profile Visits Difference: {visits_diff}"))
                self.stdout.write(self.style.WARNING(f"⚠️  Followers Difference: {followers_diff}"))
                self.stdout.write(self.style.WARNING(f"⚠️  Following Difference: {following_diff}"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ No significant discrepancies found!"))
                
            self.stdout.write("\nHeatmap Data Available:")
            self.stdout.write(f"Direct calculation has data: {'heatmap_data' in analytics}")