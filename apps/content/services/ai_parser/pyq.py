import asyncio
import re
from typing import List
from .base import BaseDocumentParser
from .schemas import ParsedPYQPaper, ParsedUnsolvedPYQPaper

class PYQParser(BaseDocumentParser):
    def get_schema(self, doc_type: str):
        return ParsedPYQPaper if doc_type == 'PYQ' else ParsedUnsolvedPYQPaper

    def get_system_prompt(self, context: dict) -> str:
        return f"""You are an elite expert AI parser specializing in Solved/Unsolved Previous Year Question Papers for RGPV University.
        
CONTEXT:
Branch: {context.get('branch_name')}
Subject: {context.get('subject_code')} - {context.get('subject_name')}
Document Type: {context.get('document_type_display')}

--- SYLLABUS REFERENCE (FOR UNIT MAPPING) ---
{context.get('syllabus_context', 'No syllabus context provided.')}

YOUR TASK:
Extract exact questions, marks, and units from the source.
If a question does not have a unit explicitly mentioned, use the SYLLABUS REFERENCE above to determine which module/unit it belongs to based on the topics.

--- SPECIAL RULES FOR PYQS ---
1. MARKS: Ensure marks are captured accurately.
2. OR CHOICES: Correctly identify if a question has an 'OR' choice and set `has_or_choice` accordingly.
3. PARTS: Capture 'a', 'b', 'c' parts accurately in the `part` field.
"""

    async def get_extra_context(self, parsed_document_obj, subject) -> dict:
        """Fetch existing syllabus for the same subject to provide context."""
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
        return {'syllabus_context': "No existing syllabus found for unit mapping context."}

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        if not all_results: return {}
        merged = all_results[0].copy()
        seen_questions = set()
        
        for res in all_results:
            if 'questions' in res:
                for q in res['questions']:
                    q['question_text'] = self._sanitize_content(q.get('question_text', ''))
                    if 'latex_answer' in q:
                        q['latex_answer'] = self._sanitize_content(q.get('latex_answer', ''))
                    
                    norm_text = re.sub(r'\s+', '', q.get('question_text', '')).lower()
                    if norm_text not in seen_questions:
                        if res is all_results[0]: # Already in merged
                            seen_questions.add(norm_text)
                        else:
                            merged['questions'].append(q)
                            seen_questions.add(norm_text)
        return merged
