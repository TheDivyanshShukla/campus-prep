import asyncio
import re
import hashlib
from typing import List
from .base import BaseDocumentParser
from .schemas import ParsedNotes

class NoteParser(BaseDocumentParser):
    def get_schema(self, doc_type: str):
        return ParsedNotes

    def get_system_prompt(self, context: dict) -> str:
        return f"""You are an elite expert AI parser specializing in Engineering Academic Notes for RGPV University.
        
getContext:
Subject: {context.get('subject_code')} - {context.get('subject_name')}
Document Type: {context.get('document_type_display')}

--- SYLLABUS REFERENCE (FOR UNIT MAPPING) ---
{context.get('syllabus_context', 'No syllabus context provided.')}

YOUR TASK:
Extract pristine, highly-accurate structured data from the source.
If the notes do not have explicit unit headings, use the SYLLABUS REFERENCE to organize the content into logical SECTIONS corresponding to Units.

--- SPECIAL RULES FOR NOTES ---
1. SECTION TITLES: Use descriptive titles based on units or topics. Use the Syllabus to guide unit-mapping.
2. CONTENT BLOCKS: Use 'text' (Markdown) for explanations and 'image' (strategies) for diagrams.
3. QUALITY: Ensure excellent vertical spacing and pure Markdown in content fields.
"""

    async def get_extra_context(self, parsed_document_obj, subject) -> dict:
        """Fetch existing syllabus for the same subject to provide context."""
        from apps.content.models import ParsedDocument
        if not subject:
            return {'syllabus_context': "No subject associated."}
        
        syllabus = await asyncio.to_thread(lambda: ParsedDocument.objects.filter(
            subjects=subject, 
            document_type='SYLLABUS', 
            parsing_status='COMPLETED'
        ).first())
        
        if syllabus and syllabus.structured_data:
            import json
            return {'syllabus_context': json.dumps(syllabus.structured_data, indent=2)}
        return {'syllabus_context': "No existing syllabus found for unit mapping context."}

    def _merge_results(self, doc_type: str, all_results: List[dict]) -> dict:
        if not all_results: return {}
        merged = all_results[0].copy()
        seen_sections = set()
        
        for res in all_results:
            if 'sections' in res:
                for s in res['sections']:
                    title_norm = s.get('section_title', '').strip().lower()
                    if title_norm not in seen_sections:
                        if res is all_results[0]:
                            seen_sections.add(title_norm)
                        else:
                            merged['sections'].append(s)
                            seen_sections.add(title_norm)
                    else:
                        # Merge content blocks into existing section
                        existing_sec = next(sec for sec in merged['sections'] if sec.get('section_title', '').strip().lower() == title_norm)
                        
                        def _get_block_hash(b):
                            if b.get('type') == 'text':
                                return hashlib.md5((b.get('content') or '').strip().encode()).hexdigest()
                            else:
                                strategy = b.get('image_strategy') or ''
                                details = b.get('image_details') or ''
                                return hashlib.md5(f"IMG:{strategy}:{details}".encode()).hexdigest()

                        existing_block_hashes = {_get_block_hash(b) for b in existing_sec['content_blocks']}
                        for b in s.get('content_blocks', []):
                            if b.get('type') == 'text':
                                b['content'] = self._sanitize_content(b.get('content', ''))
                            
                            b_hash = _get_block_hash(b)
                            if b_hash not in existing_block_hashes:
                                existing_sec['content_blocks'].append(b)
                                existing_block_hashes.add(b_hash)
        return merged
