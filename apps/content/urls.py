from django.urls import path
from . import views
from .api import ParseDocumentAPI, PublishParsedDocumentAPI

urlpatterns = [
    # Public SEO layer
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.seo_sitemap_xml, name='seo_sitemap_xml'),
    path('rgpv/', views.rgpv_root, name='rgpv_root'),
    path('rgpv/branches/', views.rgpv_branches_page, name='rgpv_branches'),
    path('rgpv/semesters/', views.rgpv_semesters_page, name='rgpv_semesters'),
    path('rgpv/subjects/', views.rgpv_subjects_page, name='rgpv_subjects'),
    path('rgpv/<slug:branch_slug>/', views.rgpv_branch_page, name='rgpv_branch'),
    path('rgpv/<slug:branch_slug>/<slug:semester_slug>/', views.rgpv_semester_page, name='rgpv_semester'),
    path('rgpv/<slug:branch_slug>/<slug:semester_slug>/<slug:subject_slug>/', views.rgpv_subject_page, name='rgpv_subject'),
    path('rgpv/<slug:branch_slug>/<slug:semester_slug>/<slug:subject_slug>/<slug:resource_slug>/', views.rgpv_subject_resource_page, name='rgpv_subject_resource'),
    path('rgpv/<slug:branch_slug>/<slug:semester_slug>/<slug:subject_slug>/<slug:resource_slug>/<slug:slug>/', views.read_document_from_seo, name='rgpv_seo_document'),
    path('rgpv/<slug:branch_slug>/<slug:semester_slug>/<slug:subject_slug>/<slug:resource_slug>/read/<slug:slug>/', views.read_document_from_seo_legacy_slug, name='rgpv_seo_read_document_legacy_slug'),
    path('rgpv/<slug:branch_slug>/<slug:semester_slug>/<slug:subject_slug>/<slug:resource_slug>/read/<int:document_id>/<slug:slug>/', views.read_document_from_seo_legacy, name='rgpv_seo_read_document_legacy'),

    path('rgpv-notes/', views.rgpv_static_page, {'page_slug': 'rgpv-notes'}, name='rgpv_notes'),
    path('rgpv-syllabus/', views.rgpv_static_page, {'page_slug': 'rgpv-syllabus'}, name='rgpv_syllabus'),
    path('rgpv-question-papers/', views.rgpv_static_page, {'page_slug': 'rgpv-question-papers'}, name='rgpv_question_papers'),
    path('rgpv-important-questions/', views.rgpv_static_page, {'page_slug': 'rgpv-important-questions'}, name='rgpv_important_questions'),
    path('rgpv-results/', views.rgpv_static_page, {'page_slug': 'rgpv-results'}, name='rgpv_results'),
    path('rgpv-exam-time-table/', views.rgpv_static_page, {'page_slug': 'rgpv-exam-time-table'}, name='rgpv_exam_time_table'),
    path('rgpv-backlog-rules/', views.rgpv_static_page, {'page_slug': 'rgpv-backlog-rules'}, name='rgpv_backlog_rules'),
    path('rgpv-grading-system/', views.rgpv_static_page, {'page_slug': 'rgpv-grading-system'}, name='rgpv_grading_system'),

    path('rgpv-most-asked-questions/', views.rgpv_static_page, {'page_slug': 'rgpv-most-asked-questions'}, name='rgpv_most_asked_questions'),
    path('rgpv-pass-in-one-night-guide/', views.rgpv_static_page, {'page_slug': 'rgpv-pass-in-one-night-guide'}, name='rgpv_pass_one_night'),
    path('rgpv-exam-tips/', views.rgpv_static_page, {'page_slug': 'rgpv-exam-tips'}, name='rgpv_exam_tips'),

    path('rgpv-result/', views.rgpv_static_page, {'page_slug': 'rgpv-result'}, name='rgpv_result'),
    path('rgpv-result-date/', views.rgpv_static_page, {'page_slug': 'rgpv-result-date'}, name='rgpv_result_date'),
    path('rgpv-exam-form-last-date/', views.rgpv_static_page, {'page_slug': 'rgpv-exam-form-last-date'}, name='rgpv_exam_form_last_date'),
    path('rgpv-time-table/', views.rgpv_static_page, {'page_slug': 'rgpv-time-table'}, name='rgpv_time_table'),
    path('rgpv-revaluation-process/', views.rgpv_static_page, {'page_slug': 'rgpv-revaluation-process'}, name='rgpv_revaluation_process'),

    path('rgpv-passing-marks/', views.rgpv_static_page, {'page_slug': 'rgpv-passing-marks'}, name='rgpv_passing_marks'),
    path('rgpv-grace-marks/', views.rgpv_static_page, {'page_slug': 'rgpv-grace-marks'}, name='rgpv_grace_marks'),
    path('rgpv-cgpa-calculation/', views.rgpv_static_page, {'page_slug': 'rgpv-cgpa-calculation'}, name='rgpv_cgpa_calculation'),

    # Public & Student Pages
    path('', views.home, name='home'),
    path('explore/', views.explore_subjects, name='explore_subjects'),
    path('subject/<int:subject_id>/', views.subject_dashboard, name='subject_dashboard'),
    path('read/<int:document_id>/', views.read_document, name='read_document'),
    path('read/<int:document_id>/<path:slug>', views.read_document, name='read_document_slug'),

    # Admin UI
    path('admin/ai-parser/', views.admin_ai_parser, name='admin_ai_parser'),
    
    # AI API Endpoints
    path('api/parse-document/', ParseDocumentAPI.as_view(), name='api_parse_document'),
    path('api/publish-document/', PublishParsedDocumentAPI.as_view(), name='api_publish_document'),
    path('api/document/<int:document_id>/key/', views.get_document_key, name='api_document_key'),
    path('api/document/<int:document_id>/pdf/', views.serve_secure_pdf, name='api_secure_pdf'),
    path('api/document/<int:document_id>/parsing-status/', views.get_parsing_status, name='get_parsing_status'),
]
