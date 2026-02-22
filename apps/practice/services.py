import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


# ── Pydantic schemas for structured AI output ────────────────────────────────

class MCQOptions(BaseModel):
    a: str = Field(description="Option A text (Markdown/LaTeX allowed)")
    b: str = Field(description="Option B text")
    c: str = Field(description="Option C text")
    d: str = Field(description="Option D text")
    correct: str = Field(description="Correct option letter: A, B, C or D")


class PracticeQuestionSchema(BaseModel):
    question_type: str = Field(
        description="One of: MCQ, SHORT, LONG, FILL, TF"
    )
    difficulty: str = Field(
        description="One of: EASY, MEDIUM, HARD"
    )
    body_md: str = Field(
        description="Question text in Markdown. Wrap inline math in $...$, block math in $$...$$."
    )
    mcq_options: Optional[MCQOptions] = Field(
        default=None,
        description="Required only for MCQ type questions."
    )
    correct_answer: str = Field(
        description=(
            "For MCQ: single letter 'A', 'B', 'C', or 'D'. "
            "For TF: 'True' or 'False'. "
            "For FILL: the exact blank word/phrase. "
            "For SHORT/LONG: a concise model answer in Markdown."
        )
    )
    explanation_md: str = Field(
        description="Step-by-step explanation of the correct answer. Markdown + LaTeX allowed."
    )


class PracticeQuestionList(BaseModel):
    questions: List[PracticeQuestionSchema]


# ── Service ────────────────────────────────────────────────────────────────────

class PracticeAIService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gemini/gemini-2.5-flash",
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
            temperature=0.7,
        )
        self.structured_llm = self.llm.with_structured_output(PracticeQuestionList)

    def generate(
        self,
        subject_name: str,
        unit_name: Optional[str],
        question_types: List[str],
        difficulty: str,
        count: int = 10,
    ) -> List[PracticeQuestionSchema]:
        """
        Generate `count` practice questions using Gemini via Bifrost.
        Returns a list of PracticeQuestionSchema objects.
        """
        scope = f"Unit: {unit_name}" if unit_name else "entire subject (all units)"
        types_readable = ", ".join(question_types)

        system_prompt = (
            "You are an expert academic question setter for RGPV University Engineering exams. "
            "Generate high-quality, exam-relevant practice questions. "
            "Use proper Markdown formatting. "
            "For any mathematical expressions, ALWAYS use LaTeX: $...$ for inline, $$...$$ for block. "
            "All question text, options, and explanations must be in English only. "
            "Explanations must be detailed and educational."
        )

        user_prompt = (
            f"Generate exactly {count} practice questions for:\n"
            f"Subject: {subject_name}\n"
            f"Scope: {scope}\n"
            f"Question types to generate: {types_readable}\n"
            f"Overall difficulty: {difficulty}\n\n"
            f"Mix the requested question types proportionally. "
            f"Make sure MCQ options are plausible distractors. "
            f"For FILL questions, make the blank clearly indicated with ___. "
            f"Ensure coverage of important concepts."
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt),
        ])
        chain = prompt | self.structured_llm
        result: PracticeQuestionList = chain.invoke({})
        return result.questions
