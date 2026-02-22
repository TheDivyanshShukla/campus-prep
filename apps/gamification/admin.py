from django.contrib import admin
from .models import GamerProfile, StudySession

@admin.register(GamerProfile)
class GamerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_xp', 'current_streak', 'longest_streak')
    search_fields = ('user__username', 'user__email')

@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'parsed_document', 'start_time', 'duration_seconds', 'is_active')
    list_filter = ('is_active', 'start_time')
    search_fields = ('user__username', 'parsed_document__title')
