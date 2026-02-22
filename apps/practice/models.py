from django.db import models
from django.conf import settings
from apps.academics.models import Subject, Unit


class Question(models.Model):
    TYPE_MCQ   = 'MCQ'
    TYPE_SHORT = 'SHORT'
    TYPE_LONG  = 'LONG'
    TYPE_FILL  = 'FILL'
    TYPE_TF    = 'TF'
    QUESTION_TYPES = [
        (TYPE_MCQ,   'Multiple Choice (MCQ)'),
        (TYPE_SHORT, 'Short Answer'),
        (TYPE_LONG,  'Long Answer'),
        (TYPE_FILL,  'Fill in the Blank'),
        (TYPE_TF,    'True / False'),
    ]

    DIFF_EASY   = 'EASY'
    DIFF_MEDIUM = 'MEDIUM'
    DIFF_HARD   = 'HARD'
    DIFFICULTIES = [
        (DIFF_EASY,   'Easy'),
        (DIFF_MEDIUM, 'Medium'),
        (DIFF_HARD,   'Hard'),
    ]

    subject  = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='practice_questions')
    unit     = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='practice_questions',
                                 help_text="Leave blank = whole subject")

    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES, default=TYPE_MCQ)
    difficulty    = models.CharField(max_length=10, choices=DIFFICULTIES, default=DIFF_MEDIUM)

    # Body — Markdown + LaTeX (rendered client-side via MathJax + markdown-it)
    body_md = models.TextField(help_text="Question text in Markdown. Use $...$ for inline LaTeX, $$...$$ for block.")

    # MCQ options (only used when question_type == MCQ)
    option_a = models.TextField(blank=True)
    option_b = models.TextField(blank=True)
    option_c = models.TextField(blank=True)
    option_d = models.TextField(blank=True)

    # For TF: store 'True' or 'False'. For FILL: store the expected word/phrase.
    # For MCQ: store 'A', 'B', 'C', or 'D'.
    # For SHORT/LONG: store a model answer for display after attempt.
    correct_answer = models.TextField(
        help_text="MCQ: A/B/C/D | TF: True/False | FILL: exact phrase | SHORT/LONG: model answer (Markdown)"
    )

    explanation_md = models.TextField(
        blank=True,
        help_text="Step-by-step explanation shown after attempt. Markdown + LaTeX."
    )

    is_ai_generated = models.BooleanField(default=False)
    is_published    = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['subject', 'unit', 'difficulty', 'question_type']

    def __str__(self):
        preview = self.body_md[:60].replace('\n', ' ')
        return f"[{self.get_question_type_display()}] {preview}…"


class QuestionSet(models.Model):
    title     = models.CharField(max_length=255)
    subject   = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='question_sets')
    unit      = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name='question_sets')
    questions = models.ManyToManyField(Question, related_name='sets', blank=True)

    is_ai_generated = models.BooleanField(default=False)
    is_published    = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        unit_str = f" — {self.unit.name}" if self.unit else " — All Units"
        return f"{self.title} ({self.subject.code}{unit_str})"

    def question_count(self):
        return self.questions.count()


class UserAttempt(models.Model):
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='practice_attempts')
    question_set = models.ForeignKey(QuestionSet, on_delete=models.CASCADE, related_name='attempts')

    started_at  = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    score     = models.PositiveIntegerField(default=0)
    max_score = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} — {self.question_set.title} ({self.score}/{self.max_score})"

    @property
    def percentage(self):
        if self.max_score == 0:
            return 0
        return round((self.score / self.max_score) * 100)


class UserAnswer(models.Model):
    attempt      = models.ForeignKey(UserAttempt, on_delete=models.CASCADE, related_name='answers')
    question     = models.ForeignKey(Question, on_delete=models.CASCADE)
    given_answer = models.TextField(blank=True)  # What the user typed/selected
    is_correct   = models.BooleanField(default=False)

    class Meta:
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f"{'✓' if self.is_correct else '✗'} {self.question}"
