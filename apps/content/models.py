from django.db import models
from apps.academics.models import Subject

def default_system_prompt():
    return """You are an elite expert AI parser specializing in Engineering Academic exams for RGPV University.

CONTEXT:
Building material for Branch: {branch_name}
Subject: {subject_code} - {subject_name}
Document Type target: {document_type}

Your task is to extract exact information from raw exam papers, syllabi, or notes (provided as text or images) and generate pristine, highly-accurate structured data for them.
You MUST output valid JSON conforming strictly to the requested schema.
For 'latex_answer' or any mathematical fields, use Markdown for normal text and wrap ANY math in KaTeX delimiters ($ for inline, $$ for block formulas)."""

class ParsedDocument(models.Model):
    DOCUMENT_TYPES = (
        ('SYLLABUS', 'Official Syllabus'),
        ('PYQ', 'Previous Year Question Paper'),
        ('NOTES', 'Comprehensive Notes'),
        ('SHORT_NOTES', 'Quick Revision Short Notes'),
        ('IMPORTANT_Q', 'Important Questions'),
        ('FORMULA', 'Formula Sheet'),
        ('CRASH_COURSE', 'Video Crash Course Links'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending AI Parsing'),
        ('PROCESSING', 'Processing in Background'),
        ('COMPLETED', 'Successfully Parsed'),
        ('FAILED', 'Parsing Failed'),
    )

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='parsed_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=255, help_text="e.g., '2023 OS Main Exam'")
    year = models.PositiveSmallIntegerField(null=True, blank=True, help_text="For PYQs")
    
    # System Instructions
    system_prompt = models.TextField(
        default=default_system_prompt,
        help_text="The core instruction given to the AI. You can edit this directly per-document to steer the LLM."
    )
    
    # AI Input
    source_file = models.FileField(upload_to='raw_docs/', null=True, blank=True, help_text="Upload raw PDF or Image for AI Parsing")
    source_text = models.TextField(null=True, blank=True, help_text="OR paste raw text manually here if you don't have a file.")
    parsing_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', help_text="Current state of the AI Parser")
    
    # Store the actual array/object returned from LangChain + OpenAI Structured Outputs
    structured_data = models.JSONField(null=True, blank=True, help_text="Stores the exact LangChain parsed output. Auto-filled by AI.")
    
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.get_document_type_display()}] {self.title} - {self.subject.code}"

class DocumentImage(models.Model):
    document = models.ForeignKey(ParsedDocument, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='raw_docs/images/', help_text="Upload a screenshot or page scan")
    order = models.PositiveIntegerField(default=0, help_text="Order in which the AI should read this image (0, 1, 2...)")
    
    class Meta:
        ordering = ['order']
        
    def __str__(self):
        return f"Image {self.order} for {self.document.title}"
