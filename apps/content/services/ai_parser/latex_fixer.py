"""
LaTeX Fixer Service — Uses KaTeX (Node.js) for validation + LLM for fixing broken math blocks.
"""

import re
import json
import subprocess
import asyncio
import os
from typing import List, Dict, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import httpx

_latex_fixer_client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=50000, max_keepalive_connections=1000)
)

KATEX_SCRIPT = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'scripts', 'validate_katex.js')

FIXER_SYSTEM_PROMPT = r"""You are an expert LaTeX/KaTeX math fixer. You receive broken KaTeX math expressions along with their surrounding markdown context.

YOUR TASK: Fix ONLY the broken LaTeX so it compiles correctly in KaTeX. 

RULES:
1. Return ONLY the fixed LaTeX string — no delimiters (no $ or $$), no explanation.
2. Preserve the original mathematical meaning exactly.
3. Common fixes: unmatched braces, missing \right or \left, broken \frac, unescaped underscores, invalid commands.
4. KaTeX does NOT support: \begin{align*}, \begin{eqnarray}, \intertext, \mbox. Convert to supported alternatives.
5. Use \text{} instead of \mbox{} or \mathrm{} for text inside math.
6. Use \boxed{} for boxed formulas (KaTeX supports this natively).
7. For aligned equations, use \begin{aligned} (not \begin{align}).
8. Escape curly braces for sets: \{ and \} or \lbrace and \rbrace.
9. If a block is hopelessly broken, return the closest valid KaTeX approximation.
"""


def extract_math_blocks(content: str) -> List[Dict]:
    """Extract all $...$ and $$...$$ math blocks with positions and line context."""
    blocks = []
    lines = content.split('\n')
    
    # Display math: $$...$$
    for match in re.finditer(r'\$\$([\s\S]*?)\$\$', content):
        latex = match.group(1).strip()
        if not latex:
            continue
        start_line = content[:match.start()].count('\n')
        end_line = content[:match.end()].count('\n')
        # 10 lines up, 10 lines down context
        ctx_start = max(0, start_line - 10)
        ctx_end = min(len(lines), end_line + 11)
        context = '\n'.join(lines[ctx_start:ctx_end])
        blocks.append({
            'id': len(blocks),
            'latex': latex,
            'displayMode': True,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'context': context,
        })
    
    # Inline math: $...$  (not preceded/followed by $)
    for match in re.finditer(r'(?<!\$)\$(?!\$)((?!\$).+?)\$(?!\$)', content):
        latex = match.group(1).strip()
        if not latex:
            continue
        start_line = content[:match.start()].count('\n')
        end_line = content[:match.end()].count('\n')
        ctx_start = max(0, start_line - 10)
        ctx_end = min(len(lines), end_line + 11)
        context = '\n'.join(lines[ctx_start:ctx_end])
        blocks.append({
            'id': len(blocks),
            'latex': latex,
            'displayMode': False,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'context': context,
        })
    
    return blocks


def validate_with_katex(blocks: List[Dict]) -> List[Dict]:
    """Run KaTeX validation on math blocks via Node.js subprocess."""
    if not blocks:
        return []
    
    input_data = json.dumps([
        {'id': b['id'], 'latex': b['latex'], 'displayMode': b['displayMode']}
        for b in blocks
    ])
    
    script_path = os.path.abspath(KATEX_SCRIPT)
    
    try:
        result = subprocess.run(
            ['node', script_path],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.dirname(script_path),
        )
        if result.returncode != 0:
            print(f"KaTeX validator error: {result.stderr}")
            return []
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        print("KaTeX validator timed out")
        return []
    except Exception as e:
        print(f"KaTeX validator exception: {e}")
        return []


class LatexFixer:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="cerebras/gpt-oss-120b",
            openai_api_base="https://bifrost.naravirtual.in/langchain",
            openai_api_key="dummy-key",
            default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
            http_async_client=_latex_fixer_client,
            max_retries=5000,
            temperature=0.1,
        )
    
    async def fix_content(self, content: str, max_retries: int = 2) -> Tuple[str, int]:
        """
        Validate and fix all LaTeX in a content string.
        Returns (fixed_content, num_fixes_applied).
        """
        blocks = extract_math_blocks(content)
        if not blocks:
            return content, 0
        
        # Validate all blocks with KaTeX
        results = validate_with_katex(blocks)
        if not results:
            return content, 0
        
        # Find broken blocks
        broken_ids = {r['id'] for r in results if not r.get('valid')}
        errors_by_id = {r['id']: r.get('error', '') for r in results if not r.get('valid')}
        
        if not broken_ids:
            return content, 0
        
        broken_blocks = [b for b in blocks if b['id'] in broken_ids]
        
        # Fix each broken block with LLM (with retry)
        fixed_content = content
        fixes_applied = 0
        
        for attempt in range(max_retries):
            if not broken_blocks:
                break
                
            fixes = await self._batch_fix(broken_blocks, errors_by_id)
            
            # Apply fixes back-to-front to preserve positions
            sorted_blocks = sorted(broken_blocks, key=lambda b: b['start'], reverse=True)
            for block in sorted_blocks:
                fix = fixes.get(block['id'])
                if fix and fix != block['latex']:
                    delim = '$$' if block['displayMode'] else '$'
                    old_text = block['full_match']
                    new_text = f"{delim}{fix}{delim}"
                    fixed_content = fixed_content[:block['start']] + new_text + fixed_content[block['end']:]
                    fixes_applied += 1
            
            # Re-validate to check if fixes worked
            if attempt < max_retries - 1:
                new_blocks = extract_math_blocks(fixed_content)
                new_results = validate_with_katex(new_blocks)
                still_broken = [r for r in new_results if not r.get('valid')]
                if not still_broken:
                    break
                broken_blocks = [b for b in new_blocks if b['id'] in {r['id'] for r in still_broken}]
                errors_by_id = {r['id']: r.get('error', '') for r in still_broken}
        
        return fixed_content, fixes_applied
    
    async def _batch_fix(self, broken_blocks: List[Dict], errors_by_id: Dict) -> Dict[int, str]:
        """Send broken blocks to LLM for fixing. Returns {id: fixed_latex}."""
        semaphore = asyncio.Semaphore(10000)
        
        async def fix_one(block):
            async with semaphore:
                error_msg = errors_by_id.get(block['id'], 'Unknown error')
                user_msg = (
                    f"BROKEN LATEX:\n```\n{block['latex']}\n```\n\n"
                    f"KATEX ERROR: {error_msg}\n\n"
                    f"SURROUNDING CONTEXT (10 lines above and below):\n```markdown\n{block['context']}\n```\n\n"
                    f"Return ONLY the fixed LaTeX string (no $ delimiters, no explanation)."
                )
                try:
                    response = await self.llm.ainvoke([
                        SystemMessage(content=FIXER_SYSTEM_PROMPT),
                        HumanMessage(content=user_msg),
                    ])
                    fixed = response.content.strip()
                    # Strip any accidental delimiter wrapping
                    fixed = re.sub(r'^\$+|\$+$', '', fixed).strip()
                    # Strip markdown code fences
                    fixed = re.sub(r'^```(?:latex)?\s*|\s*```$', '', fixed, flags=re.MULTILINE).strip()
                    return block['id'], fixed
                except Exception as e:
                    print(f"LLM fix failed for block {block['id']}: {e}")
                    return block['id'], None
        
        tasks = [fix_one(b) for b in broken_blocks]
        results = await asyncio.gather(*tasks)
        return {bid: fix for bid, fix in results if fix is not None}
