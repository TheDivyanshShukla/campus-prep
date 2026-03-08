"""
Short Notes Parser — Direct Markdown Output (no structured output / tool calling).
Uses StrOutputParser like naughty-notes for raw markdown generation.
"""
import asyncio
import json
import os
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langfuse.langchain import CallbackHandler
from .utils import normalize_markdown
import httpx

_short_notes_client = httpx.AsyncClient(timeout=120.0)

SUBJECT_PROMPTS = {
    "Mathematics": "Focus on rigorous definitions, step-by-step proofs, and clear worked examples. Use LaTeX for every equation.",
    "Physics": "Emphasize physical intuition, derivations of laws, and unit analysis. Include typical numerical problems.",
    "Computer Science": "Focus on logic, time complexity (Big O), and pseudo-code/algorithms where applicable. Use clear bullet points for features.",
    "Engineering": "Focus on application, design constraints, and standardized procedures. Emphasize diagrams and practical relevance.",
    "General": "Provide a balanced overview with clear headings and simplified explanations.",
}


class ShortNotesParser:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="openrouter/stepfun/step-3.5-flash:free",
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
            http_async_client=_short_notes_client,
            max_retries=5000,
            temperature=0.5,
        )

    def _get_subject_instruction(self, subject_name: str) -> str:
        if any(kw in subject_name.lower() for kw in ["computer", "it", "software", "data", "algorithm", "programming"]):
            return SUBJECT_PROMPTS["Computer Science"]
        elif any(kw in subject_name.lower() for kw in ["math", "calculus", "algebra", "numerical"]):
            return SUBJECT_PROMPTS["Mathematics"]
        elif any(kw in subject_name.lower() for kw in ["physics", "quantum", "mechanics", "optics"]):
            return SUBJECT_PROMPTS["Physics"]
        elif any(kw in subject_name.lower() for kw in ["engineering", "civil", "mechanical", "electrical"]):
            return SUBJECT_PROMPTS["Engineering"]
        return SUBJECT_PROMPTS["General"]

    def _build_planner_system_prompt(self, context: dict) -> str:
        subject_name = context.get('subject_name', 'General Engineering')
        unit_focus = f" for UNIT {context.get('unit_number', '')}" if 'unit_number' in context else ""
        return f"""You are an elite academic curriculum planner for {subject_name}.
Your task is to analyze the syllabus and past exam questions, and create a comprehensive, logical OUTLINE (Blueprint) for short notes{unit_focus}.

SYLLABUS & UNIT BOUNDARIES:
1. AUTHORITY: If the SYLLABUS REFERENCE is provided, it is the absolute source of truth for topic-to-unit mapping.
2. FILTERING: If the HISTORICAL EXAM CONTEXT contains questions that are NOT in the provided SYLLABUS section for this unit, YOU MUST IGNORE THEM.
3. MISSING SYLLABUS: If the SYLLABUS REFERENCE is "No syllabus", use the HISTORICAL EXAM CONTEXT to determine relevant topics for UNIT {context.get('unit_number', 'N/A')}.
4. STRICTNESS: Regardless of syllabus presence, your outline MUST stay strictly within the logical scope of the targeted unit. Do not include content from other units.

CORE PRINCIPLES:
1. EXHAUSTIVE: Ensure EVERY topic from the syllabus section (or logically related to the unit) is covered.
2. EXAM-DRIVEN: Prioritize and highlight topics that appear in the past questions for this unit.

OUTPUT FORMAT:
Provide a cleanly formatted Markdown outline. Use bullet points and sub-bullet points.
Do NOT write the actual notes. ONLY write the outline structure."""

    def _build_planner_user_prompt(self, context: dict) -> str:
        unit_focus = f" for UNIT {context['unit_number']}" if 'unit_number' in context else ""
        return f"""Create the notes blueprint{unit_focus} for: {context.get('subject_code')} - {context.get('subject_name')}

--- SYLLABUS REFERENCE ---
{context.get('syllabus_context', 'No syllabus context provided.')}

--- HISTORICAL EXAM CONTEXT (PAST QUESTIONS) ---
{context.get('raw_papers_context', 'No past paper data found.')}

Generate the detailed outline now."""

    def _build_writer_system_prompt(self, context: dict) -> str:
        subject_name = context.get('subject_name', 'General Engineering')
        subject_instruction = self._get_subject_instruction(subject_name)

        unit_str = f"UNIT {context.get('unit_number', 'N/A')}"
        title_str = f" ({context['unit_title']})" if context.get('unit_title') else ""
        
        return f"""You are a Senior Academic Architect specialized in {subject_name}.
Your mission is to write high-impact, exam-winning study notes for RGPV university students.

STRICT UNIT FOCUS:
- TARGET UNIT: {unit_str}{title_str}
- GROUND TRUTH: Follow the SYLLABUS section for this unit (if provided) and the provided OUTLINE/BLUEPRINT.
- UNIT BOUNDARIES: If the provided context or outline contains topics from other units that do not belong to the target unit's scope, YOU MUST IGNORE THEM.
- Your entire output must be strictly confined to the scope of {unit_str}.

CORE PRINCIPLES:
1. CLARITY FIRST: Use simple but professional language.
2. SCHEMATIC: Use tables, bullet points, and numbered lists for readability.
3. EXAM-READY: Highlight definitions and key formulas clearly.
4. SUBJECT-SPECIFIC: {subject_instruction}
5. ADHERE TO PLAN: You MUST strictly follow the provided OUTLINE/BLUEPRINT.

FORMATTING RULES:
- Use ### for Section Headings.
- Use **Bold** for crucial terms.
- Use > [!TIP] for Exam Tips and Common Pitfalls.
- Use LaTeX: $...$ for inline, $$...$$ for block math.
- BOX RESULTS: Use \\boxed{{...}} for final formulas, major theorems, or critical numerical answers.
- DIAGRAMS: Use `[[DIAGRAM: SEARCH: precise search keywords]]` for real-life images, or `[[DIAGRAM: CANVAS: detailed description]]` for illustrations.

CRITICAL LATEX RULES:
- Use \\left( ... \\right), \\left[ ... \\right] for delimiters.
- Use \\frac{{num}}{{den}} for fractions, NEVER slashes.
- Use $$ ... $$ for standalone formulas, $ ... $ for inline.
- Add \\n\\n between steps.

OUTPUT: Write in clean Markdown. No JSON wrapping. No code fences. Just the notes."""

    def _build_writer_user_prompt(self, context: dict) -> str:
        return f"""Subject: {context.get('subject_code')} - {context.get('subject_name')}

--- APPROVED OUTLINE / BLUEPRINT ---
{context.get('plan', 'No plan provided.')}

--- SYLLABUS REFERENCE ---
{context.get('syllabus_context', 'No syllabus context provided.')}

--- HISTORICAL EXAM CONTEXT (PAST QUESTIONS) ---
{context.get('raw_papers_context', 'No past paper data found.')}

Generate the comprehensive short notes now. Follow the exact structure of the APPROVED OUTLINE."""

    async def generate(self, parsed_document_obj, subject, **kwargs) -> dict:
        """Generate short notes as direct markdown, returning structured_data dict."""
        context = await self._build_context(parsed_document_obj, subject, **kwargs)

        from langchain_core.messages import SystemMessage, HumanMessage

        langfuse_handler = CallbackHandler()

        # STEP 1: PLANNER
        planner_messages = [
            SystemMessage(content=self._build_planner_system_prompt(context)),
            HumanMessage(content=self._build_planner_user_prompt(context)),
        ]
        planner_response = await self.llm.ainvoke(
            planner_messages,
            config={
                "callbacks": [langfuse_handler],
                "metadata": {
                    "langfuse_session_id": "short_notes_planner",
                    "langfuse_tags": ["short_notes", "planner"],
                }
            }
        )
        context['plan'] = planner_response.content

        # STEP 2: WRITER
        writer_messages = [
            SystemMessage(content=self._build_writer_system_prompt(context)),
            HumanMessage(content=self._build_writer_user_prompt(context)),
        ]
        
        response = await self.llm.ainvoke(
            writer_messages,
            config={
                "callbacks": [langfuse_handler],
                "metadata": {
                    "langfuse_session_id": "short_notes_generation",
                    "langfuse_tags": ["short_notes", "direct_markdown", "writer"],
                }
            }
        )
        result = response.content

        # Normalize the markdown
        md = normalize_markdown(result) if isinstance(result, str) else str(result)

        # Split into topics by ### headings for structured storage
        topics = self._split_into_topics(md, context)

        return {"topics": topics}

    def _split_into_topics(self, markdown: str, context: dict) -> list:
        """Split markdown by ### headings into topic entries."""
        import re
        # Split by ### headings
        parts = re.split(r'^(###\s+.+)$', markdown, flags=re.MULTILINE)

        topics = []
        if len(parts) <= 1:
            # No ### headings found — store as single topic
            unit_label = f"Unit {context.get('unit_number', '')}" if 'unit_number' in context else "Complete Notes"
            topics.append({
                "title": unit_label,
                "content": markdown.strip(),
            })
        else:
            # parts[0] is text before first ###, parts[1] is first heading, parts[2] is content, etc.
            # If there's content before the first heading, include it as intro
            if parts[0].strip():
                topics.append({
                    "title": "Introduction",
                    "content": parts[0].strip(),
                })
            for i in range(1, len(parts), 2):
                heading = parts[i].replace('###', '').strip()
                content = parts[i + 1].strip() if i + 1 < len(parts) else ''
                if heading and content:
                    topics.append({
                        "title": heading,
                        "content": f"### {heading}\n\n{content}",
                    })

        return topics

    async def _build_context(self, parsed_document_obj, subject, **kwargs) -> dict:
        """Fetch syllabus and PYQ context."""
        from apps.content.models import ParsedDocument

        if not subject:
            return {'syllabus_context': "N/A", 'raw_papers_context': "N/A", 'subject_code': 'N/A', 'subject_name': 'N/A'}

        unit_number = kwargs.get('unit_number')

        # 1. Get Syllabus
        syllabus = await asyncio.to_thread(lambda: ParsedDocument.objects.filter(
            subjects=subject,
            document_type='SYLLABUS',
            parsing_status__in=['COMPLETED', 'PENDING'],
            structured_data__isnull=False
        ).first())

        if not syllabus:
            # Fallback: find any syllabus for the same subject code
            syllabus = await asyncio.to_thread(lambda: ParsedDocument.objects.filter(
                subjects__code=subject.code,
                document_type='SYLLABUS',
                parsing_status__in=['COMPLETED', 'PENDING'],
                structured_data__isnull=False
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

        # 2. Get PYQ Questions for context
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
                
                # STRICT UNIT FILTERING
                if unit_number:
                    questions = [q for q in questions if str(q.get('unit')) == str(unit_number)]
                
                formatted_qs = [f"Q: {q.get('question_text')} ({q.get('marks')}m)" for q in questions]
                if formatted_qs:
                    raw_data.append({"paper": doc['title'], "questions": formatted_qs})
            return raw_data

        raw_docs = await asyncio.to_thread(_fetch_raw_papers)
        raw_papers_ctx = json.dumps(raw_docs, indent=2) if raw_docs else f"No historical questions found for Unit {unit_number or 'ALL'}."

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
