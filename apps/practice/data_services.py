from apps.common.services import BaseService
from apps.practice.models import Question, QuestionSet, UserAttempt
from django.db.models import Count

class PracticeDataService(BaseService):
    """
    Service for practice and quiz related data.
    """
    
    @classmethod
    def get_question_set_by_id(cls, set_id):
        return cls.get_or_set_cache(
            f'question_set_{set_id}',
            lambda: QuestionSet.objects.filter(pk=set_id, is_published=True).first(),
            timeout=3600
        )

    @classmethod
    def get_published_sets_for_subject(cls, subject, unit=None):
        cache_key = f'published_sets_{subject.id}'
        if unit:
            cache_key += f'_unit_{unit.id}'
            
        def fetch_sets():
            qs = QuestionSet.objects.filter(subject=subject, is_published=True).prefetch_related('questions')
            if unit:
                qs = qs.filter(unit=unit)
            return list(qs)
            
        return cls.get_or_set_cache(cache_key, fetch_sets, timeout=1800)

    @classmethod
    def get_subject_practice_stats(cls, subject):
        """
        Retrieves question and set counts for a subject.
        """
        return cls.get_or_set_cache(
            f'subject_practice_stats_{subject.id}',
            lambda: {
                'set_count': QuestionSet.objects.filter(subject=subject, is_published=True).count(),
                'q_count': Question.objects.filter(subject=subject, is_published=True).count()
            },
            timeout=3600
        )
