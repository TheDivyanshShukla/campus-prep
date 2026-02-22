from django.urls import path
from . import views
from .api import ParseDocumentAPI, PublishParsedDocumentAPI

urlpatterns = [
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
