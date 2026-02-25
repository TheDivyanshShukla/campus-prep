from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class PYQQuestion(BaseModel):
    """
    Represents a single question extracted from a Previous Year Question (PYQ) paper.
    """
    unit: Optional[int] = Field(None, description="The unit number (1-5) this question belongs to. If not explicit, derive from SYLLABUS REFERENCE.")
    marks: int = Field(..., description="The marks assigned to this question as an integer.")
    question_text: str = Field(..., description="The full text of the question. Preserve original English phrasing and use LaTeX for math.")
    image_strategy: Optional[Literal['SEARCH', 'GEN_PROMPT', 'CANVAS']] = Field(
        None, 
        description="The chosen strategy to recreate a visual element. SET TO NULL IF NO IMAGE EXISTS IN SOURCE."
    )
    image_details: Optional[str] = Field(
        None, 
        description="A high-quality search query for 'SEARCH', drawing prompt for 'GEN_PROMPT', or logical instructions for 'CANVAS'."
    )
    part: Optional[str] = Field(None, description="The specific part of the question (e.g., 'a', 'b', 'c').")
    has_or_choice: bool = Field(False, description="True if this question is part of an 'OR' choice pair.")
    latex_answer: str = Field(..., description="A step-by-step detailed solution for the question using professional LaTeX.")

class ParsedPYQPaper(BaseModel):
    """
    A collection of questions forming a completed/solved PYQ paper.
    """
    questions: List[PYQQuestion]

class UnsolvedPYQQuestion(BaseModel):
    """
    A single question from an unsolved paper (no answer required).
    """
    unit: Optional[int] = Field(None, description="Derived or explicit unit number.")
    marks: int = Field(..., description="Marks for the question.")
    question_text: str = Field(..., description="Pristine question text with LaTeX.")
    image_strategy: Optional[Literal['SEARCH', 'GEN_PROMPT', 'CANVAS']] = Field(None, description="Strategy for image recreation. NULL if no image.")
    image_details: Optional[str] = Field(None, description="Prompt or search query for the image.")
    part: Optional[str] = Field(None, description="Question part identifier.")
    has_or_choice: bool = Field(False, description="Whether this question is an OR choice.")

class ParsedUnsolvedPYQPaper(BaseModel):
    """
    A collection of questions from an unsolved PYQ paper.
    """
    questions: List[UnsolvedPYQQuestion]

class SyllabusModule(BaseModel):
    """
    A single unit/module in a subject syllabus.
    """
    unit: int = Field(..., description="Unit number (usually 1-5).")
    title: str = Field(..., description="The title or name of the unit. Use LaTeX for math/symbols (e.g., '$\\\\lambda$ of Sodium').")
    topics: List[str] = Field(..., description="List of topics. Use LaTeX for ALL technical symbols, constants, and formulas.")

class ParsedSyllabus(BaseModel):
    """
    Full structured syllabus for a subject.
    """
    modules: List[SyllabusModule]
    experiments: Optional[List[str]] = Field(None, description="List of laboratory experiments or practicals if mentioned.")
    reference_books: Optional[List[str]] = Field(None, description="List of suggested reference books or textbooks.")

class NoteContentBlock(BaseModel):
    """
    A specific block of content within a section of notes.
    """
    type: Literal['text', 'image'] = Field(..., description="'text' for Markdown/LaTeX content, 'image' for diagram recreation.")
    content: Optional[str] = Field(None, description="PURE Markdown content. NEVER include JSON here. Use vertical spacing for readability.")
    image_strategy: Optional[Literal['SEARCH', 'GEN_PROMPT', 'CANVAS']] = Field(None, description="Strategy for diagram recreation. NULL if no image.")
    image_details: Optional[str] = Field(None, description="Prompt or keywords for the diagram.")

class NoteSection(BaseModel):
    """
    A logical section of notes with a title and content blocks.
    """
    section_title: str = Field(..., description="Descriptive title for the section (e.g., 'Unit 1: Introduction' or 'PN Junction').")
    content_blocks: List[NoteContentBlock]

class ParsedNotes(BaseModel):
    """
    Fully parsed academic notes structured in sections.
    """
    sections: List[NoteSection]

class AcademicFormula(BaseModel):
    """
    A mathematical or engineering formula with its name and LaTeX.
    """
    name: str = Field(..., description="The name of the formula or theorem.")
    latex: str = Field(..., description="The formula in standard LaTeX format.")

class ParsedFormulaSheet(BaseModel):
    """
    A sheet containing multiple extracted formulas.
    """
    formulas: List[AcademicFormula]

class ImportantQuestion(BaseModel):
    """
    A question identified as 'important' based on frequency or importance in the source.
    """
    text: str = Field(..., description="The question text.")
    frequency: Literal['High', 'Medium', 'Low'] = Field(..., description="Importance or frequency level.")

class ParsedImportantQs(BaseModel):
    """
    A collection of highly important questions.
    """
    questions: List[ImportantQuestion]
