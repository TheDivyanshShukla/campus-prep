import os
import django
import sys
import re
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'apps'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.content.models import ParsedDocument
from django.db import transaction

# Words that should generally stay lowercase in titles
LOWERCASE_WORDS = {
    'and', 'or', 'the', 'of', 'for', 'in', 'on', 'at', 'to', 'with', 'a', 'an'
}

MONTH_MAP = {
    'JAN': 'Jan', 'FEB': 'Feb', 'MAR': 'Mar', 'APR': 'Apr',
    'MAY': 'May', 'JUN': 'Jun', 'JUL': 'Jul', 'AUG': 'Aug',
    'SEP': 'Sep', 'OCT': 'Oct', 'NOV': 'Nov', 'DEC': 'Dec'
}

def clean_title_name(name_str):
    """Converts hyphenated uppercase name to proper Title Case."""
    words = name_str.replace('-', ' ').split()
    cleaned_words = []
    
    for i, word in enumerate(words):
        word_lower = word.lower()
        # Capitalize first word, last word, and words not in LOWERCASE_WORDS
        if i == 0 or i == len(words) - 1 or word_lower not in LOWERCASE_WORDS:
            cleaned_words.append(word.capitalize())
        else:
            cleaned_words.append(word_lower)
            
    return " ".join(cleaned_words)

def reformat_titles():
    docs = ParsedDocument.objects.all()
    print(f"Analyzing {docs.count()} documents...")

    updated_docs = []
    skipped_count = 0
    
    # Regex for CODE-NUM-NAME-MONTH-YEAR (MONTH YEAR)
    # Group 1: Code-Num part (BT-201)
    # Group 2: Name part (ENGINEERING-PHYSICS)
    # Group 3: Month (DEC)
    # Group 4: Year (2024)
    pattern = re.compile(r'^([A-Z-]+-\d+)-(.+)-(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)-(\d{4})', re.IGNORECASE)

    for doc in docs:
        old_title = doc.title
        match = pattern.match(old_title)
        
        if match:
            # name_part is between the code-num and the date
            name_raw = match.group(2)
            month_raw = match.group(3).upper()
            year_raw = match.group(4)
            
            clean_name = clean_title_name(name_raw)
            clean_month = MONTH_MAP.get(month_raw, month_raw.capitalize())
            
            new_title = f"{clean_name} - {clean_month} {year_raw}"
            
            if old_title != new_title:
                print(f"Transform: '{old_title}' -> '{new_title}'")
                doc.title = new_title
                updated_docs.append(doc)
            else:
                skipped_count += 1
        else:
            # Handle titles that might not have the code prefix but have the date
            # e.g., already reformatted or different format
            print(f"Skipping non-standard title: '{old_title}'")
            skipped_count += 1

    if updated_docs:
        print(f"\nBulk updating {len(updated_docs)} titles...")
        with transaction.atomic():
            ParsedDocument.objects.bulk_update(updated_docs, ['title'])
        print("Titles reformatted successfully!")
    else:
        print("\nNo titles needed reformatting.")

    print(f"Summary: {len(updated_docs)} updated, {skipped_count} skipped.")

if __name__ == "__main__":
    reformat_titles()
