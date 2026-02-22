from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden, FileResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import models
from django.http import JsonResponse, HttpResponseForbidden
import base64
import json
import os
import binascii
import hashlib
import uuid
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

@login_required
def explore_subjects(request):
    """
    Deprecated: Redirects to the personalized student dashboard.
    """
    return redirect('dashboard')

@staff_member_required
def admin_ai_parser(request):
    subjects = Subject.objects.select_related('branch', 'semester').all()
    return render(request, 'content/admin_ai_parser.html', {'subjects': subjects})

def subject_dashboard(request, subject_id):
    """
    Displays the catalog of AI-parsed documents for a specific subject.
    """
    subject = get_object_or_404(Subject, pk=subject_id)
    documents = ParsedDocument.objects.filter(subjects=subject, is_published=True).order_by('-year', '-created_at')
    
    has_gold_pass_general = False # Removed general flag, access is granular now
    unlocked_doc_ids = set()
    
    if request.user.is_authenticated:
        # Check granular Gold Pass unlocks for the exact document type
        for doc in documents:
            if doc.is_premium and request.user.has_gold_pass(subject, doc.document_type):
                unlocked_doc_ids.add(doc.id)
            
        # Get documents unlocked specifically by one-off purchase that haven't expired
        valid_unlocked = request.user.unlocked_contents.filter(
            parsed_document__isnull=False
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=timezone.now().date())
        ).values_list('parsed_document_id', flat=True)
        unlocked_doc_ids.update(valid_unlocked)
            
    pyqs = [doc for doc in documents if doc.document_type == 'PYQ']
    unsolved_pyqs = [doc for doc in documents if doc.document_type == 'UNSOLVED_PYQ']
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
        'unsolved_pyqs': unsolved_pyqs,
        'notes': notes,
        'short_notes': short_notes,
        'imp_qs': imp_qs,
        'formulas': formulas,
        'syllabus': syllabus,
        'crash_courses': crash_courses,
        'has_gold_pass': False, # Deprecated, keeping key for backwards compat if needed temporarily
        'unlocked_doc_ids': unlocked_doc_ids
    })

@login_required
def read_document(request, document_id, slug=None):
    """
    The Zero-PDF native JSON renderer. Includes premium access checks.
    """
    document = get_object_or_404(ParsedDocument, pk=document_id, is_published=True)
    user = request.user
    
    # Global Subscription Check
    has_gold_pass = any(user.has_gold_pass(subj, document.document_type) for subj in document.subjects.all())
    
    # Specific Unlocked Content Check (If they bought just this one PDF)
    has_specific_unlock = user.unlocked_contents.filter(
        models.Q(product__subject__in=document.subjects.all(), product__category__name__icontains=document.document_type) |
        models.Q(parsed_document=document)
    ).filter(
        models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=timezone.now().date())
    ).exists()
    
    if document.is_premium:
        if not (has_gold_pass or has_specific_unlock or user.is_staff):
            # User is locked out, redirect to dashboard (use the first linked subject as a fallback)
            fallback_subject = document.subjects.first()
            if fallback_subject:
                return redirect('subject_dashboard', subject_id=fallback_subject.id)
            else:
                return redirect('home')

    # Security: Obfuscate the structured json payload so it cannot be scraped via View Source or cURL
    # We generate a random hex key for every request and store it in the session
    key_bytes = os.urandom(16)
    key_hex = binascii.hexlify(key_bytes).decode('ascii')
    
    # Generate an anti-tamper nonce to prevent proxy replay extraction
    anti_tamper_nonce = binascii.hexlify(os.urandom(16)).decode('ascii')
    
    # Store the intended decryption key and nonce securely in the user's server-side session
    request.session[f'doc_key_{document.id}'] = {
        'key': key_hex,
        'nonce': anti_tamper_nonce
    }
    
    sd = document.structured_data if document.structured_data else {}
    json_str = json.dumps(sd).encode('utf-8')
    encoded = bytearray()
    for i, b in enumerate(json_str):
        encoded.append(b ^ key_bytes[i % len(key_bytes)])
        
    encrypted_data = base64.b64encode(encoded).decode('ascii')
    
    # Generate One-Time-Use Token for PDF.js (Prevents Network Replay/Scripting)
    pdf_token = uuid.uuid4().hex
    request.session[f'pdf_token_{document.id}'] = pdf_token

    return render(request, 'content/document_reader.html', {
        'document': document,
        'current_subject': document.subjects.first(),
        'encrypted_data': encrypted_data,
        'tamper_nonce': anti_tamper_nonce,
        'pdf_token': pdf_token,
        # The key is deliberately NOT sent in the HTML payload
    })

