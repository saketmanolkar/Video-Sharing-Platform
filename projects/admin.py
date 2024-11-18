from django.contrib import admin

# Register your models here.
from .models import Video, Review, Tag, Playlist,Like, ViewHistory


admin.site.register(Video)
admin.site.register(Tag)
admin.site.register(Playlist)
admin.site.register(Like)
admin.site.register(Review)
admin.site.register(ViewHistory)
