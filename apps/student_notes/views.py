import copy
import json
import uuid
import mimetypes
from pathlib import PurePosixPath

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Count
from django.http import JsonResponse, FileResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape
from django.views.decorators.http import require_GET, require_POST

from apps.academics.data_services import AcademicsDataService
from apps.academics.models import Subject, Unit

from .models import BaseNote, Note, NoteVersion


def _normalize_note_image_path(file_path: str) -> str:
    normalized = str(PurePosixPath('/' + (file_path or '').replace('\\', '/'))).lstrip('/')
    return normalized


def _is_authorized_note_image_path(user, storage_path: str) -> bool:
    if not user.is_authenticated:
        return False
    user_prefix = f"note_images/{user.id}/"
    return storage_path.startswith(user_prefix)


@login_required
def serve_note_image(request, file_path):
    """Serve note images through an authenticated endpoint for all storage backends."""
    storage_path = _normalize_note_image_path(file_path)

    if '..' in storage_path.split('/'):
        return HttpResponseForbidden('Invalid path.')

    if not _is_authorized_note_image_path(request.user, storage_path):
        return HttpResponseForbidden('Unauthorized image access.')

    if not default_storage.exists(storage_path):
        return HttpResponseNotFound('Image not found.')

    guessed_type, _ = mimetypes.guess_type(storage_path)
    response = FileResponse(default_storage.open(storage_path, 'rb'), content_type=guessed_type or 'application/octet-stream')
    response['Cache-Control'] = 'private, max-age=86400'
    return response


@login_required
def serve_note_image_legacy(request, file_path):
    """Legacy compatibility route for old /media/note_images/... URLs."""
    return serve_note_image(request, f"note_images/{file_path}")


# ── Pages ──────────────────────────────────────────────────────────────────────


@login_required
def index(request):
    """Shows subjects available for notes, with per-subject note counts."""
    user = request.user
    branch = getattr(user, 'preferred_branch', None)
    semester = getattr(user, 'preferred_semester', None)

    subjects = AcademicsDataService.get_subjects_by_branch_and_semester(branch, semester)

    # Per-subject note counts for this user
    note_counts = dict(
        Note.objects.filter(user=user)
        .values_list('subject_id')
        .annotate(c=Count('id'))
        .values_list('subject_id', 'c')
    )

    subject_data = []
    for subj in subjects:
        total_units = subj.units.count()
        subject_data.append({
            'subject': subj,
            'total_units': total_units,
            'notes_count': note_counts.get(subj.id, 0),
        })

    return render(request, 'student_notes/index.html', {
        'subject_data': subject_data,
    })


@login_required
def subject_notes(request, subject_id):
    """Lists all units for a subject with the student's note status."""
    subject = AcademicsDataService.get_subject_by_id(subject_id)
    if not subject:
        return redirect('dashboard')

    units = list(subject.units.all())

    user_notes = {
        n.unit_id: n
        for n in Note.objects.filter(user=request.user, subject=subject)
    }
    base_notes = {
        bn.unit_id: bn
        for bn in BaseNote.objects.filter(subject=subject, is_published=True)
    }

    unit_data = []
    for unit in units:
        note = user_notes.get(unit.id)
        base = base_notes.get(unit.id)
        block_count = 0
        if note and note.blocks and 'blocks' in note.blocks:
            block_count = sum(
                1 for b in note.blocks['blocks']
                if b.get('content', '').strip()
            )
        unit_data.append({
            'unit': unit,
            'note': note,
            'base_note': base,
            'block_count': block_count,
            'has_content': block_count > 0,
        })

    return render(request, 'student_notes/subject_notes.html', {
        'subject': subject,
        'unit_data': unit_data,
    })


