from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.academics.models import Subject
from apps.content.models import ParsedDocument

from apps.academics.models import Subject, Branch, Semester
from apps.content.models import ParsedDocument

def home(request):
    branches = Branch.objects.all()
    semesters = Semester.objects.all()
    return render(request, 'content/home.html', {
        'branches': branches,
        'semesters': semesters
    })

@staff_member_required
def admin_ai_parser(request):
    subjects = Subject.objects.select_related('branch', 'semester').all()
    return render(request, 'content/admin_ai_parser.html', {'subjects': subjects})

def subject_dashboard(request, subject_id):
    """
    Displays the catalog of AI-parsed documents for a specific subject.
    """
    subject = get_object_or_404(Subject, pk=subject_id)
    documents = ParsedDocument.objects.filter(subject=subject, is_published=True).order_by('-year', '-created_at')
    
    # Evaluate global access for the padlock UI
    has_global_access = False
    if request.user.is_authenticated:
        if request.user.is_staff:
            has_global_access = True
        elif request.user.active_subscription_valid_until and request.user.active_subscription_valid_until >= timezone.now().date():
            has_global_access = True
            
    pyqs = [doc for doc in documents if doc.document_type == 'PYQ']
    notes = [doc for doc in documents if doc.document_type == 'NOTES']
    short_notes = [doc for doc in documents if doc.document_type == 'SHORT_NOTES']
    imp_qs = [doc for doc in documents if doc.document_type == 'IMPORTANT_Q']
    formulas = [doc for doc in documents if doc.document_type == 'FORMULA']
    syllabus = [doc for doc in documents if doc.document_type == 'SYLLABUS']
    crash_courses = [doc for doc in documents if doc.document_type == 'CRASH_COURSE']

    return render(request, 'content/subject_dashboard.html', {
        'subject': subject,
        'documents': documents,
        'pyqs': pyqs,
        'notes': notes,
        'short_notes': short_notes,
        'imp_qs': imp_qs,
        'formulas': formulas,
        'syllabus': syllabus,
        'crash_courses': crash_courses,
        'has_global_access': has_global_access
    })

@login_required
def read_document(request, document_id):
    """
    The Zero-PDF native JSON renderer. Includes premium access checks.
    """
    document = get_object_or_404(ParsedDocument, pk=document_id, is_published=True)
    user = request.user
    
    # Global Subscription Check
    has_global_pass = (
        user.active_subscription_valid_until and 
        user.active_subscription_valid_until >= timezone.now().date()
    )
    
    # Specific Unlocked Content Check (If they bought just this one PDF)
    has_specific_unlock = user.unlocked_contents.filter(
        product__subject=document.subject, 
        product__category__name__icontains=document.document_type
    ).exists()
    
    if document.is_premium:
        if not (has_global_pass or has_specific_unlock or user.is_staff):
            # User is locked out, redirect to dashboard
            return redirect('subject_dashboard', subject_id=document.subject.id)

    return render(request, 'content/document_reader.html', {
        'document': document
    })
