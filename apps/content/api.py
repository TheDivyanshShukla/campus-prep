import fitz  # PyMuPDF
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services.ai_parser import DocumentParserService
from .models import ParsedDocument
from apps.academics.models import Subject
from django.shortcuts import get_object_or_404

from .tasks import process_document_ai

class ParseDocumentAPI(APIView):
    """
    Accepts a PDF or Image, creates a pending ParsedDocument,
    and triggers the background AI parsing task.
    """
    def post(self, request):
        if 'file' not in request.FILES and not request.data.get('source_text'):
            return Response({"error": "No file uploaded or source text provided."}, status=status.HTTP_400_BAD_REQUEST)
        
        subject_id = request.data.get('subject_id')
        document_type = request.data.get('document_type', 'PYQ')
        title = request.data.get('title', 'Untitled Document')
        year = request.data.get('year')
        
        if not subject_id:
            return Response({"error": "Subject ID is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        subject = get_object_or_404(Subject, pk=subject_id)
        
        try:
            # Create a pending document
            doc = ParsedDocument.objects.create(
                document_type=document_type,
                title=title,
                year=year if year else None,
                source_file=request.FILES.get('file'),
                source_text=request.data.get('source_text'),
                parsing_status='PENDING',
                is_published=False
            )
            doc.subjects.add(subject)
            
            # Trigger background task
            process_document_ai.delay(doc.id)

            return Response({
                "message": "AI parsing started in the background.",
                "document_id": doc.id,
                "status": "PENDING"
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PublishParsedDocumentAPI(APIView):
    """
    Accepts final structured JSON and updates/publishes the document.
    """
    def post(self, request):
        data = request.data
        document_id = data.get('document_id')
        structured_data = data.get('structured_data')

        if not document_id or not structured_data:
             return Response({"error": "Missing required fields (document_id, structured_data)."}, status=status.HTTP_400_BAD_REQUEST)

        doc = get_object_or_404(ParsedDocument, pk=document_id)
        
        # Update with potentially edited data
        doc.structured_data = structured_data
        doc.is_published = True
        doc.save()

        return Response({
            "message": "Published successfully.",
            "document_id": doc.id
        }, status=status.HTTP_200_OK)
