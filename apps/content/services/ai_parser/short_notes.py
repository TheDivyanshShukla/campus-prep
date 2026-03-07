import asyncio
import json
from typing import List
from .base import BaseDocumentParser
from .schemas import ParsedShortNotes

class ShortNotesParser(BaseDocumentParser):
    def get_schema(self, doc_type: str):
        return ParsedShortNotes

    def get_system_prompt(self, context: dict) -> str:
        unit_focus = ""
        if 'unit_number' in context:
            title_str = f": {context['unit_title']}" if context.get('unit_title') else ""
            unit_focus = f"\nFOCUS: Generate Short Notes ONLY for UNIT {context['unit_number']}{title_str}. Focus on topics appearing in past papers for this unit."
        
        subject_name = context.get('subject_name', 'General Engineering')
        subject_instruction = "Provide a balanced overview with clear headings and simplified explanations."
        if any(kw in subject_name.lower() for kw in ["computer", "it", "software", "data", "algorithm"]):
            subject_instruction = "Focus on logic, time complexity (Big O), and pseudo-code/algorithms where applicable. Use clear bullet points for features."
        elif any(kw in subject_name.lower() for kw in ["math", "calculus", "algebra"]):
            subject_instruction = "Focus on rigorous definitions, step-by-step proofs, and clear worked examples. Use LaTeX for every equation."
        elif any(kw in subject_name.lower() for kw in ["physics", "quantum", "mechanics"]):
            subject_instruction = "Emphasize physical intuition, derivations of laws, and unit analysis. Include typical numerical problems."

        return f"""You are a Senior Academic Architect specialized in {subject_name}.
Your mission is to write high-impact, exam-winning study notes for RGPV university students.{unit_focus}

CONTEXT:
Subject: {context.get('subject_code')} - {subject_name}
--- SYLLABUS REFERENCE ---
{context.get('syllabus_context', 'No syllabus context provided.')}
--- HISTORICAL EXAM CONTEXT (PAST QUESTIONS) ---
{context.get('raw_papers_context', 'No past paper data found.')}

CORE PRINCIPLES:
1. CLARITY FIRST: Use simple but professional language.
2. SCHEMATIC: Use tables, bullet points, and numbered lists for readability.
3. EXAM-READY: Highlight definitions and key formulas clearly.
4. SUBJECT-SPECIFIC: {subject_instruction}

FORMATTING RULES:
- Use ### for Section Headings.
- Use **Bold** for crucial terms.
- Use > [!TIP] for Exam Tips and Common Pitfalls.
- Use LaTeX: $...$ for inline, $$...$$ for block math.
- BOX RESULTS: Use \\boxed{{...}} for final formulas, major theorems, or critical numerical answers.
- DIAGRAMS: Use [[DIAGRAM: precise description of a technical diagram]] inside the topic content.

YOUR TASK:
Synthesize a set of high-impact "Short Notes" for the topics in the SYLLABUS, prioritized by frequency in HISTORICAL EXAM CONTEXT.
Generate the COMPLETE unit's notes in this single JSON response. Do not truncate.

FOR EACH TOPIC IN THE 'topics' LIST:
1. title: Crystal-clear topic name.
2. content: Comprehensive breakdown including explanation, step-by-step examples, and exam tips.
"""

    async def get_extra_context(self, parsed_document_obj, subject, **kwargs) -> dict:
        from apps.content.models import ParsedDocument
        if not subject:
            return {'syllabus_context': "N/A", 'raw_papers_context': "N/A"}
        
        unit_number = kwargs.get('unit_number')

        # 1. Get Syllabus
        syllabus = await asyncio.to_thread(lambda: ParsedDocument.objects.filter(
            subjects=subject, 
            document_type='SYLLABUS', 
            parsing_status='COMPLETED'
        ).first())
        
        syllabus_ctx = "No syllabus."
        unit_title = None
        if syllabus and syllabus.structured_data:
            modules = syllabus.structured_data.get('modules', [])
            if unit_number:
                filtered_modules = [m for m in modules if str(m.get('unit')) == str(unit_number)]
                syllabus_ctx = json.dumps({"modules": filtered_modules}, indent=2)
                if filtered_modules:
                    unit_title = filtered_modules[0].get('title')
            else:
                syllabus_ctx = json.dumps(syllabus.structured_data, indent=2)

        # 2. Get PYQ Questions for context (to know what's important)
        def _fetch_raw_papers():
            docs = ParsedDocument.objects.filter(
                subjects=subject,
                document_type__in=['PYQ', 'UNSOLVED_PYQ'],
                parsing_status='COMPLETED',
                structured_data__isnull=False
            ).values('title', 'structured_data')
            
            raw_data = []
            for doc in docs:
                questions = doc['structured_data'].get('questions', [])
                if unit_number:
                    questions = [q for q in questions if str(q.get('unit')) == str(unit_number)]
                
                # We only need the text and marks to know what the exam looks like
                formatted_qs = [f"Q: {q.get('question_text')} ({q.get('marks')}m)" for q in questions]
                if formatted_qs:
                    raw_data.append({"paper": doc['title'], "questions": formatted_qs})
            return raw_data

        raw_docs = await asyncio.to_thread(_fetch_raw_papers)
        raw_papers_ctx = json.dumps(raw_docs, indent=2) if raw_docs else "No historical questions found for this unit."

        context = {
            'subject_code': subject.code,
            'subject_name': subject.name,
            'syllabus_context': syllabus_ctx,
            'raw_papers_context': raw_papers_ctx,
        }
        if unit_number:
            context['unit_number'] = unit_number
            context['unit_title'] = unit_title
            
        return context

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        from .utils import normalize_markdown
        if not all_results: return {"topics": []}
        merged = {"topics": []}
        seen_titles = set()
        for res in all_results:
            if res and 'topics' in res:
                for t in res['topics']:
                    norm_title = t.get('title', '').strip().lower()
                    if norm_title not in seen_titles:
                        if 'content' in t:
                            t['content'] = normalize_markdown(t['content'])
                        merged['topics'].append(t)
                        seen_titles.add(norm_title)
        return merged
