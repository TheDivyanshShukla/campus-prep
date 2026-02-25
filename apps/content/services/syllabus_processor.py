from django.db import transaction
from apps.academics.models import Unit
import logging

logger = logging.getLogger(__name__)

class SyllabusProcessor:
    """
    Handles post-processing of parsed syllabus documents.
    Syncs structured syllabus data to the academics.Unit models.
    """

    @transaction.atomic
    def sync_to_units(self, parsed_document):
        """
        Takes a ParsedDocument of type SYLLABUS and updates/creates Units for its associated subjects.
        """
        if parsed_document.document_type != 'SYLLABUS':
            return
            
        structured_data = parsed_document.structured_data
        if not structured_data or 'modules' not in structured_data:
            logger.warning(f"No modules found in structured data for document {parsed_document.id}")
            return

        subjects = parsed_document.subjects.all()
        for subject in subjects:
            for module in structured_data['modules']:
                unit_number = module.get('unit')
                unit_title = module.get('title')
                unit_topics = module.get('topics', [])

                if unit_number is None:
                    continue

                # Get or create the Unit
                unit, created = Unit.objects.update_or_create(
                    subject=subject,
                    number=unit_number,
                    defaults={
                        'name': unit_title or f"Unit {unit_number}",
                        'topics': unit_topics,
                        'description': "\n".join(unit_topics) if unit_topics else ""
                    }
                )
                
                status = "created" if created else "updated"
                logger.debug(f"Syllabus sync: {status} Unit {unit_number} for subject {subject.code}")

        logger.info(f"Syllabus sync completed for document {parsed_document.id} across {subjects.count()} subjects.")
