from pydantic import BaseModel, Field
from typing import List

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
    subject_name: str = Field(..., description="The name of the subject.")
    subject_code: str = Field(..., description="The code of the subject. ex (BT201, BT202, etc)")
    subject_type: str = Field(..., description="The type of the subject. ex (Theory, Practical, etc)")
    modules: List[SyllabusModule]
    experiments: List[str] = Field(default_factory=list, description="List of laboratory experiments or practicals listed in the syllabus.")
    reference_books: List[str] = Field(default_factory=list, description="List of suggested reference books, authors, or textbooks.")
    extra: str|None = Field(None, description="Extra information if given.")


class Syllabuss(BaseModel):
    subjects: List[ParsedSyllabus]

class SubjectIndex(BaseModel):
    """
    A minimal index entry to identify a subject in the document.
    """
    subject_code: str = Field(..., description="The code of the subject (e.g. BT101).")
    subject_name: str = Field(..., description="The name of the subject.")

class SyllabusTOC(BaseModel):
    """
    Table of Contents containing all subjects.
    """
    subjects: List[SubjectIndex]