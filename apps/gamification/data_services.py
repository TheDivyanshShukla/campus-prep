from apps.common.services import BaseService
from apps.gamification.models import GamerProfile, StudySession
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

class GamificationDataService(BaseService):
    """
    Service for gamification analytics and profile data.
    """

    @classmethod
    def get_user_profile(cls, user):
        if not user.is_authenticated:
            return None
        return cls.get_or_set_cache(
            f'gamer_profile_{user.id}',
            lambda: GamerProfile.objects.get_or_create(user=user)[0],
            timeout=3600
        )

    @classmethod
    def get_dashboard_analytics(cls, user):
        """
        Calculates and caches the heavy analytics for the dashboard.
        """
        if not user.is_authenticated:
            return {}
            
        def calculate_analytics():
            now = timezone.now()
            today = now.date()
            
            # Lifetime totals
            stats = StudySession.objects.filter(user=user).aggregate(
                total_seconds=Sum('duration_seconds'),
                total_sessions=Count('id')
            )
            total_seconds = stats['total_seconds'] or 0
            total_sessions = stats['total_sessions'] or 0
            
            # Weekly stats
            weekly_labels = []
            weekly_minutes = []
            for i in range(6, -1, -1):
                target_date = today - timedelta(days=i)
                day_seconds = StudySession.objects.filter(
                    user=user, start_time__date=target_date
                ).aggregate(total=Sum('duration_seconds'))['total'] or 0
                weekly_labels.append(target_date.strftime('%a %d'))
                weekly_minutes.append(round(day_seconds / 60))

            # Subject breakdown
            subject_data = (
                StudySession.objects
                .filter(user=user, subject__isnull=False)
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
                'timestamp': now.isoformat()
            }

        return cls.get_or_set_cache(
            f'user_analytics_{user.id}',
            calculate_analytics,
            timeout=600 # Cache for 10 minutes
        )
