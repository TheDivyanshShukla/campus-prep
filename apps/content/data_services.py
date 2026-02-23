from django.db.models import Prefetch, Q
from apps.common.services import BaseService
from apps.academics.models import Branch, Semester, Subject
from apps.content.models import ParsedDocument
from apps.academics.data_services import AcademicsDataService
from django.utils import timezone

class ContentDataService(BaseService):
    """
    Service for retrieving content-related data with caching support.
    """
    
    @classmethod
    def get_all_branches(cls):
        return AcademicsDataService.get_all_branches()

    @classmethod
    def get_all_semesters(cls):
        return AcademicsDataService.get_all_semesters()

    @classmethod
    def get_subject_by_id(cls, subject_id):
        return AcademicsDataService.get_subject_by_id(subject_id)

    @classmethod
    def get_published_documents_for_subject(cls, subject):
        """
        Retrieves all published documents for a subject, ordered by year and creation date.
        Caching this per subject.
        """
        return cls.get_or_set_cache(
            f'subject_documents_{subject.id}',
            lambda: list(ParsedDocument.objects.filter(
                subjects=subject, 
                is_published=True
            ).prefetch_related('subjects').order_by('-year', '-created_at')),
            timeout=1800 # Cache for 30 minutes
        )

    @classmethod
    def get_document_by_id(cls, document_id):
        return cls.get_or_set_cache(
            f'document_{document_id}',
            lambda: ParsedDocument.objects.filter(pk=document_id, is_published=True).prefetch_related('subjects').first(),
            timeout=3600
        )

    @classmethod
    def get_subjects_by_branch_and_semester(cls, branch, semester):
        return AcademicsDataService.get_subjects_by_branch_and_semester(branch, semester)
