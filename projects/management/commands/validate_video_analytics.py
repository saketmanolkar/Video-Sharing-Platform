from django.core.management.base import BaseCommand
from projects.models import Video, VideoAnalytics, ViewHistory
from projects.management.commands.rebuild_analytics import Command as RebuildCommand
from django.db.models import Count

class Command(BaseCommand):
    help = 'Validates VideoAnalytics data against fresh calculations'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Starting analytics validation...')
        rebuild_command = RebuildCommand()
        
        videos = Video.objects.all()
        issues_found = 0
        
        for video in videos:
            try:
                self.stdout.write(f"\n\n📊 Checking video: {video.title}")
                
                stored = video.analytics
                calculated = rebuild_command.get_analytics_data(video)
                
                # Get actual counts
                total_views = video.views
                completed_views = ViewHistory.objects.filter(
                    video=video, 
                    completed=True
                ).count()

                # Always show watch time comparison
                self.stdout.write(f"""
Watch Time Check:
• Stored in analytics: {stored.watch_time:.2f}
• Fresh calculation: {calculated['watch_time']:.2f}
• Difference: {abs(stored.watch_time - calculated['watch_time']):.2f}
• Last Updated: {stored.updated_at}
""")
                if abs(stored.watch_time - calculated['watch_time']) > 0.01:
                    self.stdout.write(self.style.WARNING("⚠️ Watch time mismatch!"))
                    issues_found += 1

                # Always show completed views comparison
                self.stdout.write(f"""
Completed Views Check:
• Stored in analytics: {stored.completed_views}
• Fresh calculation: {calculated['completed_views']}
• Actual DB count: {completed_views}
• Last Updated: {stored.updated_at}
""")
                if stored.completed_views != calculated['completed_views']:
                    self.stdout.write(self.style.WARNING("⚠️ Completed views mismatch!"))
                    issues_found += 1

                # Always show completion rate comparison
                actual_rate = (completed_views / total_views * 100) if total_views > 0 else 0
                self.stdout.write(f"""
Completion Rate Check:
• Stored in analytics: {stored.completion_rate:.2f}%
• Fresh calculation: {calculated['completion_rate']:.2f}%
• Actual rate: {actual_rate:.2f}%
• Based on:
  - Completed views: {completed_views}
  - Total views: {total_views}
• Last Updated: {stored.updated_at}
""")
                if abs(stored.completion_rate - calculated['completion_rate']) > 0.01:
                    self.stdout.write(self.style.WARNING("⚠️ Completion rate mismatch!"))
                    issues_found += 1
                    
            except VideoAnalytics.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'❌ No analytics record found for video: {video.title}'
                ))
                issues_found += 1

        if issues_found == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ All analytics data matches fresh calculations!'))
        else:
            self.stdout.write(self.style.ERROR(
                f'\n❌ Found {issues_found} mismatches in analytics data'
            ))