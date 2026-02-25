import asyncio
from typing import List
from .base import BaseDocumentParser
from .schemas import ParsedImportantQs

class ImportantQsParser(BaseDocumentParser):
    def get_schema(self, doc_type: str):
        return ParsedImportantQs

    def get_system_prompt(self, context: dict) -> str:
        return f"""You are an elite expert AI parser specializing in Bank of Important Questions for RGPV University.
        
CONTEXT:
Subject: {context.get('subject_code')} - {context.get('subject_name')}

--- SYLLABUS REFERENCE ---
{context.get('syllabus_context', 'No syllabus context provided.')}

YOUR TASK:
Extract the question text and estimate its frequency (High/Medium/Low) based on the source context (e.g. repeated years).
Use the SYLLABUS REFERENCE to ensure questions are relevant to the latest curriculum.

--- CONSTRAINTS ---
1. Clean Markdown/LaTeX for questions.
2. Assign accurate frequency labels.
"""

    async def get_extra_context(self, parsed_document_obj, subject) -> dict:
        from apps.content.models import ParsedDocument
        if not subject:
            return {'syllabus_context': "No subject associated."}
        
        syllabus = await asyncio.to_thread(lambda: ParsedDocument.objects.filter(
            subjects=subject, 
            document_type='SYLLABUS', 
            parsing_status='COMPLETED'
        ).first())
        
        if syllabus and syllabus.structured_data:
            import json
            return {'syllabus_context': json.dumps(syllabus.structured_data, indent=2)}
        return {'syllabus_context': "No existing syllabus found for context."}

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        if not all_results: return {}
        merged = {"questions": []}
        seen_qs = set()
        for res in all_results:
            if res and 'questions' in res:
                for q in res['questions']:
                    norm = q.get('text', '').strip().lower()
                    if norm not in seen_qs:
                        merged['questions'].append(q)
                        seen_qs.add(norm)
        return merged
