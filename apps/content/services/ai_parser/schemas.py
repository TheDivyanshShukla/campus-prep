from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class PYQQuestion(BaseModel):
    """
    Represents a single question extracted from a Previous Year Question (PYQ) paper.
    """
    unit: Optional[int] = Field(None, description="The syllabus unit number (e.g. 1, 2, 3, 4, 5) this question belongs to. Derive from subject context if possible.")
    marks: int = Field(..., description="The marks assigned to this question (e.g. 7, 10, 14).")
    question_text: str = Field(..., description="The full English text of the question. MUST use professional LaTeX for ANY mathematical symbols, formulas, or technical notation.")
    image_strategy: Optional[Literal['SEARCH', 'GEN_PROMPT', 'CANVAS']] = Field(
        None, 
        description="Choice of recreation strategy: 'CANVAS' for diagrams/charts, 'SEARCH' for realistic images. SET TO NULL if no visual exists."
    )
    image_details: Optional[str] = Field(
        None, 
        description="For 'CANVAS': extremely detailed technical description for recreation. For 'SEARCH': target keywords."
    )
    part: Optional[str] = Field(None, description="Sub-part identifier like 'a', 'b', or 'i'.")
    has_or_choice: bool = Field(False, description="True if this specific question is part of an 'OR'/Internal choice pair.")
    latex_answer: str = Field(..., description="Crystal-clear, step-by-step detailed solution. Use professional LaTeX for ALL math. Use double newlines for vertical spacing.")

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
    unit: int = Field(..., description="Unit or Module number (e.g. 1, 2, 3, 4, 5).")
    title: str = Field(..., description="The unit title. Use LaTeX for math/symbols (e.g. '$\\\\sigma$ notation').")
    topics: List[str] = Field(..., description="Atomic list of topics. Use professional English and LaTeX for all technical terms.")

class ParsedSyllabus(BaseModel):
    """
    Full structured syllabus for a subject.
    """
    modules: List[SyllabusModule]
    experiments: List[str] = Field(default_factory=list, description="List of laboratory experiments or practicals listed in the syllabus.")
    reference_books: List[str] = Field(default_factory=list, description="List of suggested reference books, authors, or textbooks.")

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
