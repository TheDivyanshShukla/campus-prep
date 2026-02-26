from .pyq import PYQParser
from .syllabus import SyllabusParser
from .notes import NoteParser
from .formula import FormulaParser
from .important_qs import ImportantQsParser

class DocumentParserService:
    @staticmethod
    async def parse_document(parsed_document_obj):
        from django.conf import settings
        doc_type = parsed_document_obj.document_type
        
        # Get model for this doc type
        model_mapping = getattr(settings, 'AI_PARSER_MODEL_MAPPING', {})
        model_name = model_mapping.get(doc_type) or getattr(settings, 'AI_PARSER_DEFAULT_MODEL', 'gemini/gemini-2.0-flash')
        
        if doc_type in ['PYQ', 'UNSOLVED_PYQ']:
            parser = PYQParser(model_name=model_name)
        elif doc_type == 'SYLLABUS':
            parser = SyllabusParser(model_name=model_name)
        elif doc_type in ['NOTES', 'SHORT_NOTES', 'CRASH_COURSE']:
            parser = NoteParser(model_name=model_name)
        elif doc_type == 'FORMULA':
            parser = FormulaParser(model_name=model_name)
        elif doc_type == 'IMPORTANT_Q':
            parser = ImportantQsParser(model_name=model_name)
        else:
            # Fallback to NoteParser as it's the most flexible
            parser = NoteParser(model_name=model_name)
            
        return await parser.parse(parsed_document_obj)
