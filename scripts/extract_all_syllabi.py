import os
import sys
import asyncio
import json
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Add the extractor paths to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTOR_DIR = os.path.join(BASE_DIR, ".me", "extractior")
EXTRACTOR_SRC = os.path.join(EXTRACTOR_DIR, "src")

sys.path.append(EXTRACTOR_DIR)
sys.path.append(EXTRACTOR_SRC)

from example_schema import SyllabusTOC, ParsedSyllabus, Syllabuss
from extractor import PDFExtractor
import pymupdf4llm

# Configuration
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
OUTPUT_DIR = os.path.join(BASE_DIR, "extracted_data")
SEM = asyncio.Semaphore(5)  # Max concurrent extractions

def cleanup_orphaned_json():
    """Removes JSON files that no longer have a corresponding PDF."""
    print("Cleaning up orphaned JSON files in extracted_data...")
    if not os.path.exists(OUTPUT_DIR):
        return
        
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for file in files:
            if file.endswith(".json"):
                rel_path = os.path.relpath(root, OUTPUT_DIR)
                pdf_name = file.replace(".json", ".pdf")
                pdf_path = os.path.join(DOWNLOADS_DIR, rel_path, pdf_name) # Corrected to use DOWNLOADS_DIR
                
                if not os.path.exists(pdf_path):
                    json_path = os.path.join(root, file)
                    print(f"  Removing orphaned JSON: {json_path}")
                    os.remove(json_path)

# Limit concurrency to avoid overloading the API
SEMAPHORE_LIMIT = 50

async def process_pdf(extractor, pdf_path, output_path, semaphore):
    async with semaphore:
        print(f"Processing: {pdf_path}")
        try:
            is_first_year = "first_year" in pdf_path.lower()
            
            # 1. Parse PDF to Markdown
            md_text = pymupdf4llm.to_markdown(pdf_path)
            
            # 2. Extract TOC
            toc_instructions = (
                "Scan the entire syllabus document and extract ONLY a list of all subjects. "
                "Return the subject code and subject name for every single course mentioned. "
                "Do not extract topics or modules yet. "
            )
            if is_first_year:
                toc_instructions += "This is a First Year syllabus which is divided into Group A and Group B. Extract all subjects from both groups."

            toc_result = await extractor.aextract(
                md_text=md_text,
                schema=SyllabusTOC,
                instructions=toc_instructions
            )
            
            if not toc_result.subjects:
                print(f"  [!] No subjects found in TOC for {pdf_path}")
                return

            # 3. Extract Details per subject
            async def extract_single_subject(subject_ref):
                detail_instructions = (
                    f"Extract the complete syllabus details ONLY for the subject "
                    f"'{subject_ref.subject_name}' (Code: {subject_ref.subject_code}).\n"
                    "You MUST fill out 'modules', 'topics', 'experiments', and 'reference_books' for this subject completely. "
                    "Do not truncate anything. Ignore all other subjects in the document."
                )
                if is_first_year:
                    detail_instructions += (
                        "\nIMPORTANT: This is a FIRST YEAR subject. "
                        "Determine if it belongs to 'Group A', 'Group B', or 'Common' based on the document's tables. "
                        "Put this Group information in the 'extra' field."
                    )
                try:
                    return await extractor.aextract(
                        md_text=md_text,
                        schema=ParsedSyllabus,
                        instructions=detail_instructions
                    )
                except Exception as e:
                    print(f"    [✖] Failed {subject_ref.subject_code}: {e}")
                    return None

            tasks = [extract_single_subject(ref) for ref in toc_result.subjects]
            subject_results = await asyncio.gather(*tasks)
            
            final_subjects = [r for r in subject_results if r is not None]
            final_result = Syllabuss(subjects=final_subjects)
            
            # 4. Save
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_result.model_dump_json(indent=2))
            
            print(f"  [✔] Saved to {output_path}")
            
        except Exception as e:
            print(f"  [✖] Error processing {pdf_path}: {e}")

async def main():
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    cleanup_orphaned_json()
    
    # Configure LLM (matching the user's config)
    llm = ChatOpenAI(
        model="cerebras/gpt-oss-120b",
        openai_api_base="https://bifrost.naravirtual.in/langchain",
        openai_api_key="dummy-key",
        default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
        max_retries=70
    )
    
    extractor = PDFExtractor(llm)
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    
    tasks = []
    
    for root, dirs, files in os.walk(DOWNLOADS_DIR):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                
                # Create relative path for output
                rel_path = os.path.relpath(pdf_path, DOWNLOADS_DIR)
                json_filename = os.path.splitext(rel_path)[0] + ".json"
                output_path = os.path.join(OUTPUT_DIR, json_filename)
                
                if os.path.exists(output_path):
                    # print(f"Skipping (already exists): {json_filename}")
                    continue
                
                tasks.append(process_pdf(extractor, pdf_path, output_path, semaphore))
    
    if not tasks:
        print("No new PDFs to process.")
        return

    print(f"Found {len(tasks)} PDFs to process. Starting extraction...")
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
