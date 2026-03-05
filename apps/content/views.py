from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden, FileResponse, Http404, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.text import slugify
from django.urls import reverse
from django.conf import settings
import re
import base64
import orjson
import json
import os
import binascii
import hashlib
import uuid
from urllib.parse import urlencode
from apps.content.data_services import ContentDataService
from apps.users.data_services import UserDataService
from apps.academics.data_services import AcademicsDataService
from apps.content.models import ParsedDocument

GUEST_ALLOWED_DOCUMENT_TYPES = {'UNSOLVED_PYQ', 'SYLLABUS'}

SEO_STATIC_PAGE_COPY = {
    'rgpv-notes': {
        'title': 'RGPV Notes',
        'description': 'Browse branch-wise and semester-wise RGPV notes. Read previews publicly and unlock full downloadable notes after login.',
        'keywords': 'rgpv notes, rgpv handwritten notes, rgpv branch wise notes',
    },
    'rgpv-syllabus': {
        'title': 'RGPV Syllabus',
        'description': 'Latest RGPV syllabus by branch, semester, and subject code with unit-wise breakdown and quick navigation.',
        'keywords': 'rgpv syllabus, rgpv semester syllabus, bt103 syllabus',
    },
    'rgpv-question-papers': {
        'title': 'RGPV Question Papers',
        'description': 'Previous year RGPV question papers organized by branch, semester, subject, and exam year.',
        'keywords': 'rgpv question papers, rgpv pyq, rgpv previous year papers',
    },
    'rgpv-important-questions': {
        'title': 'RGPV Important Questions',
        'description': 'Most important exam-focused questions for RGPV subjects with unit-level practice guidance.',
        'keywords': 'rgpv important questions, rgpv most asked questions',
    },
    'rgpv-results': {
        'title': 'RGPV Results Updates',
        'description': 'Result-related navigation and exam update pages for RGPV students.',
        'keywords': 'rgpv result, rgpv result date, rgpv updates',
    },
    'rgpv-exam-time-table': {
        'title': 'RGPV Exam Time Table',
        'description': 'Time table navigation for RGPV exams with branch and semester wise linking.',
        'keywords': 'rgpv exam time table, rgpv time table',
    },
    'rgpv-backlog-rules': {
        'title': 'RGPV Backlog Rules',
        'description': 'Understand RGPV backlog rules, attempts, and exam planning resources.',
        'keywords': 'rgpv backlog rules, rgpv atkt rules',
    },
    'rgpv-grading-system': {
        'title': 'RGPV Grading System',
        'description': 'RGPV grading system, CGPA insights, and exam performance planning pages.',
        'keywords': 'rgpv grading system, rgpv cgpa',
    },
    'rgpv-most-asked-questions': {
        'title': 'RGPV Most Asked Questions',
        'description': 'Frequently repeated and high-yield questions across RGPV subjects and semesters.',
        'keywords': 'rgpv most asked questions, rgpv repeated questions',
    },
    'rgpv-pass-in-one-night-guide': {
        'title': 'RGPV Pass in One Night Guide',
        'description': 'Quick exam survival guide with focused revision paths and important-unit prioritization for RGPV.',
        'keywords': 'rgpv pass in one night, rgpv exam strategy',
    },
    'rgpv-exam-tips': {
        'title': 'RGPV Exam Tips',
        'description': 'Practical exam tips and revision strategy pages for RGPV students.',
        'keywords': 'rgpv exam tips, rgpv preparation strategy',
    },
    'rgpv-result': {
        'title': 'RGPV Result',
        'description': 'RGPV result links, announcement updates, and result-related student FAQs.',
        'keywords': 'rgpv result, rgpv exam result',
    },
    'rgpv-result-date': {
        'title': 'RGPV Result Date',
        'description': 'Track RGPV result date related updates and official resource navigation.',
        'keywords': 'rgpv result date, rgpv result update',
    },
    'rgpv-exam-form-last-date': {
        'title': 'RGPV Exam Form Last Date',
        'description': 'Exam form deadline navigation and related notices for RGPV students.',
        'keywords': 'rgpv exam form last date, rgpv exam form',
    },
    'rgpv-time-table': {
        'title': 'RGPV Time Table',
        'description': 'RGPV time table related links by branch and semester.',
        'keywords': 'rgpv time table, rgpv exam schedule',
    },
    'rgpv-revaluation-process': {
        'title': 'RGPV Revaluation Process',
        'description': 'Revaluation process guidance and exam update links for RGPV.',
        'keywords': 'rgpv revaluation process, rgpv rechecking',
    },
    'rgpv-passing-marks': {
        'title': 'RGPV Passing Marks',
        'description': 'RGPV passing marks and exam criteria reference pages.',
        'keywords': 'rgpv passing marks, passing marks in rgpv',
    },
    'rgpv-grace-marks': {
        'title': 'RGPV Grace Marks',
        'description': 'Grace marks related pages and exam policy resources for RGPV students.',
        'keywords': 'rgpv grace marks, rgpv marks policy',
    },
    'rgpv-cgpa-calculation': {
        'title': 'RGPV CGPA Calculation',
        'description': 'CGPA calculation and grade interpretation resources for RGPV.',
        'keywords': 'rgpv cgpa calculation, rgpv sgpa cgpa',
    },
}

