import asyncio
from typing import List
from .base import BaseDocumentParser
from .schemas import ParsedSyllabus

class SyllabusParser(BaseDocumentParser):
    def get_schema(self, doc_type=None):
        return ParsedSyllabus

    def get_system_prompt(self, context: dict) -> str:
        return f"""You are an elite expert AI parser specializing in Academic Syllabi for RGPV University.
        
CONTEXT:
Subject: {context.get('subject_code')} - {context.get('subject_name')}

YOUR TASK:
Extract the module/unit structure, experiments, and reference books.

--- SPECIAL RULES FOR SYLLABUS ---
1. MODULES: Extract module unit number, title, and detailed topics.
2. LATEX: ALWAYS use LaTeX for mathematical symbols ($\lambda$, $\sigma$), formulas, and professional terms.
3. EXPERIMENTS: Extract the "List of Experiment" as a flat list of strings. Use LaTeX where needed.
4. BOOKS: Extract "Suggested Reference Books" as a flat list.
5. CLEANING: Remove administrative text (e.g. "8 lectures", "w.e.f.").

CONSTRAINTS:
1. ONLY English text.
2. Output valid JSON matching the schema.
"""

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        if not all_results: return {}
        
        merged = {
            "modules": [],
            "experiments": [],
            "reference_books": []
        }
        
        seen_units = set()
        seen_experiments = set()
        seen_books = set()
        
        for res in all_results:
            if not res: continue
            
            # Merge Modules
            for mod in res.get('modules', []):
                mod['title'] = self._sanitize_content(mod.get('title', ''))
                if mod['unit'] not in seen_units:
                    merged['modules'].append(mod)
                    seen_units.add(mod['unit'])
            
            # Merge Experiments
            for exp in res.get('experiments', []) or []:
                exp = self._sanitize_content(exp)
                norm = exp.strip().lower()
                if norm and norm not in seen_experiments:
                    merged['experiments'].append(exp)
                    seen_experiments.add(norm)
                    
            # Merge Books
            for book in res.get('reference_books', []) or []:
                norm = book.strip().lower()
                if norm and norm not in seen_books:
                    merged['reference_books'].append(book)
                    seen_books.add(norm)
                    
        return merged
