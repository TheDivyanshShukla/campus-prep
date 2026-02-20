import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional

# Define the structured output schema for PYQs
class Question(BaseModel):
    unit: int = Field(description="The unit number (1-5) this question belongs to. If unknown, estimate.")
    marks: int = Field(description="The maximum marks for this question.")
    question_text: str = Field(description="The actual text of the question, preserving any LaTeX math formatting.")
    has_or_choice: bool = Field(description="True if this question is part of an OR choice.")
    part: Optional[str] = Field(description="e.g., 'a)', 'b)', 'i', if the question is broken down.")

class ExamPaper(BaseModel):
    subject_code: str = Field(description="Extracted subject code from the paper.")
    year: int = Field(description="The year the exam was conducted.")
    questions: List[Question] = Field(description="List of all extracted questions.")

class ContentParserService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gemini/gemini-2.5-flash",
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
        )
        # Bind the Pydantic schema so the LLM strictly returns JSON
        self.structured_llm = self.llm.with_structured_output(ExamPaper)

    def parse_pyq_text(self, raw_text: str) -> dict:
        """
        Takes raw OCR text from a PDF or Image and returns a strictly structured Python dict equivalent to ExamPaper.
        """
        system_prompt = (
            "You are an expert academic assistant for RGPV University engineering students. "
            "Your task is to take raw, messy OCR text from an exam paper and structure it perfectly. "
            "Make sure to preserve any mathematical equations using proper LaTeX formatting. "
            "Group questions by their logical 'OR' sections if present."
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Extract and structure the following exam paper:\n\n{text}")
        ])

        chain = prompt | self.structured_llm
        result = chain.invoke({"text": raw_text})
        
        # Return as dict to easily save into Django JSONField
        return result.model_dump()