SEO_RESOURCE_MAP = {
    'syllabus': {'title': 'Syllabus', 'types': {'SYLLABUS'}},
    'notes': {'title': 'Notes', 'types': {'NOTES', 'SHORT_NOTES'}},
    'important-questions': {'title': 'Important Questions', 'types': {'IMPORTANT_Q'}},
    'previous-year-papers': {'title': 'Previous Year Papers', 'types': {'PYQ', 'UNSOLVED_PYQ'}},
}

SEO_RESOURCE_BY_DOC_TYPE = {
    'SYLLABUS': 'syllabus',
    'NOTES': 'notes',
    'SHORT_NOTES': 'notes',
    'IMPORTANT_Q': 'important-questions',
    'PYQ': 'previous-year-papers',
    'UNSOLVED_PYQ': 'previous-year-papers',
}


def _can_guest_access_document(document):
    return document.document_type in GUEST_ALLOWED_DOCUMENT_TYPES


def _can_access_document(user, document):
    if user.is_authenticated:
        return UserDataService.check_premium_access(user, document)

    if not _can_guest_access_document(document):
        return False

    return UserDataService.check_premium_access(user, document)


def _resolve_branch_from_slug(branch_slug):
    target = slugify(str(branch_slug or '')).strip('-').lower()
    if not target:
        return None

    branches = AcademicsDataService.get_all_branches()
    for branch in branches:
        code_slug = slugify(branch.code or '').lower()
        name_slug = slugify(branch.name or '').lower()
        if target == code_slug or target == name_slug:
            return branch
        if name_slug.startswith(target) or target in name_slug:
            return branch
    return None


def _resolve_semester_number(semester_slug):
    semester_slug = (semester_slug or '').strip().lower()
    if semester_slug.startswith('sem-'):
        semester_slug = semester_slug.replace('sem-', '', 1)
    if not semester_slug.isdigit():
        return None
    value = int(semester_slug)
    if value < 1 or value > 8:
        return None
    return value


def _canonical_semester_slug(semester_number):
    return f'sem-{semester_number}'


def _is_numeric_semester_slug(semester_slug):
    return str(semester_slug or '').strip().isdigit()


def _normalize_subject_code(subject_slug):
    return re.sub(r'[^a-zA-Z0-9]', '', str(subject_slug or '')).upper()


def _resolve_subject_from_slug(branch, semester, subject_slug):
    target_code = _normalize_subject_code(subject_slug)
    if not target_code:
        return None

    subjects = AcademicsDataService.get_subjects_by_branch_and_semester(branch, semester)
    for subject in subjects:
        normalized_db_code = _normalize_subject_code(subject.code)
        if normalized_db_code == target_code:
            return subject
    return None


def _subject_docs_for_resource(subject, resource_slug):
    docs = ContentDataService.get_published_documents_for_subject(subject)

    unit_match = re.match(r'^unit-(\d+)(?:-notes)?$', resource_slug)
    year_match = re.match(r'^question-paper-(\d{4})$', resource_slug)

    if resource_slug in SEO_RESOURCE_MAP:
        allowed = SEO_RESOURCE_MAP[resource_slug]['types']
        return [doc for doc in docs if doc.document_type in allowed], None, None

    if unit_match:
        unit_number = int(unit_match.group(1))
        filtered = [
            doc for doc in docs
            if doc.document_type in {'NOTES', 'SHORT_NOTES', 'IMPORTANT_Q'}
            and re.search(rf'\b(?:unit|u)\s*[-:#]?\s*{unit_number}\b', (doc.title or ''), flags=re.IGNORECASE)
        ]
        return filtered, unit_number, None

    if year_match:
        year_value = int(year_match.group(1))
        filtered = [
            doc for doc in docs
            if doc.document_type in {'PYQ', 'UNSOLVED_PYQ'} and doc.year == year_value
        ]
        return filtered, None, year_value

    return [], None, None


