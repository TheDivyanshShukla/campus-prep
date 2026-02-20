from django.contrib.auth.models import AbstractUser
from django.db import models

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
    # This acts as a global kill-switch/status for active subscription users
    active_subscription_valid_until = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.username
