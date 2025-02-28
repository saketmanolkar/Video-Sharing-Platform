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

                # Track if this video has any mismatches
                video_has_issues = False

                # Basic Info Validation
                if not self.validate_field("Total Views", stored.total_views, calculated['total_views']):
                    video_has_issues = True
                
                if not self.validate_field("Total Comments", stored.total_comments, calculated['total_comments']):
                    video_has_issues = True
                
                if not self.validate_field("Total Likes", stored.total_likes, calculated['total_likes']):
                    video_has_issues = True
                
                if not self.validate_field("Total Dislikes", stored.total_dislikes, calculated['total_dislikes']):
                    video_has_issues = True
                
                if not self.validate_field("Watch Time", stored.watch_time, calculated['watch_time'], tolerance=0.01):
                    video_has_issues = True
                
                if not self.validate_field("Completion Rate", stored.completion_rate, calculated['completion_rate'], tolerance=0.01):
                    video_has_issues = True
                
                if not self.validate_field("Completed Views", stored.completed_views, calculated['completed_views']):
                    video_has_issues = True

                # Increment the counter if any field had a mismatch
                if video_has_issues:
                    self.stdout.write(self.style.ERROR(f"❌ Found mismatches in video: {video.title}"))
                    issues_found += 1
                else:
                    self.stdout.write(self.style.SUCCESS(f"✅ All fields match for video: {video.title}"))

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

    def validate_field(self, field_name, stored_value, calculated_value, tolerance=0):
        """Helper method to validate a field with optional tolerance for floats"""
        if isinstance(stored_value, float) and isinstance(calculated_value, float):
            difference = abs(stored_value - calculated_value)
            matches = difference <= tolerance
        else:
            matches = stored_value == calculated_value

        self.stdout.write(f"""
{field_name}:
• Stored: {stored_value}
• Calculated: {calculated_value}
{f'• Difference: {difference:.2f}' if isinstance(stored_value, float) else ''}
""")

        if not matches:
            self.stdout.write(self.style.WARNING(f"⚠️ {field_name} mismatch!"))
            return False
        return True