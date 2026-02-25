import os
import json
import base64
import asyncio
import time
import re
import hashlib
import fitz # PyMuPDF for PDF extraction
from pathlib import Path
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from typing import List, Optional, Any, Union, Literal
from pydantic import BaseModel, Field
from django.core.files.storage import default_storage
import httpx

# Shared Async HTTP Client for AI parsing connection pooling
_ai_parser_client = httpx.AsyncClient(timeout=60.0)


# --- Structured Output Schemas (Pydantic for validation & better Gemini compatibility) ---

class PYQQuestion(BaseModel):
    unit: Optional[int] = None
    marks: int
    question_text: str = Field(..., description="Full markdown and LaTeX math formulas.")
    image_strategy: Optional[Literal['SEARCH', 'GEN_PROMPT', 'CANVAS']] = Field(None, description="The chosen strategy to recreate the image.")
    image_details: Optional[str] = Field(None, description="Keywords, prompts, or logic for image reconstruction.")
    part: Optional[str] = None
    has_or_choice: bool = False
    latex_answer: str

class ParsedPYQPaper(BaseModel):
    questions: List[PYQQuestion]

class UnsolvedPYQQuestion(BaseModel):
    unit: Optional[int] = None
    marks: int
    question_text: str = Field(..., description="Full markdown and LaTeX math formulas.")
    image_strategy: Optional[Literal['SEARCH', 'GEN_PROMPT', 'CANVAS']] = None
    image_details: Optional[str] = None
    part: Optional[str] = None
    has_or_choice: bool = False

class ParsedUnsolvedPYQPaper(BaseModel):
    questions: List[UnsolvedPYQQuestion]

class SyllabusModule(BaseModel):
    unit: int
    topics: List[str]

class ParsedSyllabus(BaseModel):
    modules: List[SyllabusModule]

class NoteContentBlock(BaseModel):
    type: Literal['text', 'image']
    content: Optional[str] = Field(None, description="Markdown content for text blocks.")
    image_strategy: Optional[Literal['SEARCH', 'GEN_PROMPT', 'CANVAS']] = None
    image_details: Optional[str] = None

class NoteSection(BaseModel):
    section_title: str
    content_blocks: List[NoteContentBlock]

class ParsedNotes(BaseModel):
    sections: List[NoteSection]

class AcademicFormula(BaseModel):
    name: str
    latex: str

class ParsedFormulaSheet(BaseModel):
    formulas: List[AcademicFormula]

class ImportantQuestion(BaseModel):
    text: str
    frequency: Literal['High', 'Medium', 'Low']

class ParsedImportantQs(BaseModel):
    questions: List[ImportantQuestion]

# --- Service Implementation ---

