from apps.common.services import BaseService
from .models import Note, BaseNote


class NotesDataService(BaseService):
    """Service layer for student notes data retrieval."""

    @classmethod
    def get_user_note(cls, user, subject_id, unit_id):
        return Note.objects.filter(
            user=user, subject_id=subject_id, unit_id=unit_id
        ).first()

    @classmethod
    def get_user_notes_for_subject(cls, user, subject):
        return list(Note.objects.filter(user=user, subject=subject))

    @classmethod
    def get_base_notes_for_subject(cls, subject):
        return cls.get_or_set_cache(
            f'base_notes_subject_{subject.id}',
            lambda: list(BaseNote.objects.filter(subject=subject, is_published=True)),
            timeout=3600,
        )
