from django.db import models
from apps.common.services import BaseService
from apps.content.models import ParsedDocument
from apps.academics.models import Subject
from apps.academics.data_services import AcademicsDataService


class ContentDataService(BaseService):
    """
    Service for retrieving content-related data with caching support.
    Delegates academic lookups to AcademicsDataService.
    """

    # Convenience aliases — prefer calling AcademicsDataService directly
    get_all_branches = AcademicsDataService.get_all_branches
    get_all_semesters = AcademicsDataService.get_all_semesters
    get_subject_by_id = AcademicsDataService.get_subject_by_id
    get_subjects_by_branch_and_semester = AcademicsDataService.get_subjects_by_branch_and_semester

    @classmethod
    def get_published_documents_for_subject(cls, subject):
        """
        Retrieves all published documents for a subject, ordered by year and creation date.
        """
        return cls.get_or_set_cache(
            f'subject_documents_{subject.id}',
            lambda: list(
                ParsedDocument.objects.filter(subjects=subject, is_published=True)
                .exclude(parsing_status__in=['PROCESSING', 'FAILED'])
                .prefetch_related(
                    models.Prefetch(
                        'subjects',
                        queryset=Subject.objects.select_related('branch', 'semester')
                    )
                )
                .order_by('-year', '-created_at')
            ),
            timeout=1800,
        )

    @classmethod
    def get_published_documents_by_type(cls, subject, document_type):
        """
        Retrieves all published documents of a specific type for a subject.
        """
        return cls.get_or_set_cache(
            f'subject_docs_type_{subject.id}_{document_type}',
            lambda: list(
                ParsedDocument.objects.filter(
                    subjects=subject, 
                    document_type=document_type,
                    is_published=True
                )
                .exclude(parsing_status__in=['PROCESSING', 'FAILED'])
                .prefetch_related(
                    models.Prefetch(
                        'subjects',
                        queryset=Subject.objects.select_related('branch', 'semester')
                    )
                )
                .order_by('-year', '-created_at')
            ),
            timeout=1800,
        )

    @classmethod
    def get_document_by_id(cls, document_id):
        return cls.get_or_set_cache(
            f'document_{document_id}',
            lambda: ParsedDocument.objects.filter(pk=document_id, is_published=True)
            .prefetch_related(
                models.Prefetch(
                    'subjects',
                    queryset=Subject.objects.select_related('branch', 'semester')
                )
            )
            .first(),
            timeout=3600,
        )

    @classmethod
    def get_document_by_id_admin(cls, document_id):
        """Staff-only lookup without is_published filter."""
        return ParsedDocument.objects.filter(pk=document_id).first()

    @classmethod
    def get_syllabus_for_subject(cls, subject):
        """Returns the completed SYLLABUS document for a subject, if any."""
        return cls.get_or_set_cache(
            f'syllabus_for_subject_{subject.id}',
            lambda: ParsedDocument.objects.filter(
                subjects=subject,
                document_type='SYLLABUS',
                parsing_status='COMPLETED',
            ).first(),
            timeout=3600,
        )
