from django.contrib import admin
from .models import ParsedDocument, DocumentImage

from django.http import HttpResponseRedirect
from django.contrib import messages
from .services.ai_parser import DocumentParserService

class DocumentImageInline(admin.TabularInline):
    model = DocumentImage
    extra = 1

@admin.register(ParsedDocument)
class ParsedDocumentAdmin(admin.ModelAdmin):
    change_form_template = 'admin/parseddocument_change_form.html'
    inlines = [DocumentImageInline]
    list_display = ('title', 'subject', 'document_type', 'parsing_status', 'is_premium', 'is_published', 'updated_at')
    list_filter = ('parsing_status', 'is_published', 'is_premium', 'document_type', 'subject__branch')
    search_fields = ('title', 'subject__code')
    readonly_fields = ('parsing_status',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('subject', 'document_type', 'title', 'year', 'is_published')
        }),
        ('Pricing & Access', {
            'fields': ('is_premium', 'price'),
            'description': 'Configure if this document is free, requires a subscription, or has a specific unlock price.'
        }),
        ('AI Data Sources (Fill at least one)', {
            'fields': ('source_file', 'source_text'),
            'description': 'Upload a massive PDF OR paste raw text. You can also upload screenshots in the Images section below.'
        }),
        ('AI Configuration', {
            'fields': ('system_prompt',),
            'classes': ('collapse',)
        }),
        ('Generated Struct Data (Editable Preview)', {
            'fields': ('structured_data',),
        }),
    )

    class Media:
        js = ('js/admin_parsed_document.js',)
    
    def response_change(self, request, obj):
        if "_parse_ai" in request.POST:
            try:
                parser = DocumentParserService()
                data = parser.parse_document(obj)
                obj.structured_data = data
                obj.parsing_status = 'COMPLETED'
                obj.save()
                self.message_user(request, "Successfully parsed Document with AI!")
                return HttpResponseRedirect(".")
            except Exception as e:
                self.message_user(request, f"Parse failed: {e}", level=messages.ERROR)
                return HttpResponseRedirect(".")
        return super().response_change(request, obj)
