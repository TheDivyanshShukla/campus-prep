from .pyq import PYQParser
from .syllabus import SyllabusParser
from .notes import NoteParser
from .formula import FormulaParser
from .important_qs import ImportantQsParser

class DocumentParserService:
    @staticmethod
    async def parse_document(parsed_document_obj):
        doc_type = parsed_document_obj.document_type
        
        if doc_type in ['PYQ', 'UNSOLVED_PYQ']:
            parser = PYQParser()
        elif doc_type == 'SYLLABUS':
            parser = SyllabusParser()
        elif doc_type in ['NOTES', 'SHORT_NOTES', 'CRASH_COURSE']:
            parser = NoteParser()
        elif doc_type == 'FORMULA':
            parser = FormulaParser()
        elif doc_type == 'IMPORTANT_Q':
            parser = ImportantQsParser()
        else:
            # Fallback to NoteParser as it's the most flexible
            parser = NoteParser()
            
        return await parser.parse(parsed_document_obj)