def _build_seo_doc_cards(request, subject, docs, branch_slug, semester_slug, subject_slug, resource_slug):
    unlocked_doc_ids = UserDataService.get_unlocked_document_ids(request.user, docs)
    cards = []
    for doc in docs:
        can_access = _can_access_document(request.user, doc)
        slug_part = slugify(doc.title or 'document')
        read_url = reverse('rgpv_seo_document', kwargs={
            'branch_slug': branch_slug,
            'semester_slug': semester_slug,
            'subject_slug': subject_slug,
            'resource_slug': resource_slug,
            'slug': slug_part,
        })
        login_url = f"{reverse('login')}?next={request.path}"
        checkout_url = reverse('checkout_document', kwargs={'document_id': doc.id}) if doc.price else ''
        gold_url = f"{reverse('checkout_gold_pass')}?branch={subject.branch.id}&semester={subject.semester.id}"

        cards.append({
            'doc': doc,
            'can_access': can_access,
            'is_unlocked': doc.id in unlocked_doc_ids,
            'read_url': read_url,
            'login_url': login_url,
            'checkout_url': checkout_url,
            'gold_url': gold_url,
        })
    return cards


def _build_seo_document_url(document):
    subject = document.subjects.first()
    if not subject:
        return None

    resource_slug = SEO_RESOURCE_BY_DOC_TYPE.get(document.document_type)
    if not resource_slug:
        return None

    return reverse('rgpv_seo_document', kwargs={
        'branch_slug': slugify(subject.branch.code),
        'semester_slug': _canonical_semester_slug(subject.semester.number),
        'subject_slug': slugify(subject.code),
        'resource_slug': resource_slug,
        'slug': slugify(document.title or 'document'),
    })


def rgpv_root(request):
    branches = AcademicsDataService.get_all_branches()
    semesters = AcademicsDataService.get_all_semesters()

    return render(request, 'content/seo_hub.html', {
        'seo_title': 'RGPV Notes, Syllabus, Question Papers & Important Questions',
        'seo_description': 'Public RGPV hub with branch-wise, semester-wise, and subject-code-wise pages for syllabus, notes, unit resources, and previous year papers.',
        'seo_keywords': 'rgpv notes, rgpv syllabus, rgpv pyq, bt103 notes, rgpv cse sem 1',
        'heading': 'RGPV Public Study Hub',
        'subheading': 'Explore branch, semester, and subject-code pages that students search on Google.',
        'branches': branches,
        'semesters': semesters,
        'subject_count': len(AcademicsDataService.get_all_active_subjects()),
        'is_nav_page': True,
    })


def rgpv_static_page(request, page_slug):
    page = SEO_STATIC_PAGE_COPY.get(page_slug)
    if not page:
        raise Http404('Page not found')

    branches = AcademicsDataService.get_all_branches()
    semesters = AcademicsDataService.get_all_semesters()

    return render(request, 'content/seo_hub.html', {
        'seo_title': f"{page['title']} | RGPV",
        'seo_description': page['description'],
        'seo_keywords': page['keywords'],
        'heading': page['title'],
        'subheading': page['description'],
        'branches': branches,
        'semesters': semesters,
        'subject_count': len(AcademicsDataService.get_all_active_subjects()),
        'is_nav_page': False,
    })


def rgpv_branches_page(request):
    branches = AcademicsDataService.get_all_branches()
    branch_rows = []

    for branch in branches:
        semesters = AcademicsDataService.get_active_semesters_for_branch(branch)
        semester_links = []
        subject_total = 0

        for semester in semesters:
            subjects = AcademicsDataService.get_subjects_by_branch_and_semester(branch, semester)
            subject_count = len(subjects)
            subject_total += subject_count

            semester_links.append({
                'number': semester.number,
                'url': reverse('rgpv_semester', kwargs={
                    'branch_slug': slugify(branch.code),
                    'semester_slug': _canonical_semester_slug(semester.number),
                }),
                'subject_count': subject_count,
            })

        branch_rows.append({
            'code': branch.code,
            'name': branch.name,
            'branch_url': reverse('rgpv_branch', kwargs={'branch_slug': slugify(branch.code)}),
            'subject_total': subject_total,
            'semester_links': semester_links,
        })

    return render(request, 'content/seo_branches_index.html', {
        'seo_title': 'RGPV Branches | CSE, IT, Mechanical, Civil, Electrical',
        'seo_description': 'Branch navigation for RGPV with semester and subject-level public pages.',
        'seo_keywords': 'rgpv branches, rgpv cse, rgpv it, rgpv mechanical',
        'branch_rows': branch_rows,
        'branch_count': len(branch_rows),
    })


