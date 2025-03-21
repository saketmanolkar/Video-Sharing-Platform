from django.contrib import admin
from .models import Profile, Follow, Message, UserSession, UserActivitySummary, Report, Blog

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['user', 
                   'user_report_generated_at',
                   'video_report_generated_at',
                   'user_report_audio_generated_at',
                   'video_report_audio_generated_at']
    
    list_filter = ['user_report_generated_at', 
                  'video_report_generated_at',
                  'user_report_audio_generated_at',
                  'video_report_audio_generated_at']
    
    search_fields = ['user__username']
    
    readonly_fields = ['id']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'id', 'audio_is_generated')
        }),
        ('User Report', {
            'fields': ('user_report_url', 'user_report_generated_at',
                      'user_report_audio_file_url', 'user_report_audio_generated_at')
        }),
        ('Video Report', {
            'fields': ('video_report_url', 'video_report_generated_at',
                      'video_report_audio_file_url', 'video_report_audio_generated_at')
        }),
    )

# Register other models
admin.site.register(Profile)
admin.site.register(Follow)
admin.site.register(Message)
admin.site.register(UserSession)
admin.site.register(UserActivitySummary)
admin.site.register(Blog)