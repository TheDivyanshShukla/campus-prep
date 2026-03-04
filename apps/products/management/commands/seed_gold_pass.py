from django.core.management.base import BaseCommand
from apps.products.models import SubscriptionPlan


class Command(BaseCommand):
    help = "Seed the default Gold Pass (Semester) subscription plan."

    def handle(self, *args, **options):
        plan, created = SubscriptionPlan.objects.get_or_create(
            plan_type='SEMESTER',
            defaults={
                'name': 'Gold Pass (Semester)',
                'price': 499.00,
                'is_active': True,
            },
        )
        status = "Created" if created else "Already exists"
        self.stdout.write(
            self.style.SUCCESS(f"{status}: {plan.name} (₹{plan.price}, active={plan.is_active})")
        )
