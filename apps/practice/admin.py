from django.contrib import admin
from .models import Question, QuestionSet, UserAttempt, UserAnswer


class UserAnswerInline(admin.TabularInline):
    model = UserAnswer
    extra = 0
    readonly_fields = ('question', 'given_answer', 'is_correct')
    can_delete = False
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('question')


from django.db.models import Count

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display  = ('__str__', 'subject', 'unit', 'question_type', 'difficulty', 'is_ai_generated', 'is_published')
    list_filter   = ('question_type', 'difficulty', 'is_ai_generated', 'is_published', 'subject')
    search_fields = ('body_md', 'subject__name', 'unit__name')
    list_editable = ('is_published',)
    list_select_related = ('subject', 'unit')
    autocomplete_fields = ['subject', 'unit']
    list_per_page = 20
    
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
    list_select_related = ('subject', 'unit')
    autocomplete_fields = ['subject', 'unit']
    list_per_page = 20

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(questions_count=Count('questions'))

    def question_count(self, obj):
        return obj.questions_count
    question_count.admin_order_field = 'questions_count'


@admin.register(UserAttempt)
class UserAttemptAdmin(admin.ModelAdmin):
    list_display  = ('user', 'question_set', 'score', 'max_score', 'percentage', 'started_at')
    list_filter   = ('question_set__subject',)
    search_fields = ('user__username', 'question_set__title')
    readonly_fields = ('started_at', 'finished_at', 'score', 'max_score')
    inlines = [UserAnswerInline]
    list_select_related = ('user', 'question_set')
    autocomplete_fields = ['user', 'question_set']
    list_per_page = 20
    show_full_result_count = False
