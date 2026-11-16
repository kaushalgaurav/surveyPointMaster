import re
from difflib import SequenceMatcher
from app.utils.processor import remove_internal_instructions

# --- FIXED: Clean Question Text (Handles 'NAME) t ?') ---
def clean_question_text(text):
    if not text: return ""
    
    # 1. Remove numbering
    text = re.sub(r'^\d+[a-z]?[\.\)\s]+', '', text)
    
    # 2. Remove symbols
    text = re.sub(r'^[\W_]+', '', text)
    
    # 3. FIX: Smart replace for (NAME) and leftover chars like 't' or 's'
    # Handles: "(NAME)", "(NAME)'s", "(NAME) t", "(NAME) ?"
    text = re.sub(r'\(NAME\)(?:\'s|[\)\s\w])?', 'the person ', text, flags=re.IGNORECASE)
    
    # 4. FIX: Remove orphan letters before question mark (e.g., "person t ?")
    text = re.sub(r'\s+[a-z]\s+\?', '?', text, flags=re.IGNORECASE)

    # 5. Remove Hindi
    text = re.sub(r'[\u0900-\u097F]+', '', text)
    
    # 6. Remove Instructions
    text = remove_internal_instructions(text)
    
    # 7. Formatting
    text = re.sub(r'\s+', ' ', text).strip()
    # Correct spacing around question mark
    text = text.replace(" ?", "?")
    
    return text

def infer_options_from_question(text):
    text_upper = text.upper()
    if text_upper.startswith(("DID ", "WAS ", "HAVE ", "HAS ", "IS ", "ARE ", "WERE ", "DO ", "DOES ")):
         return "- YES (1)\n- NO (2)"
    return ""

def split_merged_options(text):
    text = re.sub(r'(HOURS|DAYS|WEEKS|MONTHS|YEARS)(?:[\s\.]+|[\s_]+)(\d)', r'\1 (\2)\n', text, flags=re.IGNORECASE)
    # Merged codes
    pattern = r'(\b(?!(?:IF|OF|TO|IS|IN|OR|BY|AT|NO)\b)[0-9A-Z]{1,2})\s+([A-Z][A-Za-z])'
    text = re.sub(pattern, r'\1\n\2', text)
    # Lowercase lists
    text = re.sub(r'([a-z0-9])\s+([a-z]\))', r'\1\n\2', text)
    return text