def rgpv_semesters_page(request):
    branches = AcademicsDataService.get_all_branches()
    semesters = AcademicsDataService.get_all_semesters()

    semester_rows = []
    for semester in semesters:
        branch_links = []
        for branch in branches:
            subjects = AcademicsDataService.get_subjects_by_branch_and_semester(branch, semester)
            if not subjects:
                continue
            branch_links.append({
                'code': branch.code,
                'url': reverse('rgpv_semester', kwargs={
                    'branch_slug': slugify(branch.code),
                    'semester_slug': _canonical_semester_slug(semester.number),
                }),
                'subject_count': len(subjects),
            })

        semester_rows.append({
            'number': semester.number,
            'slug': _canonical_semester_slug(semester.number),
            'branch_links': branch_links,
        })

    return render(request, 'content/seo_semesters_index.html', {
        'seo_title': 'RGPV Semesters | Sem 1 to Sem 8',
        'seo_description': 'Semester navigation for RGPV resources across branches and subjects.',
        'seo_keywords': 'rgpv sem 1, rgpv sem 2, rgpv sem 8 syllabus',
        'semester_rows': semester_rows,
    })


def rgpv_subjects_page(request):
    subjects = AcademicsDataService.get_all_active_subjects()
    branches = AcademicsDataService.get_all_branches()
    semesters = AcademicsDataService.get_all_semesters()
    subject_rows = []
    for subject in subjects:
        subject_rows.append({
            'subject': subject,
            'branch_slug': slugify(subject.branch.code),
            'semester_slug': _canonical_semester_slug(subject.semester.number),
            'subject_slug': slugify(subject.code),
        })

    return render(request, 'content/seo_subject_index.html', {
        'seo_title': 'RGPV Subjects by Branch and Semester',
        'seo_description': 'Subject-code index pages for RGPV students. Browse by branch and semester.',
        'seo_keywords': 'rgpv subjects, bt103, cs402, rgpv subject code',
        'subject_rows': subject_rows,
        'branch_count': len(branches),
        'semester_count': len(semesters),
        'subject_count': len(subject_rows),
    })


def rgpv_branch_page(request, branch_slug):
    branch = _resolve_branch_from_slug(branch_slug)
    if not branch:
        raise Http404('Branch not found')

    semesters = AcademicsDataService.get_active_semesters_for_branch(branch)
    semester_rows = [
        {'number': semester.number, 'slug': _canonical_semester_slug(semester.number)}
        for semester in semesters
    ]

    return render(request, 'content/seo_branch.html', {
        'seo_title': f'RGPV {branch.code} Notes, Syllabus, Question Papers',
        'seo_description': f'RGPV {branch.name} branch page with semester navigation and subject resources.',
        'seo_keywords': f'rgpv {branch.code.lower()}, {branch.name.lower()} rgpv, rgpv {branch.code.lower()} notes',
        'branch': branch,
        'semester_rows': semester_rows,
    })


def rgpv_semester_page(request, branch_slug, semester_slug):
    branch = _resolve_branch_from_slug(branch_slug)
    semester_number = _resolve_semester_number(semester_slug)
    if not branch or semester_number is None:
        raise Http404('Invalid branch or semester')

    semester = AcademicsDataService.get_semester_by_number(semester_number)
    if not semester:
        raise Http404('Semester not found')

    canonical_semester_slug = _canonical_semester_slug(semester.number)
    if _is_numeric_semester_slug(semester_slug):
        return redirect('rgpv_semester', branch_slug=slugify(branch.code), semester_slug=canonical_semester_slug, permanent=True)

    subjects = AcademicsDataService.get_subjects_by_branch_and_semester(branch, semester)
    subject_rows = [
        {
            'subject': subject,
            'subject_slug': slugify(subject.code),
        }
        for subject in subjects
    ]

    return render(request, 'content/seo_semester.html', {
        'seo_title': f'RGPV {branch.code} Sem {semester.number} Subjects, Notes & Syllabus',
        'seo_description': f'RGPV {branch.name} semester {semester.number} subjects with syllabus, notes, and previous year paper pages.',
        'seo_keywords': f'rgpv {branch.code.lower()} sem {semester.number}, rgpv sem {semester.number} notes',
        'branch': branch,
        'semester': semester,
        'semester_slug': canonical_semester_slug,
        'subject_rows': subject_rows,
    })


