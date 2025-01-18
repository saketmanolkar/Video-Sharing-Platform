from django.contrib import admin

# Register your models here.
from .models import Video, Review, Tag, Playlist,Like, ViewHistory, VideoAnalytics, PlaylistItem


admin.site.register(Video)
admin.site.register(Tag)
admin.site.register(Playlist)
admin.site.register(Like)
admin.site.register(Review)
admin.site.register(PlaylistItem)

@admin.register(ViewHistory)
class ViewHistoryAdmin(admin.ModelAdmin):
    list_display = ['get_viewer', 'video', 'viewed_at', 'ip_address', 'window_id']
    readonly_fields = ['viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['user__username', 'video__title', 'ip_address']

    def get_viewer(self, obj):
        return obj.user.username if obj.user else f"Anonymous ({obj.ip_address})"
    get_viewer.short_description = 'Viewer'

@admin.register(VideoAnalytics)
class VideoAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploader_name', 'total_views', 'total_comments', 'total_likes', 'total_dislikes', 'created_at')
    list_filter = ('created_at', 'uploader')
    search_fields = ('title', 'uploader__username')
    ordering = ('-created_at',)

    def uploader_name(self, obj):
        return obj.uploader.username
    uploader_name.short_description = 'Uploader'  # Column header in admin