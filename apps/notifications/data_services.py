from apps.common.services import BaseService
from apps.notifications.models import Notification

class NotificationDataService(BaseService):
    """
    Service for user notifications.
    """
    
    @classmethod
    def get_user_notifications(cls, user):
        """
        Retrieves all notifications for a user.
        """
        if not user.is_authenticated:
            return []
        # We might not want to cache the full list if it changes too frequently
        # but for now we'll do it with a short timeout.
        return cls.get_or_set_cache(
            f'user_notifications_{user.id}',
            lambda: list(Notification.objects.filter(user=user).order_by('-created_at')[:50]),
            timeout=300
        )

    @classmethod
    def get_unread_count(cls, user):
        """
        Retrieves unread notification count.
        """
        if not user.is_authenticated:
            return 0
        return cls.get_or_set_cache(
            f'unread_notifications_count_{user.id}',
            lambda: Notification.objects.filter(user=user, is_read=False).count(),
            timeout=300
        )

    @classmethod
    def clear_user_notification_cache(cls, user):
        cls.clear_cache(f'user_notifications_{user.id}')
        cls.clear_cache(f'unread_notifications_count_{user.id}')
