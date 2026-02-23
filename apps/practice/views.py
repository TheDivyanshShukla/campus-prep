import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from apps.academics.models import Subject, Unit
from .models import Question, QuestionSet, UserAttempt, UserAnswer
from .data_services import PracticeDataService
from apps.academics.data_services import AcademicsDataService


# ── Index — subject / unit / type picker ──────────────────────────────────────
@login_required
def index(request):
    user = request.user
    # Show subjects relevant to the user's branch/semester preferences
    branch = getattr(user, 'preferred_branch', None)
    semester = getattr(user, 'preferred_semester', None)
    
    subjects = AcademicsDataService.get_subjects_by_branch_and_semester(branch, semester)
    if not subjects:
        # Fallback if no preferences
        subjects = Subject.objects.select_related('branch', 'semester').filter(is_active=True)

    # Pre-fetch unit counts and set counts per subject for display
    subject_data = []
    for subj in subjects:
        stats = PracticeDataService.get_subject_practice_stats(subj)
        subject_data.append({
            'subject': subj,
            'set_count': stats['set_count'],
            'question_count': stats['q_count'],
            'units': list(subj.units.all()),
        })

    return render(request, 'practice/index.html', {
        'subject_data': subject_data,
    })


# ── Set list for a subject (optionally filtered by unit) ──────────────────────
@login_required
def question_set_list(request, subject_id):
    subject  = AcademicsDataService.get_subject_by_id(subject_id)
    if not subject:
        return redirect('practice_index')
        
    unit_id  = request.GET.get('unit')
    unit     = None
    if unit_id:
        try:
            unit = Unit.objects.get(id=unit_id, subject=subject)
        except Unit.DoesNotExist:
            pass

    sets_qs = PracticeDataService.get_published_sets_for_subject(subject, unit)

    return render(request, 'practice/set_list.html', {
        'subject': subject,
        'unit': unit,
        'sets': sets_qs,
        'units': subject.units.all(),
    })


# ── Quiz page ─────────────────────────────────────────────────────────────────
@login_required
def quiz(request, set_id):
    question_set = PracticeDataService.get_question_set_by_id(set_id)
    if not question_set:
        return redirect('practice_index')
    questions    = list(question_set.questions.filter(is_published=True))

    # Serialize question data to JSON for JavaScript rendering
    questions_json = json.dumps([{
        'id':   q.id,
        'type': q.question_type,
        'body': q.body_md,
        'options': {
            'A': q.option_a,
            'B': q.option_b,
            'C': q.option_c,
            'D': q.option_d,
        } if q.question_type == 'MCQ' else {},
    } for q in questions])

    return render(request, 'practice/quiz.html', {
        'question_set':  question_set,
        'questions':     questions,
        'questions_json': questions_json,
        'question_count': len(questions),
    })



# ── Submit quiz ───────────────────────────────────────────────────────────────
@login_required
@require_POST
def submit_quiz(request, set_id):
    question_set = get_object_or_404(QuestionSet, id=set_id, is_published=True)
    questions    = list(question_set.questions.filter(is_published=True))

    attempt = UserAttempt.objects.create(
        user=request.user,
        question_set=question_set,
        max_score=len(questions),
    )

    score = 0
    for q in questions:
        given = request.POST.get(f'q_{q.id}', '').strip()
        correct = False

        if q.question_type in (Question.TYPE_MCQ, Question.TYPE_TF, Question.TYPE_FILL):
            # Normalise comparison
            correct = given.strip().upper() == q.correct_answer.strip().upper()
        # SHORT/LONG: we don't auto-grade — mark as submitted, show model answer
        # correct stays False; instructor can override in admin

        if correct:
            score += 1

        UserAnswer.objects.create(
            attempt=attempt,
            question=q,
            given_answer=given,
            is_correct=correct,
        )

    attempt.score      = score
    attempt.finished_at = timezone.now()
    attempt.save()

    return redirect('practice_result', attempt_id=attempt.id)


# ── Result page ───────────────────────────────────────────────────────────────
@login_required
def result(request, attempt_id):
    attempt  = get_object_or_404(UserAttempt, id=attempt_id, user=request.user)
    answers  = attempt.answers.select_related('question').order_by('question__id')

    auto_graded_types = (Question.TYPE_MCQ, Question.TYPE_TF, Question.TYPE_FILL)
    auto_graded = [a for a in answers if a.question.question_type in auto_graded_types]
    manual_review = [a for a in answers if a.question.question_type not in auto_graded_types]

    return render(request, 'practice/result.html', {
        'attempt': attempt,
        'answers': answers,
        'auto_graded': auto_graded,
        'manual_review': manual_review,
    })


# ── AI Generate endpoint ──────────────────────────────────────────────────────
@login_required
@require_POST
def ai_generate(request):
    try:
        data = json.loads(request.body)
        subject_id = data.get('subject_id')
        unit_id    = data.get('unit_id')
        types      = data.get('types', ['MCQ'])      # list of type strings
        difficulty = data.get('difficulty', 'MEDIUM')
        count      = min(int(data.get('count', 10)), 20)  # cap at 20

        subject = get_object_or_404(Subject, id=subject_id, is_active=True)
        unit    = None
        if unit_id:
            try:
                unit = Unit.objects.get(id=unit_id, subject=subject)
            except Unit.DoesNotExist:
                pass

        from .services import PracticeAIService
        service = PracticeAIService()
        generated = service.generate(
            subject_name=subject.name,
            unit_name=unit.name if unit else None,
            question_types=types,
            difficulty=difficulty,
            count=count,
        )

        # Save to DB
        saved_questions = []
        for g in generated:
            q = Question(
                subject=subject,
                unit=unit,
                question_type=g.question_type,
                difficulty=g.difficulty,
                body_md=g.body_md,
                correct_answer=g.correct_answer,
                explanation_md=g.explanation_md,
                is_ai_generated=True,
                is_published=True,
            )
            if g.question_type == Question.TYPE_MCQ and g.mcq_options:
                q.option_a = g.mcq_options.a
                q.option_b = g.mcq_options.b
                q.option_c = g.mcq_options.c
                q.option_d = g.mcq_options.d
                # Normalise correct_answer from MCQOptions.correct
                q.correct_answer = g.mcq_options.correct.upper()
            q.save()
            saved_questions.append(q)

        # Create QuestionSet
        unit_label = unit.name if unit else "All Units"
        qset = QuestionSet.objects.create(
            title=f"AI: {subject.name} — {unit_label} ({difficulty})",
            subject=subject,
            unit=unit,
            is_ai_generated=True,
            is_published=True,
        )
        qset.questions.set(saved_questions)

        return JsonResponse({'success': True, 'set_id': qset.id})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
