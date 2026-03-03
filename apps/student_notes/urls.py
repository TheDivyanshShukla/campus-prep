from django.urls import path
from . import views

app_name = 'student_notes'

urlpatterns = [
    # Pages
    path('', views.index, name='index'),
    path('subject/<int:subject_id>/', views.subject_notes, name='subject_notes'),
    path('editor/<int:subject_id>/<int:unit_id>/', views.editor, name='editor'),

    # API
    path('api/save/', views.api_save, name='api_save'),
    path('api/versions/<int:note_id>/', views.api_versions, name='api_versions'),
    path('api/version/<int:version_id>/', views.api_version_detail, name='api_version_detail'),
    path('api/restore/<int:version_id>/', views.api_restore_version, name='api_restore_version'),
    path('api/copy-base/', views.api_copy_base_note, name='api_copy_base_note'),
    path('api/upload-image/', views.api_upload_image, name='api_upload_image'),
]
