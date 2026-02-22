from django.db import models
from django.conf import settings

class Notification(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.URLField(max_length=500, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"
