from apps.common.services import BaseService
from apps.practice.models import Question, QuestionSet, UserAttempt, UserAnswer
from django.db.models import Count


class PracticeDataService(BaseService):
    """
    Service for practice and quiz related data.
    """

    # ── Set / Question lookups ────────────────────────────────────────────────

    @classmethod
    def get_question_set_by_id(cls, set_id):
        return cls.get_or_set_cache(
            f'question_set_{set_id}',
            lambda: QuestionSet.objects.filter(pk=set_id, is_published=True).first(),
            timeout=3600,
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
    def get_published_questions_for_set(cls, question_set):
        return cls.get_or_set_cache(
            f'published_questions_set_{question_set.id}',
            lambda: list(question_set.questions.filter(is_published=True)),
            timeout=1800,
        )

    @classmethod
    def get_subject_practice_stats(cls, subject):
        """Question and set counts for a subject."""
        return cls.get_or_set_cache(
            f'subject_practice_stats_{subject.id}',
            lambda: {
                'set_count': QuestionSet.objects.filter(subject=subject, is_published=True).count(),
                'q_count': Question.objects.filter(subject=subject, is_published=True).count(),
            },
            timeout=3600,
        )

    # ── Attempt / Answer CRUD ─────────────────────────────────────────────────

    @classmethod
    def create_attempt(cls, user, question_set, max_score):
        return UserAttempt.objects.create(
            user=user, question_set=question_set, max_score=max_score,
        )

    @classmethod
    def bulk_create_answers(cls, answers):
        return UserAnswer.objects.bulk_create(answers)

    @classmethod
    def get_user_attempt(cls, user, attempt_id):
        return UserAttempt.objects.filter(pk=attempt_id, user=user).first()

    @classmethod
    def get_answers_for_attempt(cls, attempt):
        return list(attempt.answers.select_related('question').order_by('question__id'))

    # ── AI generation helpers ─────────────────────────────────────────────────

    @classmethod
    def bulk_create_questions(cls, questions_data):
        """Bulk-create Question instances from a list of dicts and return them."""
        objs = [Question(**data) for data in questions_data]
        return Question.objects.bulk_create(objs)

    @classmethod
    def create_question_set(cls, title, subject, unit, questions, *, is_ai=False):
        qset = QuestionSet.objects.create(
            title=title, subject=subject, unit=unit,
            is_ai_generated=is_ai, is_published=True,
        )
        qset.questions.set(questions)
        # Bust cached sets for this subject
        cls.clear_cache(f'published_sets_{subject.id}')
        if unit:
            cls.clear_cache(f'published_sets_{subject.id}_unit_{unit.id}')
        cls.clear_cache(f'subject_practice_stats_{subject.id}')
        return qset
