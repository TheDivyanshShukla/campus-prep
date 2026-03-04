from apps.common.services import BaseService
from apps.academics.models import Branch, Semester, Subject, Unit, ExamDate


class AcademicsDataService(BaseService):
    """
    Service for retrieving academic data with caching support.
    """

    @classmethod
    def get_all_branches(cls):
        return cls.get_or_set_cache(
            'all_branches',
            lambda: list(Branch.objects.filter(is_active=True)),
            timeout=86400,
        )

    @classmethod
    def get_all_semesters(cls):
        return cls.get_or_set_cache(
            'all_semesters',
            lambda: list(Semester.objects.filter(is_active=True)),
            timeout=86400,
        )

    @classmethod
    def get_branch_by_id(cls, branch_id):
        return cls.get_or_set_cache(
            f'branch_{branch_id}',
            lambda: Branch.objects.filter(pk=branch_id, is_active=True).first(),
            timeout=86400,
        )

    @classmethod
    def get_semester_by_id(cls, semester_id):
        return cls.get_or_set_cache(
            f'semester_{semester_id}',
            lambda: Semester.objects.filter(pk=semester_id, is_active=True).first(),
            timeout=86400,
        )

    @classmethod
    def get_subject_by_id(cls, subject_id):
        return cls.get_or_set_cache(
            f'subject_{subject_id}',
            lambda: Subject.objects.select_related('branch', 'semester')
            .prefetch_related('units')
            .filter(pk=subject_id)
            .first(),
            timeout=3600,
        )

    @classmethod
    def get_all_active_subjects(cls):
        return cls.get_or_set_cache(
            'all_active_subjects',
            lambda: list(
                Subject.objects.select_related('branch', 'semester')
                .filter(is_active=True)
                .order_by('code')
            ),
            timeout=3600,
        )

    @classmethod
    def get_subjects_by_branch_and_semester(cls, branch, semester):
        if not branch or not semester:
            return []
        return cls.get_or_set_cache(
            f'subjects_{branch.id}_{semester.id}',
            lambda: list(
                Subject.objects.filter(
                    branch=branch, semester=semester, is_active=True
                ).order_by('code')
            ),
            timeout=3600,
        )

    @classmethod
    def get_unit_by_id(cls, unit_id, subject=None):
        cache_key = f'unit_{unit_id}'
        if subject:
            cache_key += f'_subj_{subject.id}'

        def _fetch():
            qs = Unit.objects.select_related('subject')
            if subject:
                qs = qs.filter(pk=unit_id, subject=subject)
            else:
                qs = qs.filter(pk=unit_id)
            return qs.first()

        return cls.get_or_set_cache(cache_key, _fetch, timeout=3600)

    @classmethod
    def get_units_for_subject(cls, subject):
        return cls.get_or_set_cache(
            f'units_for_subject_{subject.id}',
            lambda: list(subject.units.all().order_by('number')),
            timeout=3600,
        )

    @classmethod
    def get_exam_date(cls, branch, semester):
        return cls.get_or_set_cache(
            f'exam_date_{branch.id}_{semester.id}',
            lambda: ExamDate.objects.filter(branch=branch, semester=semester).first(),
            timeout=86400,
        )
