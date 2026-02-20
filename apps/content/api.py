import fitz  # PyMuPDF
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import ContentParserService
from .models import ParsedDocument
from apps.academics.models import Subject
from django.shortcuts import get_object_or_404

class ParseDocumentAPI(APIView):
    """
    Accepts a PDF or Image, extracts text, 
    and returns a structured JSON from LangChain.
    """
    def post(self, request):
        if 'file' not in request.FILES:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        
        file_obj = request.FILES['file']
        
        try:
            # Simple PyMuPDF extraction for PDFs
            if file_obj.name.endswith('.pdf'):
                doc = fitz.open(stream=file_obj.read(), filetype="pdf")
                raw_text = ""
                for page in doc:
                    raw_text += page.get_text()
                doc.close()
            else:
                # Placeholder: If images are strictly requested, we can handle base64 encoding
                # directly to Gemini. Standard OCR placeholder for now.
                raw_text = "IMAGE_UPLOAD_PLACEHOLDER - Awaiting Multimodal logic."
            
            # Run LangChain AI Service
            parser = ContentParserService()
            structured_result = parser.parse_pyq_text(raw_text)

            return Response({
                "message": "AI parsing successful.",
                "data": structured_result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PublishParsedDocumentAPI(APIView):
    """
    Accepts final structured JSON from the admin UI and saves it to PostgreSQL.
    """
    def post(self, request):
        data = request.data
        subject_id = data.get('subject_id')
        document_type = data.get('document_type', 'PYQ')
        title = data.get('title')
        year = data.get('year')
        structured_data = data.get('structured_data')

        if not all([subject_id, title, structured_data]):
             return Response({"error": "Missing required fields (subject, title, structured_data)."}, status=status.HTTP_400_BAD_REQUEST)

        subject = get_object_or_404(Subject, pk=subject_id)

        doc = ParsedDocument.objects.create(
            subject=subject,
            document_type=document_type,
            title=title,
            year=year,
            structured_data=structured_data,
            is_published=True
        )

        return Response({
            "message": "Published successfully.",
            "document_id": doc.id
        }, status=status.HTTP_201_CREATED)
