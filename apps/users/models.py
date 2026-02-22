from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    preferred_branch = models.ForeignKey(
        'academics.Branch', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='users'
    )
    preferred_semester = models.ForeignKey(
        'academics.Semester', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='users'
    )
    active_subscription_valid_until = models.DateField(null=True, blank=True)
    gold_pass_branch = models.ForeignKey(
        'academics.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gold_pass_users'
    )
    gold_pass_semester = models.ForeignKey(
        'academics.Semester',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gold_pass_users'
    )
    active_subscription_plan = models.ForeignKey(
        'products.SubscriptionPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscribed_users'
    )

    def has_gold_pass(self, subject=None, document_type=None):
        if self.is_staff:
            return True
            
        if self.active_subscription_valid_until and self.active_subscription_valid_until >= timezone.now().date():
            # If no specific subject or document_type is requested, general validity suffices
            if not subject and not document_type:
                return True
                
            # If a subject is provided, confirm it matches the Gold Pass constraints
            if subject:
                if self.gold_pass_branch != subject.branch or self.gold_pass_semester != subject.semester:
                    return False
            
            # If a document_type is provided, confirm the active plan allows it
            if document_type and self.active_subscription_plan:
                plan = self.active_subscription_plan
                type_map = {
                    'NOTES': plan.includes_notes,
                    'PYQ': plan.includes_pyq,
                    'UNSOLVED_PYQ': plan.includes_unsolved_pyq,
                    'SHORT_NOTES': plan.includes_short_notes,
                    'IMPORTANT_Q': plan.includes_important_q,
                    'FORMULA': plan.includes_formula,
                    'CRASH_COURSE': plan.includes_crash_course,
                    'SYLLABUS': True # Usually syllabus is inherently free/included
                }
                # Default to false if the mapping doesn't exist just as a fallback security measure, though it should.
                if not type_map.get(document_type, False):
                    return False
            
            # If all checks pass, they have access
            return True
            
        return False

    def __str__(self):
        return self.username
