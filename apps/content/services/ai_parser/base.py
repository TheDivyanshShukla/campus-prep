import os
import json
import base64
import asyncio
import re
import hashlib
import fitz
from typing import List, Optional, Any, Union, Literal
from django.conf import settings
from django.core.files.storage import default_storage
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import httpx

# Shared Async HTTP Client for AI parsing connection pooling
_ai_parser_client = httpx.AsyncClient(timeout=60.0)

class BaseDocumentParser:
    CONTENT_GUIDELINES = r"""
--- UNIVERSAL FORMATTING & QUALITY RULES ---
1. CRITICAL: PRESERVE ORIGINAL CONTENT. Do not paraphrase or summarize. Transcribe exactly.
2. DO NOT CHANGE DEFINITIONS. Transcribe exactly (preserve professional English).
3. Use professional textbook LaTeX for ALL formulas.
4. CRITICAL LATEX DELIMITERS: 
   - ALWAYS use \\left( ... \\right), \\left[ ... \\right], or \\left\\{ ... \\right\\}.
   - NEVER use \\left{ (missing backslash). Curly braces MUST be escaped: \\left\\{ and \\right\\}.
5. SELECTIVE IMAGE EXTRACTION (UNIVERSAL):
   - ONLY include 'image' blocks for TRUE visual elements: Diagrams, Figures, Graphs, Charts.
   - NEVER use 'image' blocks for text, titles, or formulas.
6. MARKDOWN TABLES:
   - Convert all tabular data into clean, well-formatted Markdown tables.
7. LATEX ROBUSTNESS & MATHJAX RENDERING:
   - ALWAYS use \\frac{num}{den} instead of slashes (/) for division.
   - Use $$ ... $$ for standalone formulas. Use $ ... $ for inline math.
   - ESCAPING: Use `\\\\` (four backslashes) for newlines inside matrices, arrays, and align blocks to ensure they render correctly. 
9. READABILITY & VERTICAL SPACING (CRITICAL):
    - ALWAYS use `\n\n` (double newline) to force vertical spacing between EVERY step of a derivation or calculation.
    - Write ONE equation per line. Do not chain multiple distinct equations on the same line.
    - Add horizontal spacing in LaTeX (like `\,` or `\quad`) if units and numbers are too close.
10. DEDUPLICATION:
    - If a section or question appears identical to the "REFERENCE ONLY" blocks provided, do not re-extract it.
-------------------------------------------
"""

    def __init__(self, model_name: Optional[str] = None):
        if not model_name:
            model_name = getattr(settings, 'AI_PARSER_DEFAULT_MODEL', 'gemini/gemini-2.5-flash')
            
        self.llm = ChatOpenAI(
            model=model_name,
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
            http_async_client=_ai_parser_client,
        )

    def get_schema(self, doc_type: str):
        raise NotImplementedError("Subclasses must implement get_schema")

    def get_system_prompt(self, context: dict) -> str:
        raise NotImplementedError("Subclasses must implement get_system_prompt")

    def encode_image(self, image_name: str) -> str:
        with default_storage.open(image_name, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _get_pdf_page_images(self, pdf_name: str) -> List[str]:
        images = []
        try:
            with default_storage.open(pdf_name, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_bytes = pix.tobytes("jpg")
                    images.append(base64.b64encode(img_bytes).decode('utf-8'))
                doc.close()
        except Exception as e:
            print(f"Error converting PDF to images: {e}")
        return images

    def _sanitize_content(self, text: str) -> str:
        if not isinstance(text, str):
            return str(text)
        text = re.sub(r'\\left\s*\{', r'\\left\\{', text)
        text = re.sub(r'\\right\s*\}', r'\\right\\}', text)
        return text

    def _split_text(self, text: str, chunk_size: int = 5000) -> List[str]:
        if not text:
            return []
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    async def _process_chunk_async(self, structured_llm, messages, chunk_idx, total_chunks, semaphore):
        async with semaphore:
            max_retries = getattr(settings, 'AI_PARSER_RETRIES', 10)
            for attempt in range(max_retries):
                try:
                    print(f"Calling Gemini for Chunk {chunk_idx + 1}... (Attempt {attempt + 1})")
                    result = await structured_llm.ainvoke(messages)
                    return result.dict() if hasattr(result, 'dict') else result
                except Exception as e:
                    print(f"LLM Call failed for Chunk {chunk_idx + 1}: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise e

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        raise NotImplementedError("Subclasses must implement _merge_results")

    async def parse(self, parsed_document_obj):
        from apps.content.models import ParsedDocument
        from django.db.models import F
        
        doc_type = parsed_document_obj.document_type
        schema_class = self.get_schema(doc_type)
        structured_llm = self.llm.with_structured_output(schema_class)
        
        # Consolidate all ORM/database-heavy fetching into a single thread-safe block
        def _fetch_initial_data():
            subj = parsed_document_obj.subjects.select_related('branch', 'semester').first()
            imgs = [img.image.name for img in parsed_document_obj.images.all() if img.image]
            return subj, imgs

        subject, additional_images_paths = await asyncio.to_thread(_fetch_initial_data)
        
        context = {
            'branch_name': subject.branch.name if subject and subject.branch else "N/A",
            'subject_code': subject.code if subject else "N/A",
            'subject_name': subject.name if subject else "N/A",
            'document_type_display': parsed_document_obj.get_document_type_display(),
        }
        
        # Subclasses can add more to context
        if hasattr(self, 'get_extra_context'):
            context.update(await self.get_extra_context(parsed_document_obj, subject))
            
        system_prompt = self.get_system_prompt(context) + self.CONTENT_GUIDELINES
        
        content_blocks = []
        source_text = parsed_document_obj.source_text
        if source_text:
            for txt in self._split_text(source_text):
                content_blocks.append({"type": "text", "data": txt})
        
        if parsed_document_obj.source_file:
            fname = parsed_document_obj.source_file.name
            if fname.lower().endswith('.pdf'):
                images = await asyncio.to_thread(self._get_pdf_page_images, fname)
                for img in images: content_blocks.append({"type": "image", "data": img})
            else:
                img_data = await asyncio.to_thread(self.encode_image, fname)
                content_blocks.append({"type": "image", "data": img_data})

        # Process additional images fetched earlier
        for img_name in additional_images_paths:
            img_data = await asyncio.to_thread(self.encode_image, img_name)
            content_blocks.append({"type": "image", "data": img_data})

        chunk_size = getattr(settings, 'AI_PARSER_CHUNK_SIZE', 5)
        max_concurrency = getattr(settings, 'AI_PARSER_MAX_CONCURRENCY', 5)
        semaphore = asyncio.Semaphore(max_concurrency)
        total_chunks = (len(content_blocks) + chunk_size - 1) // chunk_size
        
        await asyncio.to_thread(ParsedDocument.objects.filter(id=parsed_document_obj.id).update, parsing_total_chunks=total_chunks)
        
        tasks = []
        async def _run_chunk(c, idx):
            res = await self._process_chunk_async(structured_llm, c, idx, total_chunks, semaphore)
            await asyncio.to_thread(ParsedDocument.objects.filter(id=parsed_document_obj.id).update, parsing_completed_chunks=F('parsing_completed_chunks') + 1)
            return res

        for i in range(0, len(content_blocks), chunk_size):
            overlap_size = getattr(settings, 'AI_PARSER_OVERLAP_SIZE', 1)
            start_idx = max(0, i - overlap_size)
            chunk = content_blocks[start_idx : i + chunk_size]
            chunk_idx = i // chunk_size
            
            human_content = [{"type": "text", "text": "Parse this context. THE FIRST BLOCK MIGHT BE 'REFERENCE ONLY' - use it for continuity but do not re-extract its data."}]
            for idx, block in enumerate(chunk):
                is_reference = (start_idx < i and idx == 0)
                label = "[REFERENCE ONLY - ALREADY PARSED]" if is_reference else "[EXTRACT THIS]"
                if block["type"] == "text":
                    human_content.append({"type": "text", "text": f"\n\n{label} TEXT BLOCK:\n{block['data']}"})
                else:
                    human_content.append({"type": "text", "text": label})
                    human_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{block['data']}"}})
            
            messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_content)]
            tasks.append(_run_chunk(messages, chunk_idx))

        results = await asyncio.gather(*tasks)
        return self._merge_results(doc_type, results)