def rgpv_subject_page(request, branch_slug, semester_slug, subject_slug):
    branch = _resolve_branch_from_slug(branch_slug)
    semester_number = _resolve_semester_number(semester_slug)
    if not branch or semester_number is None:
        raise Http404('Invalid branch or semester')

    semester = AcademicsDataService.get_semester_by_number(semester_number)
    if not semester:
        raise Http404('Semester not found')

    subject = _resolve_subject_from_slug(branch, semester, subject_slug)
    if not subject:
        raise Http404('Subject not found')

    canonical_semester_slug = _canonical_semester_slug(subject.semester.number)
    canonical_subject_slug = slugify(subject.code)
    if _is_numeric_semester_slug(semester_slug) or subject_slug != canonical_subject_slug:
        return redirect(
            'rgpv_subject',
            branch_slug=slugify(subject.branch.code),
            semester_slug=canonical_semester_slug,
            subject_slug=canonical_subject_slug,
            permanent=True,
        )

    units = AcademicsDataService.get_units_for_subject(subject)
    unit_links = [{'number': unit.number, 'slug': f'unit-{unit.number}'} for unit in units]
    resources = [
        {'slug': 'syllabus', 'label': 'Syllabus'},
        {'slug': 'notes', 'label': 'Notes'},
        {'slug': 'important-questions', 'label': 'Important Questions'},
        {'slug': 'previous-year-papers', 'label': 'Previous Year Papers'},
    ]

    return render(request, 'content/seo_subject.html', {
        'seo_title': f'{subject.code} {subject.name} (RGPV) | Syllabus, Notes, Unit-wise Resources',
        'seo_description': f'RGPV {subject.code} {subject.name} subject page with syllabus, notes, important questions, and previous year papers.',
        'seo_keywords': f'{subject.code.lower()} syllabus, {subject.code.lower()} notes, {subject.code.lower()} rgpv',
        'subject': subject,
        'units': units,
        'unit_links': unit_links,
        'resources': resources,
        'branch_slug': slugify(subject.branch.code),
        'semester_slug': canonical_semester_slug,
        'subject_slug': canonical_subject_slug,
    })


def rgpv_subject_resource_page(request, branch_slug, semester_slug, subject_slug, resource_slug):
    branch = _resolve_branch_from_slug(branch_slug)
    semester_number = _resolve_semester_number(semester_slug)
    if not branch or semester_number is None:
        raise Http404('Invalid branch or semester')

    semester = AcademicsDataService.get_semester_by_number(semester_number)
    if not semester:
        raise Http404('Semester not found')

    subject = _resolve_subject_from_slug(branch, semester, subject_slug)
    if not subject:
        raise Http404('Subject not found')

    canonical_semester_slug = _canonical_semester_slug(subject.semester.number)
    canonical_subject_slug = slugify(subject.code)
    if _is_numeric_semester_slug(semester_slug) or subject_slug != canonical_subject_slug:
        return redirect(
            'rgpv_subject_resource',
            branch_slug=slugify(subject.branch.code),
            semester_slug=canonical_semester_slug,
            subject_slug=canonical_subject_slug,
            resource_slug=resource_slug,
            permanent=True,
        )

    docs, unit_number, year_value = _subject_docs_for_resource(subject, resource_slug)
    if resource_slug not in SEO_RESOURCE_MAP and unit_number is None and year_value is None:
        raise Http404('Resource not found')

    page_label = SEO_RESOURCE_MAP.get(resource_slug, {}).get('title')
    if unit_number is not None:
        page_label = f'Unit {unit_number} Notes'
    if year_value is not None:
        page_label = f'Question Paper {year_value}'

    cards = _build_seo_doc_cards(
        request,
        subject,
        docs,
        branch_slug=slugify(subject.branch.code),
        semester_slug=canonical_semester_slug,
        subject_slug=canonical_subject_slug,
        resource_slug=resource_slug,
    )

    return render(request, 'content/seo_resource.html', {
        'seo_title': f'RGPV {subject.code} {page_label}',
        'seo_description': f'{page_label} for {subject.code} {subject.name} (RGPV). Public preview page with login unlock for full features.',
        'seo_keywords': f"{subject.code.lower()} {resource_slug.replace('-', ' ')}, rgpv {subject.code.lower()}",
        'subject': subject,
        'resource_slug': resource_slug,
        'resource_label': page_label,
        'cards': cards,
        'unit_number': unit_number,
        'year_value': year_value,
        'branch_slug': slugify(subject.branch.code),
        'semester_slug': canonical_semester_slug,
        'subject_slug': canonical_subject_slug,
    })


