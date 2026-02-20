import os
import json
import base64
from dotenv import load_dotenv
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional

# Load environment variables
load_dotenv()

# --- 1. Define the exact JSON schema we want using Pydantic ---
class PYQQuestion(BaseModel):
    unit: Optional[int] = Field(description="The unit number this question belongs to, if identifiable. Usually 1 to 5.", default=None)
    marks: int = Field(description="The marks awarded for this question (e.g., 7 or 14).")
    question_text: str = Field(description="The theoretical question or problem statement.")
    part: Optional[str] = Field(description="The sub-part label, like 'a)' or 'b)'.", default=None)
    has_or_choice: bool = Field(description="True if this question is part of an 'OR' grouping.", default=False)
    latex_answer: str = Field(description="A highly accurate, extremely detailed step-by-step solution formatted with Markdown and KaTeX ($ or $$ delimiters) for math formulas.")

class ParsedPYQPaper(BaseModel):
    questions: List[PYQQuestion] = Field(description="A comprehensive list of all questions extracted from the provided text.")

# --- 2. Configure the Bifrost LLM Client ---
llm = ChatOpenAI(
    model="gemini/gemini-2.5-flash",
    openai_api_base="https://bifrost.naravirtual.in/langchain",
    openai_api_key="dummy-key",
    default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
    temperature=0.2, # Low temperature for analytical accuracy
)

# Enforce the structured Pydantic output
structured_llm = llm.with_structured_output(ParsedPYQPaper)

# --- 3. Define the Extraction Prompts & Helpers ---
SYSTEM_PROMPT = """You are an elite expert AI parser specializing in Engineering Academic exams.
Your task is to extract exact questions from raw exam papers (provided as text or images) and generate pristine, highly-accurate, step-by-step solutions for them.
You MUST output valid JSON conforming strictly to the provided schema.
For 'latex_answer', use Markdown for normal text and wrap ANY math in KaTeX delimiters ($ for inline, $$ for block formulas)."""

# Helper to encode images
def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def parse_with_image(image_path: str, additional_text: str = "") -> ParsedPYQPaper:
    base64_image = encode_image(image_path)
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=[
                {"type": "text", "text": "Extract all questions from this image and solve them." + ("\n" + additional_text if additional_text else "")},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    },
                },
            ]
        )
    ]
    
    # Pass the messages directly to the structured LLM
    print(f"Sending vision request to Gemini for image: {image_path}...")
    return structured_llm.invoke(messages)

def parse_text_only(raw_text: str) -> ParsedPYQPaper:
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Here is the raw exam text snippet:\n\n{raw_text}")
    ])
    chain = prompt | structured_llm
    return chain.invoke({"raw_text": raw_text})

if __name__ == "__main__":
    # --- 4. Test the pipeline ---
    
    # 4A. Test Text Parsing
    test_snippet = """
    Q.1 a) Define Heisenberg's Uncertainty Principle. Give its physical significance. (7 Marks)
    b) Calculate the de-Broglie wavelength of an electron accelerated through 50 Volts. (7 Marks)
    OR
    Q.2 a) Explain the construction and working of Ruby Laser with neat energy level diagram. (14 Marks)
    """

    print("Analyzing and synthesizing test text snippet via Bifrost/Gemini...")
    try:
        result = parse_text_only(test_snippet)
        print("\n--- Parsed Text Output ---")
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(f"Text Error occurred: {e}")
        
    # 4B. Test Vision Parsing (If an image exists in the test directory)
    # create a dummy image if we want to test locally or prompt user
    print("\n\nNote: To test Vision, call `parse_with_image('path_to_exam_screenshot.jpg')`")
