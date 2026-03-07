import re

def ensure_blank_lines_around_headings(md: str) -> str:
    # Ensure two newlines before headings (but not at file start)
    md = re.sub(r'(?<!\A)\n(?=#{1,6}\s)', '\n\n', md)
    return md

def ensure_blank_lines_around_display_math(md: str) -> str:
    # Surround each $$...$$ with blank lines for clear separation
    def repl(m):
        content = m.group(0).strip()
        return '\n\n' + content + '\n\n'
    return re.sub(r'\$\$[\s\S]*?\$\$', repl, md)

def separate_list_items(md: str) -> str:
    # Ensure one blank line before list blocks and between list items
    md = re.sub(r'([^\n])\n(\s*[-\*\+]\s)', r'\1\n\n\2', md)
    md = re.sub(r'([^\n])\n(\s*\d+\.\s)', r'\1\n\n\2', md)
    # Make list items have a blank line after (visual separation)
    md = re.sub(r'(\n\s*[-\*\+]\s[^\n]+)\n(\s*[-\*\+]\s)', r'\1\n\n\2', md)
    md = re.sub(r'(\n\s*\d+\.\s[^\n]+)\n(\s*\d+\.\s)', r'\1\n\n\2', md)
    return md

def promote_inline_math(md: str, threshold: int = 60) -> str:
    # Promote long or complex inline math ($...$) to display math ($$...$$)
    pattern = re.compile(r'(?<!\$)\$(?!\$)([^\n$]{1,2000}?)\$(?!\$)')

    def needs_promotion(s: str) -> bool:
        s_stripped = s.strip()
        if len(s_stripped) > threshold:
            return True
        # promote if contains common structural tokens
        tokens = ['\\frac', '\\int', '\\sum', '\\displaystyle', '=', '^', '_', '\\left', '\\right']
        for t in tokens:
            if t in s_stripped:
                return True
        if re.search(r'[=<>]|\\frac|\\int', s_stripped):
            return True
        return False

    def repl(m):
        inner = m.group(1)
        if needs_promotion(inner):
            promoted = '$$\\displaystyle ' + inner.strip() + ' $$'
            return promoted
        return m.group(0)

    return pattern.sub(repl, md)

def normalize_paragraph_spacing(md: str) -> str:
    # Collapse excessive blank lines
    md = re.sub(r'\n{3,}', '\n\n', md)
    # Ensure paragraphs are separated
    md = re.sub(r'([^\n])\n([^\n#\-\*\d\$])', r'\1\n\n\2', md)
    return md

def normalize_markdown(md: str, inline_math_threshold: int = 60) -> str:
    if not md:
        return md
    md = md.replace('\r\n', '\n').replace('\r', '\n')
    md = ensure_blank_lines_around_headings(md)
    md = ensure_blank_lines_around_display_math(md)
    md = separate_list_items(md)
    md = promote_inline_math(md, threshold=inline_math_threshold)
    md = normalize_paragraph_spacing(md)
    return md.strip() + '\n'