class DocumentParserService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gemini/gemini-3-flash-preview",
            # model="gemini/gemini-2.5-flash-lite",
            # model="gemini/gemini-2.5-flash",
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
            temperature=0.2,
            http_async_client=_ai_parser_client,
        )

    def encode_image(self, image_name: str) -> str:
        with default_storage.open(image_name, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def get_schema_for_type(self, doc_type: str):
        # Depending on doc_type, return different Pydantic models to enforce structure
        if doc_type == 'PYQ':
            return ParsedPYQPaper
        elif doc_type == 'UNSOLVED_PYQ':
            return ParsedUnsolvedPYQPaper
        elif doc_type == 'SYLLABUS':
            return ParsedSyllabus
        elif doc_type == 'IMPORTANT_Q':
            return ParsedImportantQs
        elif doc_type == 'FORMULA':
            return ParsedFormulaSheet
        else: # NOTES, SHORT_NOTES, CRASH_COURSE
            return ParsedNotes

    def _get_pdf_page_images(self, pdf_name: str) -> List[str]:
        """Convert PDF pages to base64 images from storage."""
        images = []
        try:
            with default_storage.open(pdf_name, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # Higher resolution for better OCR
                    img_bytes = pix.tobytes("jpg")
                    images.append(base64.b64encode(img_bytes).decode('utf-8'))
                doc.close()
        except Exception as e:
            print(f"Error converting PDF to images: {e}")
        return images

    def _sanitize_content(self, text: str) -> str:
        """Fixes common LLM hallucinations in LaTeX and Markdown."""
        if not isinstance(text, str):
            return str(text)
        
        # 1. Fix common \left{ error (should be \left\{ or \left()
        # Case: \left{ or \left { (space)
        text = re.sub(r'\\left\s*\{', r'\\left\\{', text)
        text = re.sub(r'\\right\s*\}', r'\\right\\}', text)
        
        # 2. Fix cases where \left is used with a bracket but missing backslash for some symbols
        # (Curly braces are handled above, others like ( and [ usually don't need backslashes for delimiters)
        
        return text

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        """Merges multiple chunk results into a single structured dictionary."""
        if not all_results:
            return {}
        
        merged = all_results[0].copy()

        # Sanitize first chunk
        if doc_type in ['NOTES', 'SHORT_NOTES']:
            if 'sections' in merged:
                for s in merged['sections']:
                    for block in s.get('content_blocks', []):
                        if block.get('type') == 'text' and 'content' in block:
                            block['content'] = self._sanitize_content(block['content'])
        elif 'questions' in merged:
            for q in merged['questions']:
                if 'question_text' in q: q['question_text'] = self._sanitize_content(q['question_text'])
                if 'latex_answer' in q: q['latex_answer'] = self._sanitize_content(q['latex_answer'])

        # Store seen content to deduplicate
        seen_questions = set()
        if 'questions' in merged:
            for q in merged['questions']:
                # Basic normalization for deduplication
                norm_text = re.sub(r'\s+', '', q.get('question_text', '')).lower()
                seen_questions.add(norm_text)

        seen_sections = set()
        if 'sections' in merged:
            for s in merged['sections']:
                seen_sections.add(s.get('section_title', '').strip().lower())

        for next_result in all_results[1:]:
            if doc_type in ['PYQ', 'UNSOLVED_PYQ', 'IMPORTANT_Q']:
                if 'questions' in next_result:
                    for q in next_result['questions']:
                        if 'question_text' in q: q['question_text'] = self._sanitize_content(q['question_text'])
                        if 'latex_answer' in q: q['latex_answer'] = self._sanitize_content(q['latex_answer'])
                        
                        norm_text = re.sub(r'\s+', '', q.get('question_text', '')).lower()
                        if norm_text not in seen_questions:
                            merged['questions'].append(q)
                            seen_questions.add(norm_text)
            elif doc_type == 'SYLLABUS':
                if 'modules' in next_result:
                    merged['modules'].extend(next_result['modules'])
            elif doc_type == 'FORMULA':
                if 'formulas' in next_result:
                    for f in next_result['formulas']:
                        if 'latex' in f: f['latex'] = self._sanitize_content(f['latex'])
                    merged['formulas'].extend(next_result['formulas'])
            elif doc_type in ['NOTES', 'SHORT_NOTES']:
                if 'sections' in next_result:
                    for s in next_result['sections']:
                        for block in s.get('content_blocks', []):
                            if block.get('type') == 'text' and 'content' in block:
                                block['content'] = self._sanitize_content(block['content'])
                        
                        title_norm = s.get('section_title', '').strip().lower()
                        if title_norm not in seen_sections:
                            merged['sections'].append(s)
                            seen_sections.add(title_norm)
                        else:
                            # If section exists, merge blocks (avoid duplicate EXACT blocks)
                            existing_sec = next(sec for sec in merged['sections'] if sec.get('section_title', '').strip().lower() == title_norm)
                            
                            def _get_block_hash(b):
                                if b.get('type') == 'text':
                                    return hashlib.md5((b.get('content') or '').strip().encode()).hexdigest()
                                else:
                                    strategy = b.get('image_strategy') or ''
                                    details = b.get('image_details') or ''
                                    return hashlib.md5(f"IMG:{strategy}:{details}".encode()).hexdigest()

                            existing_block_hashes = {_get_block_hash(b) for b in existing_sec['content_blocks']}
                            for b in s.get('content_blocks', []):
                                b_hash = _get_block_hash(b)
                                if b_hash not in existing_block_hashes:
                                    existing_sec['content_blocks'].append(b)
                                    existing_block_hashes.add(b_hash)
        
        return merged

    async def _prepare_document_context(self, parsed_document_obj):
        """Helper to fetch all related data safely in a single thread-safe call."""
        def _get_data():
            subject = parsed_document_obj.subjects.select_related('branch', 'semester').first()
            if not subject:
                return None
            
            return {
                'branch_name': subject.branch.name if subject.branch else "N/A",
                'subject_code': subject.code,
                'subject_name': subject.name,
                'document_type_display': parsed_document_obj.get_document_type_display(),
                'source_text': parsed_document_obj.source_text,
                'source_file_name': parsed_document_obj.source_file.name if parsed_document_obj.source_file else None,
                'additional_images': [img.image.name for img in parsed_document_obj.images.all() if img.image]
            }
        
        return await asyncio.to_thread(_get_data)

    def _split_text(self, text: str, chunk_size: int = 5000) -> List[str]:
        """Splits large text into smaller chunks."""
        if not text:
            return []
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    async def _process_chunk_async(self, structured_llm, messages, chunk_idx, total_chunks, parsed_document_obj, semaphore):
        async with semaphore:
            max_retries = getattr(settings, 'AI_PARSER_RETRIES', 10)
            for attempt in range(max_retries):
                try:
                    print(f"Calling Gemini for Chunk {chunk_idx + 1}... (Attempt {attempt + 1})")
                    result = await structured_llm.ainvoke(messages)
                    
                    # Log result type for debugging
                    if hasattr(result, 'dict'):
                        return result.dict()
                    return result
                except Exception as e:
                    print(f"LLM Call failed for Chunk {chunk_idx + 1}: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise e

    async def parse_document(self, parsed_document_obj):
        schema_class = self.get_schema_for_type(parsed_document_obj.document_type)
        structured_llm = self.llm.with_structured_output(schema_class)
        
        doc_context = await self._prepare_document_context(parsed_document_obj)
        if not doc_context:
            raise ValueError(f"Document '{parsed_document_obj.title}' has no associated subjects or missing context.")

        base_system_prompt = parsed_document_obj.system_prompt.format(
            branch_name=doc_context['branch_name'],
            subject_code=doc_context['subject_code'],
            subject_name=doc_context['subject_name'],
            document_type=doc_context['document_type_display']
        )

        CONTENT_GUIDELINES = r"""
--- CONTENT FIDELITY & FORMATTING RULES ---
1. CRITICAL: PRESERVE ORIGINAL CONTENT. Do not paraphrase or summarize. Transcribe exactly.
2. DO NOT CHANGE DEFINITIONS. Transcribe exactly.
3. Use professional textbook LaTeX for ALL formulas.
4. CRITICAL LATEX DELIMITERS: 
   - ALWAYS use \\left( ... \\right), \\left[ ... \\right], or \\left\\{ ... \\right\\}.
   - NEVER use \\left{ (missing backslash). Curly braces MUST be escaped: \\left\\{ and \\right\\}.
5. SELECTIVE IMAGE EXTRACTION & RECREATION (CRITICAL):
   - ONLY use 'image' blocks for TRUE visual elements: Diagrams, Figures, Graphs, Charts.
   - NEVER use 'image' blocks for text, titles, or formulas.
   - COMPLEX/SIMPLE IMAGES: For ALL diagrams, create an 'image' block and populate the `image_strategy` and `image_details` fields by choosing exactly ONE best strategy:
     1. [SEARCH]: If the diagram is a standard textbook image. Provide keywords + source instructions in 'image_details'.
     2. [GEN_PROMPT]: If it's a unique drawing. Provide a highly technical prompt for Gemini (Imagen Pro) in 'image_details'.
     3. [CANVAS]: If it's a geometric or mathematical plot or just basic digram that can be easily recreated using code. Provide high-level logical instructions (not raw code) for an LLM to generate JS Canvas code in 'image_details' inclue all the labels you want and where to make exact recreation.
   - The AI must evaluate which of the 3 is the most effective for that specific image.
6. STRUCTURED SECTIONS & BLOCKS (For Notes):
   - Break notes into logical 'sections' with a descriptive 'section_title'.
   - Each section MUST have a list of 'content_blocks'.
   - A block 'type' is either 'text' (for Markdown) or 'image' (for recreation prompts).
7. AVOID REDUNDANCY:
   - Do not create a 'section' just for a title (e.g., "UNIT-3"). 
   - If a title is standalone, merge it into the next logical content section.
8. MARKDOWN TABLES:
   - Convert all tabular data into clean, well-formatted Markdown tables.
9. ALWAYS use \\frac{num}{den} instead of slashes (/) for division.
10. Use $$ ... $$ for standalone formulas. Use $ ... $ for inline math.
11. CRITICAL: The 'content' field in 'text' blocks MUST be PURE Markdown. NEVER include JSON.
12. CRITICAL PARALLEL CONTEXT:
   - If a block is labeled as "REFERENCE ONLY", it means it was parsed in the previous chunk.
   - Use it ONLY for continuity. DO NOT re-output content from "REFERENCE ONLY" blocks.
13. ZERO REPETITION POLICY (STRICT):
    - DO NOT transcribe the same sentence, formula, or concept multiple times.
    - If a formula is presented (e.g., $\tau = \mu \frac{du}{dy}$), do not repeat it in an 'array' or 'table' format immediately after unless it adds new information.
    - NO redundant explainers. If a variable is defined once, do not redefine it in the same section.
    - Be concise. One high-fidelity transcription is better than three repetitive ones.
14. CLEAN LATEX & LAYOUT:
    - Avoid using `\begin{array}` or `\left\{` to group simple definitions or bullet points.
    - Use standard Markdown lists for definitions.
    - ONLY use 'array' for actual matrices or multi-line aligned equations.
    - If a diagram includes text labels, merge those labels into the 'text' block description, do not create separate repetitive LaTeX blocks for them.
15. LATEX ROBUSTNESS & MATHJAX RENDERING (CRITICAL):
    - MATHJAX IS NOW USED FOR RENDERING. You are free to use standard `amsmath` environments (e.g., `\begin{align*}`, `\begin{bmatrix}`, `\begin{cases}`).
    - ESCAPING: Because your output passes through a Markdown parser before MathJax, you MUST use `\\\\` (four backslashes) for newlines inside matrices, arrays, and align blocks to ensure they survive and render correctly in HTML. 
    - AVOID `\boldsymbol` or `\pmboldsymbol` for Greek letters. Use standard Greek letters directly ($\sigma$, $\mu$).
    - DO NOT use obscure LaTeX packages. Stick to standard MathJax-supported AMSMath.
16. READABILITY & VERTICAL SPACING (CRITICAL):
    - NEVER cram multiple "Given", "Find", or "Solution" steps onto one line.
    - ALWAYS use `\n\n` (double newline) to force vertical spacing between EVERY step of a derivation or calculation.
    - Write ONE equation per line. Do not chain multiple distinct equations with "and" or commas on the same line.
    - Add horizontal spacing in LaTeX (like `\,` or `\quad`) if units and numbers are too close, e.g., $40 \text{ kN}$ instead of $40kN$.
    - Make the content extremely comfortable to read for a student.
-------------------------------------------
"""
        base_system_prompt += CONTENT_GUIDELINES

        content_blocks = []
        if doc_context['source_text']:
            for txt in self._split_text(doc_context['source_text']):
                content_blocks.append({"type": "text", "data": txt})

        if doc_context['source_file_name']:
            fname = doc_context['source_file_name']
            if fname.lower().endswith('.pdf'):
                pdf_images = await asyncio.to_thread(self._get_pdf_page_images, fname)
                for img_b64 in pdf_images:
                    content_blocks.append({"type": "image", "data": img_b64})
            elif fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                img_data = await asyncio.to_thread(self.encode_image, fname)
                content_blocks.append({"type": "image", "data": img_data})

        # Add additional DocumentImages
        for img_name in doc_context['additional_images']:
            img_data = await asyncio.to_thread(self.encode_image, img_name)
            content_blocks.append({"type": "image", "data": img_data})

        chunk_size = getattr(settings, 'AI_PARSER_CHUNK_SIZE', 5)
        max_concurrency = getattr(settings, 'AI_PARSER_MAX_CONCURRENCY', 5)
        semaphore = asyncio.Semaphore(max_concurrency)
        total_chunks = (len(content_blocks) + chunk_size - 1) // chunk_size

        # Set total chunks in DB
        def _set_total():
            from ..models import ParsedDocument
            ParsedDocument.objects.filter(id=parsed_document_obj.id).update(parsing_total_chunks=total_chunks)
        await asyncio.to_thread(_set_total)
        
        tasks = []
        completed_chunks = []
        
        async def _run_chunk(c, idx):
            res = await self._process_chunk_async(structured_llm, c, idx, total_chunks, parsed_document_obj, semaphore)
            
            # Discrete Step Tracking: Increment chunk counter atomically
            def _step_update():
                from ..models import ParsedDocument
                from django.db.models import F
                ParsedDocument.objects.filter(id=parsed_document_obj.id).update(
                    parsing_completed_chunks=F('parsing_completed_chunks') + 1
                )
            
            await asyncio.to_thread(_step_update)
            return res

        for i in range(0, len(content_blocks), chunk_size):
            overlap_size = getattr(settings, 'AI_PARSER_OVERLAP_SIZE', 1)
            start_idx = max(0, i - overlap_size)
            chunk = content_blocks[start_idx : i + chunk_size]
            chunk_idx = i // chunk_size
            
            human_content = []
            human_content.append({"type": "text", "text": "Parse this context. THE FIRST BLOCK MIGHT BE 'REFERENCE ONLY' - use it for continuity but do not re-extract its data."})
            
            for idx, block in enumerate(chunk):
                is_reference = (start_idx < i and idx == 0)
                label = "[REFERENCE ONLY - ALREADY PARSED]" if is_reference else "[EXTRACT THIS]"
                
                if block["type"] == "text":
                    human_content.append({"type": "text", "text": f"\n\n{label} TEXT BLOCK:\n{block['data']}"})
                else:
                    human_content.append({"type": "text", "text": label})
                    human_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{block['data']}"}})

            messages = [SystemMessage(content=base_system_prompt), HumanMessage(content=human_content)]
            tasks.append(_run_chunk(messages, chunk_idx))

        all_chunk_results = await asyncio.gather(*tasks)
        return self._merge_results(parsed_document_obj.document_type, all_chunk_results)
