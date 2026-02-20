import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.academics.models import Subject
from apps.content.models import ParsedDocument

print('--- All Engineering Physics Subjects ---')
subjects = Subject.objects.filter(name__icontains='Engineering Physics')
for s in subjects:
    print(f'ID: {s.id}, Branch: {s.branch.code}, Sem: {s.semester.number}')

print('\n--- Attached Documents ---')
docs = ParsedDocument.objects.filter(subject__name__icontains='Engineering Physics')
for d in docs:
    print(f'Doc: "{d.title}", Type: {d.document_type}, Subj_ID: {d.subject_id}, Pub: {d.is_published}')
