import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Sum, Count, Q, Avg
from .models import GamerProfile, StudySession


@login_required
def analytics_dashboard(request):
    """
    Renders the Gamification Dashboard with rich XP, Streaks, Subject breakdown,
    hourly heatmap, and complete session log charts.
    """
    profile, _ = GamerProfile.objects.get_or_create(user=request.user)
    now = timezone.now()
    today = now.date()

    # ── 1. Lifetime totals ──────────────────────────────────────────────────
    total_seconds = StudySession.objects.filter(user=request.user).aggregate(
        total=Sum('duration_seconds')
    )['total'] or 0
    total_hours = round(total_seconds / 3600, 1)
    total_sessions = StudySession.objects.filter(user=request.user).count()

    # ── 2. Weekly bar chart – last 7 days (minutes per day) ──────────────────
    weekly_labels = []
    weekly_minutes = []
    weekly_xp = []

    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        qs = StudySession.objects.filter(user=request.user, start_time__date=target_date)
        day_seconds = qs.aggregate(total=Sum('duration_seconds'))['total'] or 0
        weekly_labels.append(target_date.strftime('%a %d'))
        weekly_minutes.append(round(day_seconds / 60))
        weekly_xp.append(round(day_seconds / 60))  # 1 XP ≈ 1 min

    today_minutes = weekly_minutes[-1]

    # ── 3. Monthly heatmap – contribution-style (last 30 days) ───────────────
    heatmap_data = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        secs = StudySession.objects.filter(
            user=request.user, start_time__date=d
        ).aggregate(total=Sum('duration_seconds'))['total'] or 0
        heatmap_data.append({
            'date': d.strftime('%b %d'),
            'minutes': round(secs / 60),
        })

    # ── 4. Subject donut chart (all-time) ────────────────────────────────────
    subject_data = (
        StudySession.objects
        .filter(user=request.user, subject__isnull=False)
        .values('subject__name', 'subject__code')
        .annotate(total_seconds=Sum('duration_seconds'))
        .order_by('-total_seconds')[:8]
    )
    subject_labels = [row['subject__name'] for row in subject_data]
    subject_minutes = [round(row['total_seconds'] / 60) for row in subject_data]

    # Sessions with no subject
    no_subject_secs = StudySession.objects.filter(
        user=request.user, subject__isnull=True
    ).aggregate(total=Sum('duration_seconds'))['total'] or 0
    if no_subject_secs:
        subject_labels.append('Uncategorised')
        subject_minutes.append(round(no_subject_secs / 60))

    # ── 5. Hourly heatmap (24h distribution – all-time) ──────────────────────
    hourly_data = [0] * 24
    sessions_all = StudySession.objects.filter(user=request.user).values('start_time', 'duration_seconds')
    for s in sessions_all:
        hour = timezone.localtime(s['start_time']).hour
        hourly_data[hour] += round(s['duration_seconds'] / 60)

    # ── 6. 12-week trend (line chart) ─────────────────────────────────────────
    trend_labels = []
    trend_minutes = []
    for w in range(11, -1, -1):
        week_start = today - timedelta(days=today.weekday() + w * 7)
        week_end = week_start + timedelta(days=6)
        secs = StudySession.objects.filter(
            user=request.user,
            start_time__date__gte=week_start,
            start_time__date__lte=week_end,
        ).aggregate(total=Sum('duration_seconds'))['total'] or 0
        trend_labels.append(week_start.strftime('W%W'))
        trend_minutes.append(round(secs / 60))

    # ── 7. Full session log (last 50) ─────────────────────────────────────────
    recent_sessions = (
        StudySession.objects
        .filter(user=request.user)
        .select_related('subject', 'parsed_document')
        .order_by('-start_time')[:50]
    )
    session_log = []
    for s in recent_sessions:
        duration_min = round(s.duration_seconds / 60)
        hours, mins = divmod(duration_min, 60)
        duration_str = f"{hours}h {mins}m" if hours else f"{mins}m"
        session_log.append({
            'date': timezone.localtime(s.start_time).strftime('%d %b %Y'),
            'time': timezone.localtime(s.start_time).strftime('%I:%M %p'),
            'subject': s.subject.name if s.subject else '—',
            'subject_code': s.subject.code if s.subject else '',
            'document': s.parsed_document.title if s.parsed_document else '—',
            'duration': duration_str,
            'duration_min': duration_min,
            'xp_earned': max(1, duration_min),
        })

    # ── 10. Practice Stats ────────────────────────────────────────────────────
    from apps.practice.models import UserAttempt, UserAnswer
    
    practice_attempts = UserAttempt.objects.filter(user=request.user).order_by('-started_at')
    total_practice_qs = UserAnswer.objects.filter(attempt__user=request.user).count()
    
    avg_accuracy = 0
    if practice_attempts.exists():
        # Calculate as (Total Score / Total Max Score)
        Totals = practice_attempts.aggregate(s=Sum('score'), m=Sum('max_score'))
        if Totals['m'] and Totals['m'] > 0:
            avg_accuracy = (Totals['s'] / Totals['m']) * 100
    
    # Practice by Subject
    practice_subject_raw = (
        UserAttempt.objects.filter(user=request.user)
        .values('question_set__subject__name')
        .annotate(
            count=Count('id'),
            sum_score=Sum('score'),
            sum_max=Sum('max_score')
        )
        .order_by('-count')[:5]
    )
    practice_subject_labels = [row['question_set__subject__name'] for row in practice_subject_raw]
    practice_subject_scores = []
    for row in practice_subject_raw:
        if row['sum_max'] > 0:
            practice_subject_scores.append(round((row['sum_score'] / row['sum_max']) * 100))
        else:
            practice_subject_scores.append(0)

    # Weekly Practice (Qs per day - last 7 days)
    practice_weekly_labels = []
    practice_weekly_qs = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        qs_count = UserAnswer.objects.filter(attempt__user=request.user, attempt__started_at__date=d).count()
        practice_weekly_labels.append(d.strftime('%a %d'))
        practice_weekly_qs.append(qs_count)

    # 12-Week Accuracy Trend
    practice_trend_labels = []
    practice_trend_scores = []
    for w in range(11, -1, -1):
        week_start = today - timedelta(days=today.weekday() + w * 7)
        week_end = week_start + timedelta(days=6)
        atts = UserAttempt.objects.filter(
            user=request.user,
            started_at__date__gte=week_start,
            started_at__date__lte=week_end,
        )
        practice_trend_labels.append(week_start.strftime('W%W'))
        
        t = atts.aggregate(s=Sum('score'), m=Sum('max_score'))
        if t['m'] and t['m'] > 0:
            practice_trend_scores.append(round((t['s'] / t['m']) * 100))
        else:
            practice_trend_scores.append(0)

    # Hourly Practice Pattern
    practice_hourly_data = [0] * 24
    practice_ans_all = UserAnswer.objects.filter(attempt__user=request.user).values('attempt__started_at')
    for a in practice_ans_all:
        hour = timezone.localtime(a['attempt__started_at']).hour
        practice_hourly_data[hour] += 1

    # 30-Day Practice Heatmap
    practice_heatmap_data = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        qs_count = UserAnswer.objects.filter(attempt__user=request.user, attempt__started_at__date=d).count()
        practice_heatmap_data.append({
            'date': d.strftime('%b %d'),
            'qs': qs_count,
        })

    practice_history = []
    for att in practice_attempts[:20]:
        practice_history.append({
            'date': timezone.localtime(att.started_at).strftime('%d %b'),
            'subject': att.question_set.subject.name,
            'subject_code': att.question_set.subject.code,
            'title': att.question_set.title,
            'score': f"{att.score}/{att.max_score}",
            'accuracy': att.percentage,
        })

    # ── 8. Daily progress ─────────────────────────────────────────────────────
    daily_progress = min(100, int((today_minutes / max(1, profile.daily_xp_goal)) * 100))

    # ── 9. XP level tier ─────────────────────────────────────────────────────
    lvl_info = profile.get_level_info()
    level = lvl_info['level']
    level_name = lvl_info['name']
    next_level = lvl_info['next_xp']
    xp_level_pct = min(100, int((profile.total_xp / max(1, next_level)) * 100))

    context = {
        'profile': profile,
        'total_hours': total_hours,
        'total_sessions': total_sessions,
        'today_minutes': today_minutes,
        'daily_progress': daily_progress,

        # Charts (Study)
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_minutes': json.dumps(weekly_minutes),
        'heatmap_data': json.dumps(heatmap_data),
        'subject_labels': json.dumps(subject_labels),
        'subject_minutes': json.dumps(subject_minutes),
        'hourly_data': json.dumps(hourly_data),
        'trend_labels': json.dumps(trend_labels),
        'trend_minutes': json.dumps(trend_minutes),

        # Practice Data
        'total_practice_qs': total_practice_qs,
        'avg_accuracy': round(avg_accuracy),
        'practice_subject_labels': json.dumps(practice_subject_labels),
        'practice_subject_scores': json.dumps(practice_subject_scores),
        'practice_weekly_labels': json.dumps(practice_weekly_labels),
        'practice_weekly_qs': json.dumps(practice_weekly_qs),
        'practice_trend_labels': json.dumps(practice_trend_labels),
        'practice_trend_scores': json.dumps(practice_trend_scores),
        'practice_hourly_data': json.dumps(practice_hourly_data),
        'practice_heatmap_data': json.dumps(practice_heatmap_data),
        'practice_history': practice_history,

        # Session log (Study)
        'session_log': session_log,

        # Level
        'level': level,
        'level_name': level_name,
        'next_level': next_level,
        'xp_level_pct': xp_level_pct,
    }

    return render(request, 'gamification/user_analytics.html', context)
