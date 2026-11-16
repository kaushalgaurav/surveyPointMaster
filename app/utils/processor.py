import re
# --- HELPERS ---
def normalize_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text).strip()

def is_mostly_english(text):
    if not text: return False
    ascii_count = len([c for c in text if ord(c) < 128])
    return (ascii_count / len(text)) > 0.7

def contains_hindi(text):
    return bool(re.search(r'[\u0900-\u097F]', text))

def clean_noise(text):
    text = re.sub(r'(?:[\.\-_]\s*){2,}', ' ', text)
    text = re.sub(r'^[\s\-\.\)]+', '', text)
    return text.strip()

def remove_internal_instructions(text):
    triggers = [
        "PROBE FOR", "PROBE TO", "RECORD ALL", "RECORD THE", "RECORD NAME",
        "IF UNABLE TO", "IF RESPONDENT", "WRITE THE NAME", 
        "CHECK THE", "CHECK RE", "CHECK 2", "CHECK 3", 
        "(NAME OF FACILITY", "SKIP TO", "ANSWER ANY QUESTIONS"
    ]
    text_upper = text.upper()
    best_cut_index = len(text)
    found_trigger = False
    for trigger in triggers:
        idx = text_upper.find(trigger)
        if idx != -1 and idx < best_cut_index:
            best_cut_index = idx
            found_trigger = True
    if found_trigger:
        return text[:best_cut_index].strip()
    return text

def is_real_question(text):
    text = text.strip()
    upper = text.upper()
    if len(text) < 12: return False
    if len(text) > 300: return False 
    bad_starters = ["SECTION", "CHAPTER", "RECORD", "SKIP", "GO TO", "IF UNABLE", "PROBE", "CORRECT", "BIRTHS", "AGE:", "ADDRESS", "NAME FROM", "OF FAMILY", "NOTE", "NAMASTE", "MY NAME IS"]
    if any(upper.startswith(bad) for bad in bad_starters): return False
    question_starters = ["WHO", "WHAT", "WHERE", "WHEN", "WHY", "HOW", "IS", "ARE", "DO", "DOES", "DID", "HAVE", "HAS", "CAN", "COULD", "WOULD", "SHOULD", "WHICH", "KINDLY", "PLEASE"]
    has_question_mark = "?" in text
    starts_with_q_word = any(upper.startswith(w) for w in question_starters)
    if not (has_question_mark or starts_with_q_word): return False
    return True