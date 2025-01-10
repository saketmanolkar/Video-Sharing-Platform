from django.contrib import admin
from .models import Profile, Follow, Message, UserSession, UserActivitySummary

admin.site.register(Profile)
admin.site.register(Follow)
admin.site.register(Message)
admin.site.register(UserSession)
admin.site.register(UserActivitySummary)