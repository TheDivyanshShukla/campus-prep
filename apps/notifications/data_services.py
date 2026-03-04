from apps.common.services import BaseService
from apps.notifications.models import Notification


class NotificationDataService(BaseService):
    """
    Service for user notifications.
    """

    @classmethod
    def get_user_notifications(cls, user):
        if not user.is_authenticated:
            return []
        return cls.get_or_set_cache(
            f'user_notifications_{user.id}',
            lambda: list(Notification.objects.filter(user=user).order_by('-created_at')[:50]),
            timeout=300,
        )

    @classmethod
    def get_unread_count(cls, user):
        if not user.is_authenticated:
            return 0
        return cls.get_or_set_cache(
            f'unread_notifications_count_{user.id}',
            lambda: Notification.objects.filter(user=user, is_read=False).count(),
            timeout=300,
        )

    @classmethod
    def clear_user_notification_cache(cls, user):
        cls.clear_cache(f'user_notifications_{user.id}')
        cls.clear_cache(f'unread_notifications_count_{user.id}')

    # ── Mutation helpers ──────────────────────────────────────────────────────

    @classmethod
    def mark_notification_read(cls, user, pk):
        """Mark a single notification as read and bust caches."""
        updated = Notification.objects.filter(pk=pk, user=user, is_read=False).update(is_read=True)
        if updated:
            cls.clear_user_notification_cache(user)
        return updated

    @classmethod
    def mark_all_read(cls, user):
        """Bulk-mark all unread notifications and bust caches."""
        updated = Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        cls.clear_user_notification_cache(user)
        return updated
