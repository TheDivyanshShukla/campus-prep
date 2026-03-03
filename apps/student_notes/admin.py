from django.contrib import admin
from .models import Note, NoteVersion, BaseNote


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'unit', 'updated_at')
    list_filter = ('subject__branch', 'subject__semester')
    search_fields = ('user__username', 'subject__code', 'unit__name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user', 'subject', 'unit')


@admin.register(NoteVersion)
class NoteVersionAdmin(admin.ModelAdmin):
    list_display = ('note', 'created_at')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)
    raw_id_fields = ('note',)


@admin.register(BaseNote)
class BaseNoteAdmin(admin.ModelAdmin):
    list_display = ('subject', 'unit', 'title', 'is_published', 'updated_at')
    list_filter = ('is_published', 'subject__branch', 'subject__semester')
    search_fields = ('title', 'subject__code', 'unit__name')
    raw_id_fields = ('subject', 'unit')
