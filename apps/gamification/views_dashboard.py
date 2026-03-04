import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .data_services import GamificationDataService


@login_required
def analytics_dashboard(request):
    """
    Renders the Gamification Dashboard with rich XP, Streaks, Subject breakdown,
    hourly heatmap, and complete session log charts.
    All data flows through GamificationDataService (cached).
    """
    user = request.user
    profile = GamificationDataService.get_user_profile(user)
    analytics = GamificationDataService.get_dashboard_analytics(user)

    # ── 1. Lifetime totals ────────────────────────────────────────────────────
    total_seconds = analytics.get('total_seconds', 0)
    total_hours = round(total_seconds / 3600, 1)
    total_sessions = analytics.get('total_sessions', 0)

    # ── 2. Weekly bar chart ───────────────────────────────────────────────────
    weekly_labels = analytics.get('weekly_labels', [])
    weekly_minutes = analytics.get('weekly_minutes', [])
    today_minutes = weekly_minutes[-1] if weekly_minutes else 0

    # ── 3. Monthly heatmap ────────────────────────────────────────────────────
    heatmap_data = GamificationDataService.get_monthly_heatmap(user)

    # ── 4. Subject donut chart ────────────────────────────────────────────────
    subject_labels = analytics.get('subject_labels', [])
    subject_minutes = analytics.get('subject_minutes', [])

    # ── 5. Hourly heatmap ─────────────────────────────────────────────────────
    hourly_data = GamificationDataService.get_hourly_heatmap(user)

    # ── 6. 12-week trend ──────────────────────────────────────────────────────
    trend = GamificationDataService.get_weekly_trend(user)
    trend_labels = trend['labels']
    trend_minutes = trend['minutes']

    # ── 7. Session log ────────────────────────────────────────────────────────
    session_log = GamificationDataService.get_recent_sessions(user, limit=50)

    # ── 8. Practice stats ─────────────────────────────────────────────────────
    ps = GamificationDataService.get_practice_stats(user)

    # ── 9. Daily progress ─────────────────────────────────────────────────────
    daily_progress = min(100, int((today_minutes / max(1, profile.daily_xp_goal)) * 100))

    # ── 10. XP level tier ─────────────────────────────────────────────────────
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
        'total_practice_qs': ps['total_qs'],
        'avg_accuracy': ps['avg_accuracy'],
        'practice_subject_labels': json.dumps(ps['subject_labels']),
        'practice_subject_scores': json.dumps(ps['subject_scores']),
        'practice_weekly_labels': json.dumps(ps['weekly_labels']),
        'practice_weekly_qs': json.dumps(ps['weekly_qs']),
        'practice_trend_labels': json.dumps(ps['trend_labels']),
        'practice_trend_scores': json.dumps(ps['trend_scores']),
        'practice_hourly_data': json.dumps(ps['hourly_data']),
        'practice_heatmap_data': json.dumps(ps['heatmap']),
        'practice_history': ps['history'],

        # Session log (Study)
        'session_log': session_log,

        # Level
        'level': level,
        'level_name': level_name,
        'next_level': next_level,
        'xp_level_pct': xp_level_pct,
    }

    return render(request, 'gamification/user_analytics.html', context)
