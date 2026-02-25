from typing import List
from .base import BaseDocumentParser
from .schemas import ParsedFormulaSheet

class FormulaParser(BaseDocumentParser):
    def get_schema(self, doc_type: str):
        return ParsedFormulaSheet

    def get_system_prompt(self, context: dict) -> str:
        return f"""You are an elite expert AI parser specializing in Formula Sheets for RGPV University.
        
CONTEXT:
Subject: {context.get('subject_code')} - {context.get('subject_name')}

YOUR TASK:
Extract formula names and their corresponding LaTeX representations.
Ensure all variable definitions are included if present.

--- SPECIAL RULES ---
1. Use profesional LaTeX formatting.
2. Ensure newlines in multi-line formulas use four backslashes (\\\\).
"""

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        if not all_results: return {}
        merged = {"formulas": []}
        seen_formulas = set()
        for res in all_results:
            for f in res.get('formulas', []):
                f['latex'] = self._sanitize_content(f.get('latex', ''))
                norm = f.get('name', '').strip().lower()
                if norm not in seen_formulas:
                    merged['formulas'].append(f)
                    seen_formulas.add(norm)
        return merged
