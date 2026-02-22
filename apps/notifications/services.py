from .models import Notification

class NotificationService:
    @staticmethod
    def notify(user, title, message, level='info', link=None):
        """
        Create a new notification for a specific user and send a Web Push.
        """
        notification = Notification.objects.create(
            user=user,
            level=level,
            title=title,
            message=message,
            link=link
        )
        
        # Send Web Push Notification
        try:
            from webpush import send_user_notification
            payload = {
                "title": title,
                "body": message,
                "link": link or "/notifications/",
            }
            send_user_notification(user=user, payload=payload, ttl=1000)
        except Exception:
            # Shield service from webpush delivery failures
            pass
            
        return notification

    @staticmethod
    def get_unread_count(user):
        return Notification.objects.filter(user=user, is_read=False).count()
