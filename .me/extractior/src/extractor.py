import pymupdf4llm
from pydantic import BaseModel
from typing import Type, TypeVar
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

T = TypeVar('T', bound=BaseModel)

class PDFExtractor:
    """
    A utility class to extract structured data from PDF files using pymupdf4llm and LangChain.
    """
    def __init__(self, llm: BaseChatModel):
        """
        Initialize the extractor with a LangChain chat model.
        """
        self.llm = llm

    def extract(self, file_path: str, schema: Type[T], instructions: str = "") -> T:
        """
        Parses a PDF file to markdown using pymupdf4llm, then uses the provided LLM
        to extract information matching the given Pydantic schema.
        
        Args:
            file_path: Path to the PDF file.
            schema: The Pydantic model class defining the desired output structure.
            instructions: Additional instructions to guide the LLM's extraction.
            
        Returns:
            An instance of the provided schema with the extracted data.
        """
        # 1. Parse the PDF into Markdown using pymupdf4llm
        try:
            md_text = pymupdf4llm.to_markdown(file_path)
        except Exception as e:
            raise ValueError(f"Failed to parse PDF file at {file_path}: {e}")

        # 2. Create the prompt template
        system_prompt = (
            "You are an expert data extraction assistant.\n"
            "Your task is to extract information from the provided document and match it strictly to the required schema.\n"
        )
        if instructions:
            system_prompt += f"\nAdditional Instructions:\n{instructions}\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Here is the document content:\n\n{document_content}\n\nPlease extract the information according to the schema.")
        ])

        # 3. Create the extraction chain enforcing the schema
        # with_structured_output uses function calling or JSON mode to guarantee the output matches the Pydantic schema
        chain = prompt | self.llm.with_structured_output(schema)
        
        # 4. Invoke the chain to get the structured output
        result = chain.invoke({
            "document_content": md_text
        })
        
        return result

    async def aextract(self, md_text: str, schema: Type[T], instructions: str = "") -> T:
        """
        Asynchronously uses the provided LLM to extract information matching the given
        Pydantic schema from the provided markdown text. (Text parsing should be done before).
        """
        # Create the prompt template
        system_prompt = (
            "You are an expert data extraction assistant.\n"
            "Your task is to extract information from the provided document and match it strictly to the required schema.\n"
        )
        if instructions:
            system_prompt += f"\nAdditional Instructions:\n{instructions}\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Here is the document content:\n\n{document_content}\n\nPlease extract the information according to the schema.")
        ])

        # Create the extraction chain
        chain = prompt | self.llm.with_structured_output(schema)
        
        # Invoke the chain asynchronously
        result = await chain.ainvoke({
            "document_content": md_text
        })
        
        return result
