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
CRITICAL INSTRUCTION: DO NOT process or transcribe any Hindi text whatsoever. Extract and process ONLY the English versions of the questions.
For 'latex_answer' or any mathematical fields, use Markdown for normal text and wrap ANY math in KaTeX delimiters ($ for inline, $$ for block formulas)."""

class ParsedDocument(models.Model):
    DOCUMENT_TYPES = (
        ('SYLLABUS', 'Official Syllabus'),
        ('PYQ', 'Solved Previous Year Question Paper'),
        ('UNSOLVED_PYQ', 'Unsolved PYQ Paper'),
        ('NOTES', 'Notes'),
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

    subjects = models.ManyToManyField(Subject, related_name='parsed_documents', help_text="Select all branch/semester variants this document applies to. E.g. attach to AD's Physics, CSE's Physics, etc.")
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
    parsing_completed_chunks = models.PositiveIntegerField(default=0, help_text="Number of chunks processed so far")
    parsing_total_chunks = models.PositiveIntegerField(default=0, help_text="Total number of chunks to process")
    
    # Image Recreation Progress
    recreation_completed_images = models.PositiveIntegerField(default=0, help_text="Number of images recreated so far")
    recreation_total_images = models.PositiveIntegerField(default=0, help_text="Total number of images to recreate")
    
    # Store the actual array/object returned from LangChain + OpenAI Structured Outputs
    structured_data = models.JSONField(null=True, blank=True, help_text="Stores the exact LangChain parsed output. Auto-filled by AI.")
    
    is_published = models.BooleanField(default=False)
    
    # Display Settings
    RENDER_MODES = (
        ('NATIVE', 'Native AI Generated Render (JSON/Markdown)'),
        ('DIRECT_PDF', 'Direct PDF Render (Raw File Viewer)'),
    )
    render_mode = models.CharField(max_length=20, choices=RENDER_MODES, default='NATIVE', help_text="Choose how this document should be displayed to the user.")
    
    # Pricing & Access
    is_premium = models.BooleanField(default=False, help_text="Check if this content requires a premium subscription or one-time purchase.")
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Optional: Set a specific price to unlock just this document.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        subject_codes = ", ".join(set([s.code for s in self.subjects.all()])) if self.pk else "Unsaved"
        return f"[{self.get_document_type_display()}] {self.title} - {subject_codes}"

class DocumentImage(models.Model):
    document = models.ForeignKey(ParsedDocument, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='raw_docs/images/', help_text="Upload a screenshot or page scan")
    order = models.PositiveIntegerField(default=0, help_text="Order in which the AI should read this image (0, 1, 2...)")
    
    class Meta:
        ordering = ['order']
        
    def __str__(self):
        return f"Image {self.order} for {self.document.title}"
