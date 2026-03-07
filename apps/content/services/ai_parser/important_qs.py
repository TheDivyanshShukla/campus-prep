import asyncio
from typing import List
from .base import BaseDocumentParser
from .schemas import ParsedImportantQs

class ImportantQsParser(BaseDocumentParser):
    def get_schema(self, doc_type: str):
        return ParsedImportantQs

    def get_system_prompt(self, context: dict) -> str:
        unit_focus = ""
        if 'unit_number' in context:
            title_str = f": {context['unit_title']}" if context.get('unit_title') else ""
            unit_focus = f"\nFOCUS: Focus EXCLUSIVELY on generating important questions for UNIT {context['unit_number']}{title_str}. Ensure all generated questions relate to this unit's topics."
        return f"""You are an elite expert AI academic strategist for RGPV University.{unit_focus}
        
CONTEXT:
Subject: {context.get('subject_code')} - {context.get('subject_name')}

--- SYLLABUS REFERENCE ---
{context.get('syllabus_context', 'No syllabus context provided.')}

--- SUPPLEMENTARY NOTES (CONCEPTUAL REFERENCE) ---
{context.get('supplementary_notes', 'No supplementary notes found.')}

--- RAW PAST PAPER DATA (CONTEXT) ---
{context.get('raw_papers_context', 'No raw papers found.')}

--- AGGREGATED ANALYTICS HEATMAP ---
{context.get('paper_trends_context', 'No analytics summary available.')}

YOUR TASK:
Using the SYLLABUS, SUPPLEMENTARY NOTES, RAW PAST PAPER DATA, and the ANALYTICS HEATMAP, synthesize a definitive "Important Questions" list.
- Prioritize topics that appear frequently in the RAW PAPERS.
- Use the SYLLABUS to ensure technical accuracy and terminology.
- Use SUPPLEMENTARY NOTES to understand the core concepts and provide accurate question text and descriptions.
- Generate questions that represent the standard and pattern of RGPV exams.

For each question:
1. text: Clear English question text. Use LaTeX ($...$) ONLY for mathematical formulas, variables, or technical symbols. NEVER wrap plain English sentences in LaTeX tags like \text{...}.
2. marks: Typical marks awarded in RGPV exams (e.g. 7, 10, 14).
3. description: Brief rationale (e.g. "Core derivation from Unit 2", "Repeated 4 times").
4. frequency_count: Integer total occurrences.
5. years: List of actual years.
6. unit: Syllabus unit (1-5).
7. priority: 'High' (asked >3 times), 'Medium' (asked 1-2 times), 'Low' (predicted probability).

CONSTRAINTS:
1. Use professional LaTeX ($...$ and $$...$$) for mathematical formulas, variables, and technical symbols ONLY.
2. NEVER use LaTeX for lists or document structure. For lists, use standard Markdown (e.g., - item).
3. EXPLICITLY FORBIDDEN: \\begin{{itemize}}, \\begin{{enumerate}}, \\item, \\begin{{center}}, etc.
4. DO NOT wrap the entire question in LaTeX. Keep plain text as plain text for readability.
5. Deduplicate similar/overlapping concepts.
6. If raw data is empty, use syllabus and general knowledge.
"""

    async def get_extra_context(self, parsed_document_obj, subject, **kwargs) -> dict:
        from apps.content.models import ParsedDocument
        if not subject:
            return {'syllabus_context': "N/A", 'paper_trends_context': "N/A", 'raw_papers_context': "N/A"}
        
        import json
        unit_number = kwargs.get('unit_number')

        # 1. Get Syllabus
        syllabus = await asyncio.to_thread(lambda: ParsedDocument.objects.filter(
            subjects=subject, 
            document_type='SYLLABUS', 
            parsing_status='COMPLETED'
        ).first())
        
        syllabus_ctx = "No syllabus."
        if syllabus and syllabus.structured_data:
            if unit_number:
                # Filter modules for the specific unit
                modules = syllabus.structured_data.get('modules', [])
                filtered_modules = [m for m in modules if str(m.get('unit')) == str(unit_number)]
                syllabus_ctx = json.dumps({"modules": filtered_modules}, indent=2)
                if not filtered_modules:
                    syllabus_ctx = f"Syllabus for Unit {unit_number} not found in full syllabus."
            else:
                syllabus_ctx = json.dumps(syllabus.structured_data, indent=2)

        # 2. Get Raw Papers (PYQs)
        def _fetch_raw_papers():
            docs = ParsedDocument.objects.filter(
                subjects=subject,
                document_type__in=['PYQ', 'UNSOLVED_PYQ'],
                parsing_status='COMPLETED',
                structured_data__isnull=False
            ).values('title', 'year', 'structured_data')
            
            raw_data = list(docs)
            if unit_number:
                # Filter questions in each paper for the specific unit
                for doc in raw_data:
                    if doc['structured_data'] and 'questions' in doc['structured_data']:
                        questions = doc['structured_data']['questions']
                        # Some might use 'unit' as int or string
                        doc['structured_data']['questions'] = [q for q in questions if str(q.get('unit')) == str(unit_number)]
            return raw_data

        raw_docs = await asyncio.to_thread(_fetch_raw_papers)
        raw_papers_ctx = json.dumps(raw_docs, indent=2) if raw_docs else "No raw papers found."

        # 3. Get AI Analytics
        from apps.academics.models import SubjectAnalytics
        analytics = await asyncio.to_thread(lambda: SubjectAnalytics.objects.filter(subject=subject).first())
        paper_trends_ctx = "No analytics."
        if analytics:
            heatmap = analytics.syllabus_heatmap or {}
            top_qs = analytics.top_repeated_questions or []
            
            if unit_number:
                # Filter heatmap to only include this unit's topics
                filtered_heatmap = {k: v for k, v in heatmap.items() if str(v.get('unit')) == str(unit_number)}
                paper_trends_ctx = json.dumps({
                    "unit_topic_frequency": filtered_heatmap,
                    "global_top_questions": top_qs # Keep global top qs for reference
                }, indent=2)
            else:
                paper_trends_ctx = json.dumps({
                    "syllabus_heatmap": heatmap,
                    "top_repeated_questions": top_qs
                }, indent=2)

        # 4. Get Short Notes (Added for better conceptual synthesis)
        def _fetch_notes():
            notes_query = ParsedDocument.objects.filter(
                subjects=subject,
                document_type__in=['NOTES', 'SHORT_NOTES'],
                parsing_status='COMPLETED'
            )
            if unit_number:
                # Try to find unit-specific notes
                unit_notes = notes_query.filter(title__contains=f"Unit {unit_number}").first()
                if not unit_notes:
                    # Fallback to general notes if unit-specific not found
                    unit_notes = notes_query.first()
                return unit_notes.structured_data if unit_notes else None
            return [n.structured_data for n in notes_query[:2]] # Limit to 2 for context size

        notes_data = await asyncio.to_thread(_fetch_notes)
        notes_ctx = json.dumps(notes_data, indent=2) if notes_data else "No supplementary notes found."

        context = {
            'syllabus_context': syllabus_ctx,
            'raw_papers_context': raw_papers_ctx,
            'paper_trends_context': paper_trends_ctx,
            'supplementary_notes': notes_ctx
        }
        if unit_number:
            context['unit_number'] = unit_number
            # Try to find unit title for context
            if syllabus and syllabus.structured_data:
                modules = syllabus.structured_data.get('modules', [])
                for m in modules:
                    if str(m.get('unit')) == str(unit_number):
                        context['unit_title'] = m.get('title')
                        break
        return context

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        if not all_results: return {"questions": []}
        merged = {"questions": []}
        seen_qs = set()
        for res in all_results:
            if res and 'questions' in res:
                for q in res['questions']:
                    # Simple text-based deduplication
                    norm = q.get('text', '').strip().lower()
                    if norm not in seen_qs:
                        merged['questions'].append(q)
                        seen_qs.add(norm)
        return merged