@login_required
def editor(request, subject_id, unit_id):
    """The Notion-like block editor for a specific unit note."""
    subject = get_object_or_404(Subject, pk=subject_id, is_active=True)
    unit = get_object_or_404(Unit, pk=unit_id, subject=subject)

    note, _created = Note.objects.get_or_create(
        user=request.user,
        subject=subject,
        unit=unit,
    )

    base_note = BaseNote.objects.filter(
        subject=subject, unit=unit, is_published=True
    ).first()

    embed_mode = request.GET.get('embed') == '1'

    return render(request, 'student_notes/editor.html', {
        'note': note,
        'subject': subject,
        'unit': unit,
        'base_note': base_note,
        'blocks_json': json.dumps(note.blocks),
        'embed_mode': embed_mode,
    })


# ── API endpoints ──────────────────────────────────────────────────────────────


@login_required
@require_POST
def api_save(request):
    """Auto-save endpoint — receives blocks JSON and persists."""
    try:
        data = json.loads(request.body)
        note_id = data.get('note_id')
        blocks = data.get('blocks')
        create_version = data.get('create_version', False)

        if not note_id or blocks is None:
            return JsonResponse({'success': False, 'error': 'Missing fields'}, status=400)

        note = Note.objects.filter(pk=note_id, user=request.user).first()
        if not note:
            return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

        # Optionally snapshot before saving
        if create_version:
            NoteVersion.objects.create(note=note, blocks=note.blocks)
            # Keep only last 50 versions
            old_ids = list(
                NoteVersion.objects.filter(note=note)
                .order_by('-created_at')
                .values_list('id', flat=True)[50:]
            )
            if old_ids:
                NoteVersion.objects.filter(id__in=old_ids).delete()

        note.blocks = blocks
        note.save(update_fields=['blocks', 'updated_at'])

        return JsonResponse({
            'success': True,
            'updated_at': note.updated_at.isoformat(),
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_GET
def api_versions(request, note_id):
    """Returns version history for a note."""
    note = Note.objects.filter(pk=note_id, user=request.user).first()
    if not note:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    versions = NoteVersion.objects.filter(note=note)[:20]
    return JsonResponse({
        'success': True,
        'versions': [
            {'id': v.id, 'created_at': v.created_at.isoformat()}
            for v in versions
        ],
    })


@login_required
@require_GET
def api_version_detail(request, version_id):
    """Returns full blocks for a specific version."""
    try:
        version = NoteVersion.objects.select_related('note').get(
            pk=version_id, note__user=request.user
        )
    except NoteVersion.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    return JsonResponse({
        'success': True,
        'blocks': version.blocks,
        'created_at': version.created_at.isoformat(),
    })


@login_required
@require_POST
def api_restore_version(request, version_id):
    """Restores a note to a previous version."""
    try:
        version = NoteVersion.objects.select_related('note').get(
            pk=version_id, note__user=request.user
        )
    except NoteVersion.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    note = version.note

    # Save current state before restoring
    NoteVersion.objects.create(note=note, blocks=note.blocks)

    note.blocks = version.blocks
    note.save(update_fields=['blocks', 'updated_at'])

    return JsonResponse({
        'success': True,
        'blocks': note.blocks,
        'updated_at': note.updated_at.isoformat(),
    })


@login_required
@require_POST
def api_append_from_reader(request):
    """Append selected reader content (text/image) to a student's unit note."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    subject_id = data.get('subject_id')
    unit_id = data.get('unit_id')
    selected_text = (data.get('text') or '').strip()
    image_url = (data.get('image_url') or '').strip()
    image_urls = data.get('image_urls') or []
    source_title = (data.get('source_title') or '').strip()

    if not isinstance(image_urls, list):
        image_urls = []
    image_urls = [str(url).strip() for url in image_urls if str(url).strip()]
    if image_url:
        image_urls.append(image_url)

    if not subject_id or not unit_id:
        return JsonResponse({'success': False, 'error': 'Missing subject/unit'}, status=400)

    if not selected_text and not image_urls:
        return JsonResponse({'success': False, 'error': 'Nothing to append'}, status=400)

    subject = Subject.objects.filter(pk=subject_id, is_active=True).first()
    unit = Unit.objects.filter(pk=unit_id, subject_id=subject_id).first()
    if not subject or not unit:
        return JsonResponse({'success': False, 'error': 'Invalid subject or unit'}, status=404)

    note, _created = Note.objects.get_or_create(
        user=request.user,
        subject=subject,
        unit=unit,
    )

    # Version-protect current note if it has content
    current_blocks = note.blocks if isinstance(note.blocks, dict) else {'blocks': []}
    block_list = current_blocks.get('blocks')
    if not isinstance(block_list, list):
        block_list = []

    has_content = any((b.get('content') or '').strip() for b in block_list)
    if has_content:
        NoteVersion.objects.create(note=note, blocks=note.blocks)

    new_blocks = []

    if selected_text:
        safe_text = escape(selected_text).replace('\n', '<br>')
        new_blocks.append({
            'id': str(uuid.uuid4()),
            'type': 'paragraph',
            'content': safe_text,
            'attrs': {'from_reader': True, 'source_title': source_title},
            'children': [],
        })

    for queued_url in image_urls:
        new_blocks.append({
            'id': str(uuid.uuid4()),
            'type': 'image',
            'content': '',
            'attrs': {
                'url': queued_url,
                'caption': f'From {source_title}' if source_title else 'From reader',
                'align': 'left',
                'from_reader': True,
            },
            'children': [],
        })

    block_list.extend(new_blocks)
    note.blocks = {'blocks': block_list}
    note.save(update_fields=['blocks', 'updated_at'])

    return JsonResponse({
        'success': True,
        'note_id': note.id,
        'editor_url': reverse('student_notes:editor', args=[subject.id, unit.id]),
        'updated_at': note.updated_at.isoformat(),
    })


@login_required
@require_POST
def api_copy_base_note(request):
    """Copies admin base note into the student's personal note."""
    try:
        data = json.loads(request.body)
        base_note_id = data.get('base_note_id')

        base = BaseNote.objects.filter(pk=base_note_id, is_published=True).first()
        if not base:
            return JsonResponse({'success': False, 'error': 'Base note not found'}, status=404)

        note, created = Note.objects.get_or_create(
            user=request.user,
            subject=base.subject,
            unit=base.unit,
        )

        # Version-protect existing content
        if not created and note.blocks and note.blocks.get('blocks'):
            has_content = any(
                b.get('content', '').strip()
                for b in note.blocks['blocks']
            )
            if has_content:
                NoteVersion.objects.create(note=note, blocks=note.blocks)

        # Deep-copy with fresh IDs
        new_blocks = copy.deepcopy(base.blocks)
        for block in new_blocks.get('blocks', []):
            block['id'] = str(uuid.uuid4())
            for child in block.get('children', []):
                child['id'] = str(uuid.uuid4())

        note.blocks = new_blocks
        note.save(update_fields=['blocks', 'updated_at'])

        return JsonResponse({
            'success': True,
            'blocks': note.blocks,
            'note_id': note.id,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_upload_image(request):
    """Handles image upload for the note editor."""
    if 'image' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No image provided'}, status=400)

    image = request.FILES['image']

    # Validate
    max_size = 5 * 1024 * 1024  # 5 MB
    if image.size > max_size:
        return JsonResponse({'success': False, 'error': 'Image too large (max 5 MB)'}, status=400)

    allowed_types = {'image/webp'}
    if image.content_type not in allowed_types:
        return JsonResponse({'success': False, 'error': 'Invalid image type. Please upload WebP only.'}, status=400)

    filename = f"note_images/{request.user.id}/{uuid.uuid4().hex}.webp"
    # Use _save() directly to skip the exists()/HeadObject check.
    # The UUID filename is already guaranteed unique so the check is wasteful
    # and fails with 403 when the IAM role lacks s3:GetObject on this prefix.
    path = default_storage._save(filename, ContentFile(image.read()))
    url = reverse('student_notes:serve_note_image', args=[path])

    return JsonResponse({'success': True, 'url': url})
