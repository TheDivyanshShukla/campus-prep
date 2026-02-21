import os
import json
import base64
import time
import fitz # PyMuPDF for PDF extraction
from pathlib import Path
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, create_model

# Import our Pydantic schemas (we'll define a quick factory or standard schemas)
from typing import List, Optional, Any

class DocumentParserService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gemini/gemini-2.5-flash",
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
            temperature=0.2,
        )

    def encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def get_schema_for_type(self, doc_type: str):
        # Depending on doc_type, return different Pydantic models to enforce structure
        if doc_type == 'PYQ':
            return self._pyq_schema()
        elif doc_type == 'UNSOLVED_PYQ':
            return self._unsolved_pyq_schema()
        elif doc_type == 'SYLLABUS':
            return self._syllabus_schema()
        elif doc_type == 'IMPORTANT_Q':
            return self._important_q_schema()
        elif doc_type == 'FORMULA':
            return self._formula_schema()
        else: # NOTES, SHORT_NOTES, CRASH_COURSE
            return self._notes_schema()

    def _pyq_schema(self):
        class PYQQuestion(BaseModel):
            unit: Optional[int] = None
            marks: int
            question_text: str # MUST contain full markdown and LaTeX math formulas.
            image_recreation_prompt: Optional[str] = None # Complete prompt for generative AI or Canvas to exactly recreate any image/diagram in this question.
            part: Optional[str] = None
            has_or_choice: bool = False
            latex_answer: str
        
        class ParsedPYQPaper(BaseModel):
            questions: List[PYQQuestion]
        return ParsedPYQPaper

    def _unsolved_pyq_schema(self):
        class UnsolvedPYQQuestion(BaseModel):
            unit: Optional[int] = None
            marks: int
            question_text: str # MUST contain full markdown and LaTeX math formulas.
            image_recreation_prompt: Optional[str] = None # Complete prompt for generative AI or Canvas to exactly recreate any image/diagram in this question.
            part: Optional[str] = None
            has_or_choice: bool = False
            
        class ParsedUnsolvedPYQPaper(BaseModel):
            questions: List[UnsolvedPYQQuestion]
        return ParsedUnsolvedPYQPaper

    def _syllabus_schema(self):
        class SyllabusModule(BaseModel):
            unit: int
            topics: List[str]
            
        class ParsedSyllabus(BaseModel):
            modules: List[SyllabusModule]
        return ParsedSyllabus

    def _notes_schema(self):
        class ParsedNotes(BaseModel):
            title: str
            content: str # containing full markdown & latex
        return ParsedNotes

    def _formula_schema(self):
        class AcademicFormula(BaseModel):
            name: str
            latex: str
        class ParsedFormulaSheet(BaseModel):
            formulas: List[AcademicFormula]
        return ParsedFormulaSheet

    def _important_q_schema(self):
        class ImportantQuestion(BaseModel):
            text: str
            frequency: str # e.g., 'High', 'Medium'
        class ParsedImportantQs(BaseModel):
            questions: List[ImportantQuestion]
        return ParsedImportantQs

    def _get_pdf_page_images(self, pdf_path: str) -> List[str]:
        """Convert PDF pages to base64 images."""
        images = []
        try:
            doc = fitz.open(pdf_path)
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # Higher resolution for better OCR
                img_bytes = pix.tobytes("jpg")
                images.append(base64.b64encode(img_bytes).decode('utf-8'))
            doc.close()
        except Exception as e:
            print(f"Error converting PDF to images: {e}")
        return images

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        """Merges multiple chunk results into a single structured dictionary."""
        if not all_results:
            return {}
        
        merged = all_results[0].copy()
        
        for next_result in all_results[1:]:
            if doc_type in ['PYQ', 'UNSOLVED_PYQ', 'IMPORTANT_Q']:
                if 'questions' in next_result:
                    merged['questions'].extend(next_result['questions'])
            elif doc_type == 'SYLLABUS':
                if 'modules' in next_result:
                    merged['modules'].extend(next_result['modules'])
            elif doc_type == 'FORMULA':
                if 'formulas' in next_result:
                    merged['formulas'].extend(next_result['formulas'])
            elif doc_type in ['NOTES', 'SHORT_NOTES']:
                if 'content' in next_result:
                    merged['content'] += "\n\n" + next_result['content']
        
        return merged

    def parse_document(self, parsed_document_obj):
        schema = self.get_schema_for_type(parsed_document_obj.document_type)
        structured_llm = self.llm.with_structured_output(schema)
        
        system_prompt_template = parsed_document_obj.system_prompt
        
        # 0. Safety Check: Ensure document has at least one subject
        subject = parsed_document_obj.subjects.first()
        if not subject:
            raise ValueError(f"Document '{parsed_document_obj.title}' has no associated subjects.")

        # Format the system prompt template with the object context
        base_system_prompt = system_prompt_template.format(
            branch_name=subject.branch.name,
            subject_code=subject.code,
            subject_name=subject.name,
            document_type=parsed_document_obj.get_document_type_display()
        )

        # LaTeX Excellence Guidelines (Injected to ensure "crispy" notes)
        LATEX_GUIDELINES = """
--- MATH FORMATTING RULES ---
1. Use professional textbook LaTeX for ALL formulas.
2. ALWAYS use \\frac{num}{den} instead of slashes (/) for division.
3. ALWAYS use \\text{} for non-variable subscripts or labels (e.g., \\rho_{\\text{std}}).
4. Group multi-character exponents and subscripts in curly braces (e.g., a^{2n+1}).
5. Use $$ ... $$ for standalone, important derivation steps or final formulas.
6. Ensure Markdown is extremely clean, structured, and easy to read.
----------------------------
"""
        base_system_prompt += LATEX_GUIDELINES

        all_images = []
        # 1. Convert main source_file PDF to images if needed
        if parsed_document_obj.source_file and parsed_document_obj.source_file.path.lower().endswith('.pdf'):
            print(f"Converting PDF {parsed_document_obj.source_file.name} to images...")
            all_images.extend(self._get_pdf_page_images(parsed_document_obj.source_file.path))
        elif parsed_document_obj.source_file and parsed_document_obj.source_file.path.lower().endswith(('.png', '.jpg', '.jpeg')):
            all_images.append(self.encode_image(parsed_document_obj.source_file.path))

        # 2. Add additional DocumentImages
        for doc_image in parsed_document_obj.images.all():
            if doc_image.image:
                all_images.append(self.encode_image(doc_image.image.path))

        # 3. Chunked Processing (5 pages at a time)
        chunk_size = 5
        all_chunk_results = []
        rolling_context = "" # To maintain continuity between chunks

        for i in range(0, len(all_images), chunk_size):
            chunk = all_images[i:i + chunk_size]
            current_chunk_num = (i // chunk_size) + 1
            total_chunks = (len(all_images) + chunk_size - 1) // chunk_size
            
            print(f"Processing Chunk {current_chunk_num}/{total_chunks}...")
            
            chunk_system_prompt = base_system_prompt
            if rolling_context:
                chunk_system_prompt += f"\n\n--- PREVIOUS CONTEXT (Tail of previous chunk) ---\n{rolling_context}\n--- END PREVIOUS CONTEXT ---\nContinue from exactly where the previous context left off. Do not repeat titles or intro if already covered."

            human_content = []
            human_text = "Please fully parse the provided context into the strict JSON schema. Use Vision to read any text and describe any diagrams."
            if parsed_document_obj.source_text and i == 0:
                human_text += f"\n\nRAW TEXT CONTEXT:\n{parsed_document_obj.source_text}"
            
            human_content.append({"type": "text", "text": human_text})
            for img_b64 in chunk:
                human_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})

            messages = [
                SystemMessage(content=chunk_system_prompt),
                HumanMessage(content=human_content)
            ]

            # 3.1 Retry Logic for LLM Call
            max_retries = getattr(settings, 'AI_PARSER_RETRIES', 3)
            result = None
            for attempt in range(max_retries):
                try:
                    print(f"Calling Gemini... (Attempt {attempt + 1}/{max_retries})")
                    result = structured_llm.invoke(messages)
                    break
                except Exception as e:
                    print(f"LLM Call failed (Attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt # Exponential backoff
                        print(f"Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        raise e

            chunk_data = result.model_dump()
            all_chunk_results.append(chunk_data)

            # Update rolling context for continuity (last 500 chars of content if it's notes)
            if parsed_document_obj.document_type in ['NOTES', 'SHORT_NOTES']:
                rolling_context = chunk_data.get('content', '')[-500:]
            elif 'questions' in chunk_data and chunk_data['questions']:
                last_q = chunk_data['questions'][-1]
                rolling_context = f"Last extracted question was: {last_q.get('question_text', '')[:200]}..."

        # 4. Final Merging
        final_result = self._merge_results(parsed_document_obj.document_type, all_chunk_results)
        return final_result