def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse('seo_sitemap_xml'))
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        'Disallow: /dashboard/',
        f'Sitemap: {sitemap_url}',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


def seo_sitemap_xml(request):
    static_names = [
        'rgpv_root', 'rgpv_branches', 'rgpv_semesters', 'rgpv_subjects',
        'rgpv_notes', 'rgpv_syllabus', 'rgpv_question_papers', 'rgpv_important_questions',
        'rgpv_results', 'rgpv_exam_time_table', 'rgpv_backlog_rules', 'rgpv_grading_system',
        'rgpv_most_asked_questions', 'rgpv_pass_one_night', 'rgpv_exam_tips',
        'rgpv_result', 'rgpv_result_date', 'rgpv_exam_form_last_date', 'rgpv_time_table',
        'rgpv_revaluation_process', 'rgpv_passing_marks', 'rgpv_grace_marks', 'rgpv_cgpa_calculation',
    ]

    urls = []
    for name in static_names:
        urls.append(request.build_absolute_uri(reverse(name)))

    branches = AcademicsDataService.get_all_branches()
    for branch in branches:
        branch_slug = slugify(branch.code)
        urls.append(request.build_absolute_uri(reverse('rgpv_branch', kwargs={
            'branch_slug': branch_slug,
        })))

        active_semesters = AcademicsDataService.get_active_semesters_for_branch(branch)
        for semester in active_semesters:
            urls.append(request.build_absolute_uri(reverse('rgpv_semester', kwargs={
                'branch_slug': branch_slug,
                'semester_slug': _canonical_semester_slug(semester.number),
            })))

    subjects = AcademicsDataService.get_all_active_subjects()[:1200]
    for subject in subjects:
        branch_slug = slugify(subject.branch.code)
        semester_slug = f'sem-{subject.semester.number}'
        subject_slug = slugify(subject.code)

        urls.append(request.build_absolute_uri(reverse('rgpv_subject', kwargs={
            'branch_slug': branch_slug,
            'semester_slug': semester_slug,
            'subject_slug': subject_slug,
        })))

        for resource_slug in ['syllabus', 'notes', 'important-questions', 'previous-year-papers']:
            urls.append(request.build_absolute_uri(reverse('rgpv_subject_resource', kwargs={
                'branch_slug': branch_slug,
                'semester_slug': semester_slug,
                'subject_slug': subject_slug,
                'resource_slug': resource_slug,
            })))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc in urls:
        xml.append('<url>')
        xml.append(f'<loc>{loc}</loc>')
        xml.append('</url>')
    xml.append('</urlset>')
    return HttpResponse('\n'.join(xml), content_type='application/xml')


def _render_document_reader(request, document, back_url):
    key_bytes = os.urandom(16)
    key_hex = binascii.hexlify(key_bytes).decode('ascii')

    anti_tamper_nonce = binascii.hexlify(os.urandom(16)).decode('ascii')

    request.session[f'doc_key_{document.id}'] = {
        'key': key_hex,
        'nonce': anti_tamper_nonce
    }

    sd = document.structured_data if document.structured_data else {}
    json_bytes = orjson.dumps(sd)

    encoded = bytearray(json_bytes)
    key_len = len(key_bytes)
    for i in range(len(encoded)):
        encoded[i] ^= key_bytes[i % key_len]

    encrypted_data = base64.b64encode(encoded).decode('ascii')

    pdf_token = uuid.uuid4().hex
    request.session[f'pdf_token_{document.id}'] = pdf_token

    current_subject = document.subjects.first()
    subject_units = []
    preferred_unit_number = None
    if current_subject:
        subject_units = list(
            current_subject.units.all()
            .order_by('number')
            .values('id', 'number', 'name')
        )

    title = (document.title or '')
    unit_match = re.search(r'\b(?:unit|u)\s*[-:#]?\s*(\d{1,2})\b', title, flags=re.IGNORECASE)
    if unit_match:
        try:
            preferred_unit_number = int(unit_match.group(1))
        except (TypeError, ValueError):
            preferred_unit_number = None

    return render(request, 'content/document_reader.html', {
        'document': document,
        'current_subject': current_subject,
        'back_url': back_url,
        'subject_units': subject_units,
        'preferred_unit_number': preferred_unit_number,
        'can_append_to_notes': request.user.is_authenticated and current_subject is not None,
        'encrypted_data': encrypted_data,
        'tamper_nonce': anti_tamper_nonce,
        'pdf_token': pdf_token,
    })


