from django.contrib import admin
from .models import ParsedDocument

@admin.register(ParsedDocument)
class ParsedDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'document_type', 'is_published', 'updated_at')
    list_filter = ('is_published', 'document_type', 'subject__branch')
    search_fields = ('title', 'subject__code')
