from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.academics.models import Subject
from apps.content.models import ParsedDocument

class GamerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gamer_profile')
    total_xp = models.BigIntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    daily_xp_goal = models.IntegerField(default=50) # 50 XP = roughly 50 mins of study
    
    def __str__(self):
        return f"{self.user.username}'s Gamer Profile"
        
    def add_xp(self, amount):
        self.total_xp += amount
        self.save(update_fields=['total_xp'])

class StudySession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_sessions')
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    parsed_document = models.ForeignKey(ParsedDocument, on_delete=models.SET_NULL, null=True, blank=True)
    
    start_time = models.DateTimeField(default=timezone.now)
    last_ping_time = models.DateTimeField(default=timezone.now)
    duration_seconds = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        doc_name = self.parsed_document.title if self.parsed_document else "Unknown Doc"
        return f"{self.user.username} studied {doc_name} for {self.duration_seconds}s"
