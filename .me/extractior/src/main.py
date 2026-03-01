import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Add parent directory to path to import example schemas
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from example_schema import Syllabuss, SyllabusTOC, ParsedSyllabus

from extractor import PDFExtractor

import asyncio
import pymupdf4llm

async def async_main():
    # Reconfigure stdout to utf-8 to avoid charmap errors on windows
    sys.stdout.reconfigure(encoding='utf-8')
    # Load environment variables
    load_dotenv()
    
    # Configure LangChain model as per how_to_use_llm.py
    llm = ChatOpenAI(
        model="cerebras/gpt-oss-120b",
        openai_api_base="https://bifrost.naravirtual.in/langchain",
        openai_api_key="dummy-key",
        default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
    )

    # Initialize Extractor
    extractor = PDFExtractor(llm)

    # Location of testing PDF
    pdf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "example-pdf", "syllabus.pdf")
    
    if not os.path.exists(pdf_path):
        print(f"Error: Could not find PDF file at {pdf_path}")
        return

    print(f"Parsing PDF to text...")
    try:
        # Parse PDF text once to share across async tasks
        md_text = pymupdf4llm.to_markdown(pdf_path)
    except Exception as e:
        print(f"Failed to read PDF: {e}")
        return

    print("Step 1: Extracting Subject Index (TOC)...")
    try:
        toc_instructions = (
            "Scan the entire syllabus document and extract ONLY a list of all subjects. "
            "Return the subject code and subject name for every single course mentioned. "
            "Do not extract topics or modules yet."
        )
        # Use aextract for TOC too
        toc_result = await extractor.aextract(
            md_text=md_text,
            schema=SyllabusTOC,
            instructions=toc_instructions
        )
        
        print(f"Found {len(toc_result.subjects)} subjects in the TOC.\n")
        
        # Step 2: Extract Details per Subject asynchronously tasks
        print("Step 2: Starting parallel extraction for all subjects...")
        
        async def extract_single_subject(subject_ref, idx, total):
            detail_instructions = (
                f"Extract the complete syllabus details ONLY for the subject "
                f"'{subject_ref.subject_name}' (Code: {subject_ref.subject_code}).\n"
                "You MUST fill out 'modules', 'topics', 'experiments', and 'reference_books' for this subject completely. "
                "Do not truncate anything. Ignore all other subjects in the document."
            )
            try:
                res = await extractor.aextract(
                    md_text=md_text,
                    schema=ParsedSyllabus,
                    instructions=detail_instructions
                )
                print(f"  [✔] Finished: {subject_ref.subject_code}")
                return res
            except Exception as e:
                print(f"  [✖] Failed {subject_ref.subject_code}: {e}")
                return None
                
        # Gather all extraction tasks
        tasks = [extract_single_subject(ref, i, len(toc_result.subjects)) for i, ref in enumerate(toc_result.subjects, 1)]
        results = await asyncio.gather(*tasks)
        
        # Filter out failed extractions
        final_subjects = [r for r in results if r is not None]
        
        # Step 3: Combine and Save
        final_result = Syllabuss(subjects=final_subjects)
        
        print("\nAll extractions complete. Saving to res.json...")
        with open("res.json", "w", encoding="utf-8") as f:
            f.write(final_result.model_dump_json(indent=2))
        
    except Exception as e:
        print(f"Process failed: {e}")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
