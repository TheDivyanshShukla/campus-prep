from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.notifications.services import NotificationService

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a welcome notification for all users'

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            NotificationService.notify(
                user=user,
                level='success',
                title='Welcome to the new Alert System! 🔔',
                message='We have launched a new notification system to help you track your streaks and achievements. Happy studying!',
                link='/notifications/'
            )
        self.stdout.write(self.style.SUCCESS(f'Successfully created welcome notifications for {users.count()} users'))