def _resolve_resource_document_by_slug(subject, resource_slug, slug):
    docs, _, _ = _subject_docs_for_resource(subject, resource_slug)
    target_slug = slugify(slug)

    for doc in docs:
        if slugify(doc.title or 'document') == target_slug:
            return doc

    return None

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    branches = ContentDataService.get_all_branches()
    semesters = ContentDataService.get_all_semesters()

    return render(request, 'content/home.html', {
        'branches': branches,
        'semesters': semesters,
        'user_branch_id': None,
        'user_semester_id': None,
        'is_onboarded': False,
    })

def explore_subjects(request):
    """Public subject explorer filtered by branch and semester."""
    branches = ContentDataService.get_all_branches()
    semesters = ContentDataService.get_all_semesters()

    branch_id = request.GET.get('branch') or request.POST.get('branch')
    semester_id = request.GET.get('semester') or request.POST.get('semester')

    branch = None
    semester = None

    if branch_id:
        branch = AcademicsDataService.get_branch_by_id(branch_id)
    if semester_id:
        semester = AcademicsDataService.get_semester_by_id(semester_id)

    if not branch and branches:
        branch = branches[0]
    if not semester and semesters:
        semester = semesters[0]

    subjects = ContentDataService.get_subjects_by_branch_and_semester(branch, semester)

    return render(request, 'content/explore_subjects.html', {
        'subjects': subjects,
        'branch': branch,
        'semester': semester,
        'branches': branches,
        'semesters': semesters,
    })

@staff_member_required
def admin_ai_parser(request):
    subjects = AcademicsDataService.get_all_active_subjects()
    return render(request, 'content/admin_ai_parser.html', {'subjects': subjects})

def subject_dashboard(request, subject_id):
    """
    Displays the catalog of AI-parsed documents for a specific subject.
    """
    subject = ContentDataService.get_subject_by_id(subject_id)
    if not subject:
        return redirect('home')
        
    documents = ContentDataService.get_published_documents_for_subject(subject)
    unlocked_doc_ids = UserDataService.get_unlocked_document_ids(request.user, documents)
            
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
        'has_gold_pass': False, # Deprecated
        'unlocked_doc_ids': unlocked_doc_ids
    })

def read_document(request, document_id, slug=None):
    """
    The Zero-PDF native JSON renderer. Includes premium access checks.
    """
    document = ContentDataService.get_document_by_id(document_id)
    if not document:
        return redirect('home')

    if not request.user.is_authenticated:
        seo_url = _build_seo_document_url(document)
        if seo_url:
            return redirect(seo_url)
        
    user = request.user

    if not _can_access_document(user, document):
        if not user.is_authenticated and not _can_guest_access_document(document):
            return redirect('login')

        # User is locked out, redirect to dashboard/subject
        fallback_subject = document.subjects.first()
        if fallback_subject:
            return redirect('subject_dashboard', subject_id=fallback_subject.id)
        else:
            return redirect('home')

    current_subject = document.subjects.first()

    next_path = request.GET.get('next', '')
    has_safe_next = isinstance(next_path, str) and next_path.startswith('/') and not next_path.startswith('//')

    back_url = reverse('home')
    if current_subject:
        back_url = reverse('subject_dashboard', kwargs={'subject_id': current_subject.id})
    if has_safe_next:
        back_url = next_path

    return _render_document_reader(request, document, back_url)


def read_document_from_seo(request, branch_slug, semester_slug, subject_slug, resource_slug, slug=None):
    branch = _resolve_branch_from_slug(branch_slug)
    semester_number = _resolve_semester_number(semester_slug)
    if not branch or semester_number is None:
        raise Http404('Invalid branch or semester')

    semester = AcademicsDataService.get_semester_by_number(semester_number)
    if not semester:
        raise Http404('Semester not found')

    subject = _resolve_subject_from_slug(branch, semester, subject_slug)
    if not subject:
        raise Http404('Subject not found')

    document = _resolve_resource_document_by_slug(subject, resource_slug, slug)
    if not document:
        raise Http404('Document not found for resource')

    user = request.user
    if not _can_access_document(user, document):
        if not user.is_authenticated and not _can_guest_access_document(document):
            return redirect('login')

        return redirect('rgpv_subject_resource', branch_slug=slugify(subject.branch.code), semester_slug=_canonical_semester_slug(subject.semester.number), subject_slug=slugify(subject.code), resource_slug=resource_slug)

    back_url = reverse('rgpv_subject_resource', kwargs={
        'branch_slug': slugify(subject.branch.code),
        'semester_slug': _canonical_semester_slug(subject.semester.number),
        'subject_slug': slugify(subject.code),
        'resource_slug': resource_slug,
    })
    return _render_document_reader(request, document, back_url)


