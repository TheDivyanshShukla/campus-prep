from django.db import models
from apps.academics.models import Subject

class ParsedDocument(models.Model):
    DOCUMENT_TYPES = (
        ('PYQ', 'Previous Year Question Paper'),
        ('NOTES', 'Chapter Notes'),
        ('FORMULA', 'Formula Sheet'),
    )

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='parsed_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=255, help_text="e.g., '2023 OS Main Exam'")
    year = models.PositiveSmallIntegerField(null=True, blank=True, help_text="For PYQs")
    
    # Store the actual array/object returned from LangChain + OpenAI Structured Outputs
    structured_data = models.JSONField(help_text="Stores the exact LangChain parsed output.")
    
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.get_document_type_display()}] {self.title} - {self.subject.code}"