@login_required
def serve_secure_pdf(request, document_id):
    """
    Acts as an authenticated proxy to stream the raw PDF binary.
    Hides the true URL of the bucket/media folder and prevents unauthenticated downloads via URL sharing.
    """
    document = get_object_or_404(ParsedDocument, pk=document_id, is_published=True)
    user = request.user
    
    # Premium Access Checks
    has_gold_pass = any(user.has_gold_pass(subj, document.document_type) for subj in document.subjects.all())
    
    has_specific_unlock = user.unlocked_contents.filter(
        models.Q(product__subject__in=document.subjects.all(), product__category__name__icontains=document.document_type) |
        models.Q(parsed_document=document)
    ).filter(
        models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=timezone.now().date())
    ).exists()
    
    if document.is_premium and document.render_mode == 'DIRECT_PDF':
        if not (has_gold_pass or has_specific_unlock or user.is_staff):
            return HttpResponseForbidden("Unauthorized to view this PDF.")
            
    if not document.source_file:
        return HttpResponseForbidden("Document has no PDF file attached.")

    # BURN ON READ: One-Time Token Check
    client_token = request.headers.get('X-PDF-Token')
    session_key = f'pdf_token_{document_id}'
    server_token = request.session.get(session_key)

    if not client_token or client_token != server_token:
        # Token is invalid, missing, or already used
        return HttpResponseForbidden("PDF access token expired or invalid. Reload page to request a new token.")
        
    # BURN THE TOKEN IMMEDIATELY so it cannot be copied to cURL or accessed via Network Tab refresh
    del request.session[session_key]

    try:
        response = FileResponse(open(document.source_file.path, 'rb'), content_type='application/pdf')
        # Instruct browser to NEVER cache this file to prevent extraction from disk
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    except Exception as e:
        return HttpResponseForbidden("Failed to retrieve file.")

@login_required
@require_POST
def get_document_key(request, document_id):
    """
    Secure Key Delivery endpoint. The client must make an authenticated AJAX request
    *after* passing all anti-scraping traps. It retrieves the key from the server session
    and verifies the anti-tamper challenge.
    """
    session_key = f'doc_key_{document_id}'
    session_data = request.session.get(session_key)
    
    if not session_data or not isinstance(session_data, dict):
        return HttpResponseForbidden("Session expired or invalid.")
        
    server_key = session_data.get('key')
    server_nonce = session_data.get('nonce')
    
    try:
        body = json.loads(request.body)
        client_hash = body.get('challenge_hash')
    except json.JSONDecodeError:
        return HttpResponseForbidden("Invalid payload.")
        
    # Verify the Anti-Tamper Hash
    # The client must prove it ran the JS code unmodified by hashing the nonce with a shared secret
    expected_hash = hashlib.sha256((server_nonce + "RGPV_LIVE_SECURE_PAYLOAD").encode()).hexdigest()
    
    if not client_hash or client_hash != expected_hash:
        # If the hash fails, someone is spoofing the fetch request via Burp Suite
        del request.session[session_key]
        return HttpResponseForbidden("Integrity check failed. Session terminated.")
        
    # We delete it after one successful read to prevent replay attacks
    del request.session[session_key]
    
    return JsonResponse({'key': server_key})

@staff_member_required
def get_parsing_status(request, document_id):
    """
    API endpoint to poll for document parsing status and progress.
    Only accessible by staff (admins).
    """
    try:
        doc = ParsedDocument.objects.get(pk=document_id)
        return JsonResponse({
            'status': doc.parsing_status,
            'completed_steps': doc.parsing_completed_chunks,
            'total_steps': doc.parsing_total_chunks,
            'recreation_completed': doc.recreation_completed_images,
            'recreation_total': doc.recreation_total_images,
        })
    except ParsedDocument.DoesNotExist:
        return JsonResponse({'status': 'ERROR', 'message': 'Document not found'}, status=404)