def read_document_from_seo_legacy(request, branch_slug, semester_slug, subject_slug, resource_slug, document_id, slug=None):
    branch = _resolve_branch_from_slug(branch_slug)
    semester_number = _resolve_semester_number(semester_slug)
    if not branch or semester_number is None:
        raise Http404('Invalid branch or semester')

    semester = AcademicsDataService.get_semester_by_number(semester_number)
    if not semester:
        raise Http404('Semester not found')

    subject = _resolve_subject_from_slug(branch, semester, subject_slug)
    if not subject:
        raise Http404('Subject not found')

    document = ContentDataService.get_document_by_id(document_id)
    if not document:
        raise Http404('Document not found')

    return redirect(
        'rgpv_seo_document',
        branch_slug=slugify(subject.branch.code),
        semester_slug=_canonical_semester_slug(subject.semester.number),
        subject_slug=slugify(subject.code),
        resource_slug=resource_slug,
        slug=slugify(document.title or 'document'),
        permanent=True,
    )


def read_document_from_seo_legacy_slug(request, branch_slug, semester_slug, subject_slug, resource_slug, slug=None):
    branch = _resolve_branch_from_slug(branch_slug)
    semester_number = _resolve_semester_number(semester_slug)
    if not branch or semester_number is None:
        raise Http404('Invalid branch or semester')

    semester = AcademicsDataService.get_semester_by_number(semester_number)
    if not semester:
        raise Http404('Semester not found')

    subject = _resolve_subject_from_slug(branch, semester, subject_slug)
    if not subject:
        raise Http404('Subject not found')

    return redirect(
        'rgpv_seo_document',
        branch_slug=slugify(subject.branch.code),
        semester_slug=_canonical_semester_slug(subject.semester.number),
        subject_slug=slugify(subject.code),
        resource_slug=resource_slug,
        slug=slugify(slug or ''),
        permanent=True,
    )

def serve_secure_pdf(request, document_id):
    """
    Acts as an authenticated proxy to stream the raw PDF binary.
    """
    document = ContentDataService.get_document_by_id(document_id)
    if not document:
        return HttpResponseForbidden("Document not found.")
        
    if not _can_access_document(request.user, document):
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
        # Optimization: Redirect to the signed S3/B2 URL directly to offload transfer.
        # Use a very short expiration (30 seconds) to ensure security.
        default_storage_backend = settings.STORAGES.get("default", {}).get("BACKEND", "")
        is_s3_storage = default_storage_backend == "storages.backends.s3.S3Storage"

        if os.getenv('B2_DIRECT_DELIVERY', 'False') == 'True' and is_s3_storage:
            storage = document.source_file.storage
            # Generate a URL that expires in 5 seconds
            signed_url = storage.url(document.source_file.name, expire=5)
            return redirect(signed_url)
            
        # Fallback/Proxy: Stream through Django if CORS is an issue or direct delivery is disabled.
        response = FileResponse(document.source_file.open('rb'), content_type='application/pdf')
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    except Exception as e:
        return HttpResponseForbidden("Failed to retrieve file.")

@require_POST
def get_document_key(request, document_id):
    """
    Secure Key Delivery endpoint. The client must make an authenticated AJAX request
    *after* passing all anti-scraping traps. It retrieves the key from the server session
    and verifies the anti-tamper challenge.
    """
    document = ContentDataService.get_document_by_id(document_id)
    if not document:
        return HttpResponseForbidden("Document not found.")

    if not _can_access_document(request.user, document):
        return HttpResponseForbidden("Unauthorized to access document key.")

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
    expected_hash = hashlib.sha256((server_nonce + "CAMPUS_PREP_SECURE_PAYLOAD").encode()).hexdigest()
    
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
    Only accessible by staff (admins). Returns results when completed.
    """
    doc = ContentDataService.get_document_by_id_admin(document_id)
    try:
        if not doc:
            return JsonResponse({'status': 'ERROR', 'message': 'Document not found'}, status=404)
        response_data = {
            'status': doc.parsing_status,
            'completed_steps': doc.parsing_completed_chunks,
            'total_steps': doc.parsing_total_chunks,
            'recreation_completed': doc.recreation_completed_images,
            'recreation_total': doc.recreation_total_images,
        }
        
        # Include data if finished so the frontend can populate the editor
        if doc.parsing_status == 'COMPLETED':
            response_data['structured_data'] = doc.structured_data
            
        return JsonResponse(response_data)
    except Exception:
        return JsonResponse({'status': 'ERROR', 'message': 'Failed to retrieve document status'}, status=500)
