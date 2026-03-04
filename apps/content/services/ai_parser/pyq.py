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
1. INDIVIDUAL QUESTION GRANULARITY (CRITICAL):
    - NEVER merge multiple sub-parts into one record.
    - If a paper shows Q2(a) and Q2(b), output TWO separate `questions[]` entries.
    - If a line contains both parts (for example "a) ... b) ..."), split into separate entries.
    - `part` must be filled with "a", "b", "c", "i", "ii" etc when present.
2. MARKS:
    - Capture explicit marks exactly when printed.
    - For the common RGPV 14-mark pattern where one main question is split into two parts (a/b), assign 7 marks to each part unless paper explicitly says otherwise.
    - For three equal parts under one 14-mark question, distribute as close as possible and keep integer marks (prefer explicit printed marks when available).
3. QUESTION TEXT QUALITY:
    - Keep `question_text` in English only.
    - Ignore Hindi translation lines entirely.
    - Preserve exact technical wording, symbols, numbering, and constraints.
    - Remove OCR garbage but do not change meaning.
4. EXAM LAYOUT AWARENESS:
    - Papers often appear as: Qn (14 marks) with two subparts a/b.
    - Extract at subpart level so final output is a list of individual answerable questions.
5. UNIT MAPPING:
    - Prefer explicit unit tags (e.g., "Unit 1").
    - If absent, infer from syllabus topics with best effort.
6. COUNT SANITY:
    - Typical paper has 8 main questions; because of subpart splitting, final extracted count can be higher.
    - Do not force exactly 8 output items.
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
