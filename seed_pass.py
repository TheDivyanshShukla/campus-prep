import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.products.models import SubscriptionPlan

plan, created = SubscriptionPlan.objects.get_or_create(
    plan_type='SEMESTER',
    defaults={
        'name': 'Gold Pass (Semester)',
        'price': 499.00,
        'is_active': True
    }
)
print("SEMESTER Plan created:", created, "| active:", plan.is_active)
