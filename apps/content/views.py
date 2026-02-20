from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.academics.models import Subject
from apps.content.models import ParsedDocument

def home(request):
    return render(request, 'home.html')

@staff_member_required
def admin_ai_parser(request):
    subjects = Subject.objects.select_related('branch', 'semester').all()
    return render(request, 'admin_ai_parser.html', {'subjects': subjects})

def subject_dashboard(request, subject_id):
    """
    Displays the catalog of AI-parsed documents for a specific subject.
    """
    subject = get_object_or_404(Subject, pk=subject_id)
    documents = ParsedDocument.objects.filter(subject=subject, is_published=True).order_by('-year', '-created_at')
    
    # We will pass the request.user dynamically to the template to evaluate the padlock
    return render(request, 'subject_dashboard.html', {
        'subject': subject,
        'documents': documents
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
    
    if not (has_global_pass or has_specific_unlock or user.is_staff):
        # User is locked out, redirect to a premium pitch page (or back to dashboard with a message)
        # Note: We can implement messages framework later. For now, redirect to dashboard.
        return redirect('subject_dashboard', subject_id=document.subject.id)

    return render(request, 'document_reader.html', {
        'document': document
    })
