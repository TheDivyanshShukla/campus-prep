from django.db.models import Count
from django.db import connection, IntegrityError
import logging

from apps.common.services import BaseService
from .models import BaseNote, Note, NoteVersion

_logger = logging.getLogger(__name__)


class NotesDataService(BaseService):
    """Service layer for student notes data retrieval."""

    # ── User notes ────────────────────────────────────────────────────────────

    @classmethod
    def get_user_note(cls, user, subject_id, unit_id):
        return Note.objects.filter(
            user=user, subject_id=subject_id, unit_id=unit_id
        ).first()

    @classmethod
    def get_user_notes_for_subject(cls, user, subject):
        return list(Note.objects.filter(user=user, subject=subject))

    @classmethod
    def get_user_note_counts_by_subject(cls, user):
        """Returns ``{subject_id: count}`` for all subjects with notes."""
        return dict(
            Note.objects.filter(user=user)
            .values_list('subject_id')
            .annotate(c=Count('id'))
            .values_list('subject_id', 'c')
        )

    @classmethod
    def get_note_by_id(cls, user, note_id):
        return Note.objects.filter(pk=note_id, user=user).first()

    @classmethod
    def get_or_create_note(cls, user, subject, unit):
        return Note.objects.get_or_create(
            user=user, subject=subject, unit=unit,
        )

    # ── Base notes ────────────────────────────────────────────────────────────

    @classmethod
    def get_base_notes_for_subject(cls, subject):
        return cls.get_or_set_cache(
            f'base_notes_subject_{subject.id}',
            lambda: list(BaseNote.objects.filter(subject=subject, is_published=True)),
            timeout=3600,
        )

    @classmethod
    def get_base_note_for_unit(cls, subject, unit):
        return cls.get_or_set_cache(
            f'base_note_{subject.id}_{unit.id}',
            lambda: BaseNote.objects.filter(
                subject=subject, unit=unit, is_published=True
            ).first(),
            timeout=3600,
        )

    @classmethod
    def get_base_note_by_id(cls, base_note_id):
        return BaseNote.objects.filter(pk=base_note_id, is_published=True).first()

    # ── Versions ──────────────────────────────────────────────────────────────

    @classmethod
    def _reset_noteversion_sequence(cls):
        """Reset the Postgres sequence for NoteVersion.id to max(id).

        This handles cases where rows were inserted/restored bypassing the
        sequence, causing nextval to produce duplicate primary keys.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT setval(
                  pg_get_serial_sequence('student_notes_noteversion','id'),
                  COALESCE((SELECT MAX(id) FROM student_notes_noteversion), 1),
                  (SELECT MAX(id) FROM student_notes_noteversion) IS NOT NULL
                );
                """
            )

    @classmethod
    def create_version_snapshot(cls, note):
        try:
            return NoteVersion.objects.create(note=note, blocks=note.blocks)
        except IntegrityError as exc:
            _logger.warning(
                "NoteVersion create failed with IntegrityError; resetting sequence and retrying (%s)",
                exc,
            )
            try:
                cls._reset_noteversion_sequence()
            except Exception:
                _logger.exception("Failed to reset NoteVersion sequence")
                raise
            return NoteVersion.objects.create(note=note, blocks=note.blocks)

    @classmethod
    def prune_versions(cls, note, keep=50):
        old_ids = list(
            NoteVersion.objects.filter(note=note)
            .order_by('-created_at')
            .values_list('id', flat=True)[keep:]
        )
        if old_ids:
            NoteVersion.objects.filter(id__in=old_ids).delete()

    @classmethod
    def get_version_history(cls, note, limit=20):
        return list(NoteVersion.objects.filter(note=note).order_by('-created_at')[:limit])

    @classmethod
    def get_version_by_id(cls, user, version_id):
        return (
            NoteVersion.objects.select_related('note')
            .filter(pk=version_id, note__user=user)
            .first()
        )
