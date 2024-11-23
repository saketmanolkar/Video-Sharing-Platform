from django.contrib import admin

# Register your models here.
from .models import Video, Review, Tag, Playlist,Like, ViewHistory, VideoAnalytics


admin.site.register(Video)
admin.site.register(Tag)
admin.site.register(Playlist)
admin.site.register(Like)
admin.site.register(Review)
admin.site.register(ViewHistory)

@admin.register(VideoAnalytics)
class VideoAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploader_name', 'total_views', 'total_comments', 'total_likes', 'total_dislikes', 'created_at')
    list_filter = ('created_at', 'uploader')
    search_fields = ('title', 'uploader__username')
    ordering = ('-created_at',)

    def uploader_name(self, obj):
        return obj.uploader.username
    uploader_name.short_description = 'Uploader'  # Column header in admin