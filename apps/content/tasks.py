import logging
import asyncio
from celery import shared_task
from django.utils import timezone
from .models import ParsedDocument
from .services.ai_parser import DocumentParserService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_document_ai(self, document_id):
    """
    Background task to parse a document using AI.
    """
    # Wait for document to be available in DB (handles transaction race condition)
    document = None
    for i in range(5):
        try:
            document = ParsedDocument.objects.get(id=document_id)
            break
        except ParsedDocument.DoesNotExist:
            if i == 4:
                logger.error(f"Document with id {document_id} not found after 5 retries.")
                return
            import time
            time.sleep(1)

    # Guard: prevent multiple concurrent parsing tasks for the same document
    if document.parsing_status == 'PROCESSING':
        logger.warning(f"Document {document_id} is already being processed. Skipping.")
        return {"status": "skipped", "reason": "already_processing"}

    # Update status to PROCESSING and reset chunk counters
    document.parsing_status = 'PROCESSING'
    document.parsing_completed_chunks = 0
    document.parsing_total_chunks = 0
    document.save(update_fields=['parsing_status', 'parsing_completed_chunks', 'parsing_total_chunks'])

    try:
        parser = DocumentParserService()
        # The parser service handles its own internal chunking and merging
        structured_data = asyncio.run(parser.parse_document(document))
        
        # Post-Processing: Recreate CANVAS images
        from .services.image_recreator import ImageRecreationService
        recreator = ImageRecreationService(doc_obj=document)
        structured_data = asyncio.run(recreator.process_structured_data(structured_data))
        
        # Save results and update status
        document.structured_data = structured_data
        document.parsing_status = 'COMPLETED'
        
        # Clear original source files as requested (Zero-PDF Experience)
        # Note: We do this AFTER a successful parse
        if document.source_file:
            document.source_file.delete(save=False)
            document.source_file = None
            
        document.save(update_fields=['structured_data', 'parsing_status', 'source_file', 'updated_at'])

        # Delete related DocumentImages
        document.images.all().delete()
        
        # Post-Processing: Sync syllabus units if applicable
        if document.document_type == 'SYLLABUS':
            from .services.syllabus_processor import SyllabusProcessor
            processor = SyllabusProcessor()
            processor.sync_to_units(document)
        
        logger.info(f"Successfully parsed and post-processed document {document_id}")
        return {"status": "success", "document_id": document_id}

    except Exception as exc:
        logger.error(f"Error parsing document {document_id}: {exc}")
        
        # Update status to FAILED
        document.parsing_status = 'FAILED'
        document.save(update_fields=['parsing_status', 'updated_at'])
        
        # Retry the task with exponential backoff if it's a transient error
        # (Parser service already has some retries, but this covers higher level failures)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
