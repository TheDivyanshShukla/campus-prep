import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.academics.models import Branch, Semester, Subject
from apps.content.models import ParsedDocument
from apps.products.models import Purchase, UnlockedContent
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds dummy purchases for user "test" to test the My Purchases UI'

    def handle(self, *args, **kwargs):
        # 1. Get the user
        try:
            test_user = User.objects.get(username="test")
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('User "test" does not exist. Please create it first.'))
            return

        # 2. Get the target branch and semester
        try:
            branch = Branch.objects.get(name="Artificial Intelligence & Data Science")
            semester = Semester.objects.get(number=1)
        except (Branch.DoesNotExist, Semester.DoesNotExist):
            self.stdout.write(self.style.ERROR('Branch or Semester not found.'))
            return

        # 3. Get all documents for subjects in this branch and sem
        subjects = Subject.objects.filter(branch=branch, semester=semester)
        if not subjects.exists():
            self.stdout.write(self.style.ERROR('No subjects found for this branch and sem.'))
            return

        all_docs = ParsedDocument.objects.filter(subject__in=subjects, is_published=True)
        
        if all_docs.count() < 5:
            self.stdout.write(self.style.WARNING(f'Found only {all_docs.count()} documents. Need at least 5 for the test criteria.'))
            # Continue anyway with whatever we have
        
        docs_list = list(all_docs)
        
        # Clear existing unlocks for this user for a clean slate
        UnlockedContent.objects.filter(user=test_user).delete()
        self.stdout.write('Cleared existing unlocked content for user "test".')
        
        # We need 3 active purchases (valid in the future) and 2 expired purchases (valid in the past)
        today = timezone.now().date()
        
        # Active unlocks (valid unlimted or 6 months from now)
        active_docs = docs_list[:3]
        for idx, doc in enumerate(active_docs):
            UnlockedContent.objects.create(
                user=test_user,
                parsed_document=doc,
                valid_until=today + datetime.timedelta(days=180) if idx % 2 == 0 else None # Mix of infinite and expiring
            )
            self.stdout.write(self.style.SUCCESS(f'Created ACTIVE unlock for: {doc.title}'))

        # Expired unlocks (valid date in the past)
        expired_docs = docs_list[3:5] if len(docs_list) >= 5 else []
        for doc in expired_docs:
            UnlockedContent.objects.create(
                user=test_user,
                parsed_document=doc,
                valid_until=today - datetime.timedelta(days=30) # Expired 30 days ago
            )
            self.stdout.write(self.style.WARNING(f'Created EXPIRED unlock for: {doc.title}'))

        self.stdout.write(self.style.SUCCESS('Successfully seeded dummy purchases! Please log in as "test" and check the UI.'))
