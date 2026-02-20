import os
import json
import base64
import fitz # PyMuPDF for PDF extraction
import base64
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
            question_text: str
            part: Optional[str] = None
            has_or_choice: bool = False
            latex_answer: str
        
        class ParsedPYQPaper(BaseModel):
            questions: List[PYQQuestion]
        return ParsedPYQPaper

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

    def parse_document(self, parsed_document_obj):
        schema = self.get_schema_for_type(parsed_document_obj.document_type)
        structured_llm = self.llm.with_structured_output(schema)
        
        system_prompt = parsed_document_obj.system_prompt
        
        # Format the system prompt template with the object context
        system_prompt = system_prompt.format(
            branch_name=parsed_document_obj.subject.branch.name,
            subject_code=parsed_document_obj.subject.code,
            subject_name=parsed_document_obj.subject.name,
            document_type=parsed_document_obj.get_document_type_display()
        )

        messages = [SystemMessage(content=system_prompt)]
        human_content = []

        # 1. Attach text if exists
        human_text = "Please fully parse the provided context into the strict JSON schema."
        if parsed_document_obj.source_text:
            human_text += f"\n\nRAW TEXT CONTEXT:\n{parsed_document_obj.source_text}"
        
        human_content.append({"type": "text", "text": human_text})

        # 2. Attach main source_file if it's an image or PDF
        if parsed_document_obj.source_file:
            path = parsed_document_obj.source_file.path
            # basic check for image
            if path.lower().endswith(('.png', '.jpg', '.jpeg')):
                b64 = self.encode_image(path)
                human_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            elif path.lower().endswith('.pdf'):
                # Extract text using PyMuPDF
                try:
                    doc = fitz.open(path)
                    pdf_text = f"\n\n--- EXTRACTED TEXT FROM PDF ({parsed_document_obj.source_file.name}) ---\n"
                    for page in doc:
                        pdf_text += page.get_text()
                    doc.close()
                    human_content[0]["text"] += pdf_text
                except Exception as e:
                    print(f"Failed to extract PDF text: {e}")
                
        # 3. Attach additional DocumentImages
        for doc_image in parsed_document_obj.images.all():
            if doc_image.image:
                b64 = self.encode_image(doc_image.image.path)
                human_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        messages.append(HumanMessage(content=human_content))
        
        print(f"Calling Gemini with Schema {schema.__name__}...")
        result = structured_llm.invoke(messages)
        return result.model_dump()
