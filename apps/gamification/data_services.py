from apps.common.services import BaseService
from apps.gamification.models import GamerProfile, StudySession
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, TruncHour, TruncWeek
from django.utils import timezone
from datetime import timedelta


class GamificationDataService(BaseService):
    """
    Service for gamification analytics and profile data.
    """

    STREAK_THRESHOLD_SECONDS = 300  # 5 minutes to count a day

    # ── Profile ───────────────────────────────────────────────────────────────

    @classmethod
    def get_user_profile(cls, user):
        if not user.is_authenticated:
            return None
        return cls.get_or_set_cache(
            f'gamer_profile_{user.id}',
            lambda: GamerProfile.objects.get_or_create(user=user)[0],
            timeout=3600,
        )

    @classmethod
    def invalidate_profile_cache(cls, user):
        cls.clear_cache(f'gamer_profile_{user.id}')

    # ── Session helpers ───────────────────────────────────────────────────────

    @classmethod
    def get_or_create_today_session(cls, user, document, subject):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return StudySession.objects.get_or_create(
            user=user,
            parsed_document=document,
            subject=subject,
            start_time__gte=today_start,
            defaults={'start_time': now, 'last_ping_time': now},
        )

    @classmethod
    def record_heartbeat(cls, session, active_seconds):
        increment = min(active_seconds, 120)
        session.duration_seconds += increment
        session.last_ping_time = timezone.now()
        session.save(update_fields=['duration_seconds', 'last_ping_time'])
        return increment

    @classmethod
    def get_today_total_seconds(cls, user):
        today = timezone.now().date()
        return (
            StudySession.objects.filter(user=user, start_time__date=today)
            .aggregate(total=Sum('duration_seconds'))['total']
            or 0
        )

    # ── Streak logic ──────────────────────────────────────────────────────────

    @classmethod
    def evaluate_streak(cls, profile):
        today = timezone.now().date()
        if profile.last_active_date == today:
            return False
        today_total = cls.get_today_total_seconds(profile.user)
        if today_total < cls.STREAK_THRESHOLD_SECONDS:
            return False
        yesterday = today - timedelta(days=1)
        if profile.last_active_date == yesterday:
            profile.current_streak += 1
        else:
            profile.current_streak = 1
        if profile.current_streak > profile.longest_streak:
            profile.longest_streak = profile.current_streak
        profile.last_active_date = today
        profile.save(update_fields=['current_streak', 'longest_streak', 'last_active_date'])
        cls.invalidate_profile_cache(profile.user)
        return True

    # ── Dashboard analytics (heavy, cached 10 min) ───────────────────────────

    @classmethod
    def get_dashboard_analytics(cls, user):
        if not user.is_authenticated:
            return {}

        def calculate_analytics():
            now = timezone.now()
            today = now.date()
            stats = StudySession.objects.filter(user=user).aggregate(
                total_seconds=Sum('duration_seconds'),
                total_sessions=Count('id'),
            )
            total_seconds = stats['total_seconds'] or 0
            total_sessions = stats['total_sessions'] or 0
            weekly_labels, weekly_minutes = [], []
            for i in range(6, -1, -1):
                target_date = today - timedelta(days=i)
                day_seconds = (
                    StudySession.objects.filter(user=user, start_time__date=target_date)
                    .aggregate(total=Sum('duration_seconds'))['total']
                    or 0
                )
                weekly_labels.append(target_date.strftime('%a %d'))
                weekly_minutes.append(round(day_seconds / 60))
            subject_data = (
                StudySession.objects.filter(user=user, subject__isnull=False)
                .values('subject__name', 'subject__code')
                .annotate(total_seconds=Sum('duration_seconds'))
                .order_by('-total_seconds')[:8]
            )
            return {
                'total_seconds': total_seconds,
                'total_sessions': total_sessions,
                'weekly_labels': weekly_labels,
                'weekly_minutes': weekly_minutes,
                'subject_labels': [row['subject__name'] for row in subject_data],
                'subject_minutes': [round(row['total_seconds'] / 60) for row in subject_data],
                'timestamp': now.isoformat(),
            }

        return cls.get_or_set_cache(f'user_analytics_{user.id}', calculate_analytics, timeout=600)

    # ── Chart-specific aggregate queries (cached 10 min) ──────────────────────

    @classmethod
    def get_monthly_heatmap(cls, user):
        def _calc():
            today = timezone.now().date()
            thirty_days_ago = today - timedelta(days=29)
            daily_totals = dict(
                StudySession.objects.filter(user=user, start_time__date__gte=thirty_days_ago)
                .annotate(day=TruncDate('start_time'))
                .values('day')
                .annotate(total=Sum('duration_seconds'))
                .values_list('day', 'total')
            )
            return [
                {'date': (today - timedelta(days=i)).strftime('%b %d'),
                 'minutes': round(daily_totals.get(today - timedelta(days=i), 0) / 60)}
                for i in range(29, -1, -1)
            ]
        return cls.get_or_set_cache(f'monthly_heatmap_{user.id}', _calc, timeout=600)

    @classmethod
    def get_hourly_heatmap(cls, user):
        def _calc():
            hourly_data = [0] * 24
            rows = (
                StudySession.objects.filter(user=user)
                .annotate(hour=TruncHour('start_time'))
                .values('hour')
                .annotate(total=Sum('duration_seconds'))
            )
            for row in rows:
                h = timezone.localtime(row['hour']).hour
                hourly_data[h] += round(row['total'] / 60)
            return hourly_data
        return cls.get_or_set_cache(f'hourly_heatmap_{user.id}', _calc, timeout=600)

    @classmethod
    def get_weekly_trend(cls, user):
        def _calc():
            today = timezone.now().date()
            twelve_weeks_ago = today - timedelta(weeks=12)
            weekly_totals = {}
            rows = (
                StudySession.objects.filter(user=user, start_time__date__gte=twelve_weeks_ago)
                .annotate(week=TruncWeek('start_time'))
                .values('week')
                .annotate(total=Sum('duration_seconds'))
            )
            for row in rows:
                weekly_totals[row['week'].date()] = row['total']
            labels, minutes = [], []
            for w in range(11, -1, -1):
                week_start = today - timedelta(days=today.weekday() + w * 7)
                labels.append(week_start.strftime('W%W'))
                minutes.append(round(weekly_totals.get(week_start, 0) / 60))
            return {'labels': labels, 'minutes': minutes}
        return cls.get_or_set_cache(f'weekly_trend_{user.id}', _calc, timeout=600)

    @classmethod
    def get_recent_sessions(cls, user, limit=50):
        sessions = (
            StudySession.objects.filter(user=user)
            .select_related('subject', 'parsed_document')
            .order_by('-start_time')[:limit]
        )
        log = []
        for s in sessions:
            duration_min = round(s.duration_seconds / 60)
            hours, mins = divmod(duration_min, 60)
            duration_str = f"{hours}h {mins}m" if hours else f"{mins}m"
            log.append({
                'date': timezone.localtime(s.start_time).strftime('%d %b %Y'),
                'time': timezone.localtime(s.start_time).strftime('%I:%M %p'),
                'subject': s.subject.name if s.subject else '—',
                'subject_code': s.subject.code if s.subject else '',
                'document': s.parsed_document.title if s.parsed_document else '—',
                'duration': duration_str,
                'duration_min': duration_min,
                'xp_earned': max(1, duration_min),
            })
        return log

    # ── Practice analytics (cached 10 min) ────────────────────────────────────

    @classmethod
    def get_practice_stats(cls, user):
        """Complete practice analytics bundle — avoids multiple small queries."""
        from apps.practice.models import UserAttempt, UserAnswer

        def _calc():
            today = timezone.now().date()
            twelve_weeks_ago = today - timedelta(weeks=12)
            thirty_days_ago = today - timedelta(days=29)
            seven_days_ago = today - timedelta(days=6)

            attempts = UserAttempt.objects.filter(user=user).select_related('question_set__subject')
            total_qs = UserAnswer.objects.filter(attempt__user=user).count()

            # Average accuracy
            avg_accuracy = 0
            if attempts.exists():
                totals = attempts.aggregate(s=Sum('score'), m=Sum('max_score'))
                if totals['m'] and totals['m'] > 0:
                    avg_accuracy = round((totals['s'] / totals['m']) * 100)

            # By subject
            subject_raw = (
                attempts.values('question_set__subject__name')
                .annotate(count=Count('id'), sum_score=Sum('score'), sum_max=Sum('max_score'))
                .order_by('-count')[:5]
            )
            subject_labels = [r['question_set__subject__name'] for r in subject_raw]
            subject_scores = [
                round((r['sum_score'] / r['sum_max']) * 100) if r['sum_max'] > 0 else 0
                for r in subject_raw
            ]

            # Weekly questions answered
            daily_practice = dict(
                UserAnswer.objects.filter(
                    attempt__user=user, attempt__started_at__date__gte=seven_days_ago,
                )
                .annotate(day=TruncDate('attempt__started_at'))
                .values('day')
                .annotate(count=Count('id'))
                .values_list('day', 'count')
            )
            weekly_labels, weekly_qs = [], []
            for i in range(6, -1, -1):
                d = today - timedelta(days=i)
                weekly_labels.append(d.strftime('%a %d'))
                weekly_qs.append(daily_practice.get(d, 0))

            # 12-week accuracy trend
            pw_agg = {}
            for row in (
                attempts.filter(started_at__date__gte=twelve_weeks_ago)
                .annotate(week=TruncWeek('started_at'))
                .values('week')
                .annotate(s=Sum('score'), m=Sum('max_score'))
            ):
                pw_agg[row['week'].date()] = row
            trend_labels, trend_scores = [], []
            for w in range(11, -1, -1):
                ws = today - timedelta(days=today.weekday() + w * 7)
                trend_labels.append(ws.strftime('W%W'))
                r = pw_agg.get(ws)
                trend_scores.append(round((r['s'] / r['m']) * 100) if r and r['m'] else 0)

            # Hourly pattern
            hourly_data = [0] * 24
            for row in (
                UserAnswer.objects.filter(attempt__user=user)
                .annotate(hour=TruncHour('attempt__started_at'))
                .values('hour')
                .annotate(count=Count('id'))
            ):
                hourly_data[timezone.localtime(row['hour']).hour] += row['count']

            # 30-day heatmap
            daily_full = dict(
                UserAnswer.objects.filter(
                    attempt__user=user, attempt__started_at__date__gte=thirty_days_ago,
                )
                .annotate(day=TruncDate('attempt__started_at'))
                .values('day')
                .annotate(count=Count('id'))
                .values_list('day', 'count')
            )
            heatmap = [
                {'date': (today - timedelta(days=i)).strftime('%b %d'),
                 'qs': daily_full.get(today - timedelta(days=i), 0)}
                for i in range(29, -1, -1)
            ]

            # Recent history
            history = []
            for att in attempts.order_by('-started_at')[:20]:
                history.append({
                    'date': timezone.localtime(att.started_at).strftime('%d %b'),
                    'subject': att.question_set.subject.name if att.question_set and att.question_set.subject else '—',
                    'subject_code': att.question_set.subject.code if att.question_set and att.question_set.subject else '',
                    'title': att.question_set.title if att.question_set else '—',
                    'score': f'{att.score}/{att.max_score}',
                    'accuracy': att.percentage,
                })

            return {
                'total_qs': total_qs,
                'avg_accuracy': avg_accuracy,
                'subject_labels': subject_labels,
                'subject_scores': subject_scores,
                'weekly_labels': weekly_labels,
                'weekly_qs': weekly_qs,
                'trend_labels': trend_labels,
                'trend_scores': trend_scores,
                'hourly_data': hourly_data,
                'heatmap': heatmap,
                'history': history,
            }

        return cls.get_or_set_cache(f'practice_stats_{user.id}', _calc, timeout=600)
