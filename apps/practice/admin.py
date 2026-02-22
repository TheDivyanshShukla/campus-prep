from django.contrib import admin
from .models import Question, QuestionSet, UserAttempt, UserAnswer


class UserAnswerInline(admin.TabularInline):
    model = UserAnswer
    extra = 0
    readonly_fields = ('question', 'given_answer', 'is_correct')
    can_delete = False


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display  = ('__str__', 'subject', 'unit', 'question_type', 'difficulty', 'is_ai_generated', 'is_published')
    list_filter   = ('question_type', 'difficulty', 'is_ai_generated', 'is_published', 'subject')
    search_fields = ('body_md', 'subject__name', 'unit__name')
    list_editable = ('is_published',)
    fieldsets = (
        ('Question', {
            'fields': ('subject', 'unit', 'question_type', 'difficulty', 'body_md')
        }),
        ('MCQ Options', {
            'classes': ('collapse',),
            'fields': ('option_a', 'option_b', 'option_c', 'option_d'),
        }),
        ('Answer & Explanation', {
            'fields': ('correct_answer', 'explanation_md')
        }),
        ('Meta', {
            'fields': ('is_ai_generated', 'is_published')
        }),
    )


@admin.register(QuestionSet)
class QuestionSetAdmin(admin.ModelAdmin):
    list_display  = ('title', 'subject', 'unit', 'question_count', 'is_ai_generated', 'is_published', 'created_at')
    list_filter   = ('is_ai_generated', 'is_published', 'subject')
    search_fields = ('title', 'subject__name')
    filter_horizontal = ('questions',)


@admin.register(UserAttempt)
class UserAttemptAdmin(admin.ModelAdmin):
    list_display  = ('user', 'question_set', 'score', 'max_score', 'percentage', 'started_at')
    list_filter   = ('question_set__subject',)
    search_fields = ('user__username',)
    readonly_fields = ('started_at', 'finished_at', 'score', 'max_score')
    inlines = [UserAnswerInline]
