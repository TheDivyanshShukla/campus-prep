import uuid
from django.db import models
from django.conf import settings
from apps.academics.models import Subject, Unit


def default_blocks():
    """Fresh default block structure for a new note."""
    return {
        "blocks": [
            {
                "id": str(uuid.uuid4()),
                "type": "paragraph",
                "content": "",
                "attrs": {},
                "children": [],
            }
        ]
    }


class Note(models.Model):
    """A student's personal note for a specific subject unit (chapter)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_notes',
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='student_notes',
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='student_notes',
    )
    blocks = models.JSONField(
        default=default_blocks,
        help_text="Structured JSON block document",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'subject', 'unit')
        ordering = ['unit__number']

    def __str__(self):
        return f"{self.user.username} — {self.subject.code} Unit {self.unit.number}"


class NoteVersion(models.Model):
    """Snapshot of a note's blocks at a point in time."""

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='versions')
    blocks = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"v{self.id} — {self.note}"


class BaseNote(models.Model):
    """Admin-provided read-only template note that students can copy."""

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='base_notes',
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='base_notes',
    )
    title = models.CharField(max_length=255, default='Base Notes')
    blocks = models.JSONField(
        default=default_blocks,
        help_text="Admin-authored block content",
    )
    is_published = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('subject', 'unit')
        ordering = ['unit__number']

    def __str__(self):
        return f"[Base] {self.subject.code} Unit {self.unit.number} — {self.title}"
