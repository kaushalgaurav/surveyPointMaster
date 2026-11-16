import requests
import unicodedata
from dotenv import load_dotenv
import os
load_dotenv()

# Aapki API Key yahan set karein
URL = "https://translation.googleapis.com/language/translate/v2"

# Mapping for common Indian languages to Google codes
LANG_CODES = {
    "hindi": "hi",
    "marathi": "mr",
    "gujarati": "gu",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "bengali": "bn",
    "punjabi": "pa",
    "malayalam": "ml"
}

# --- HELPERS ---
def translate_text(text, target_langs):
    """Google Translate API key ka use karke text translate karta hai."""
    if not target_langs:
        return {}
    
    translations = {}
    for lang in target_langs:
        target_code = LANG_CODES.get(lang.lower().strip())
        if not target_code:
            continue
            
        params = {
            'q': text,
            'target': target_code,
            'key': os.getenv("GOOGLE_API_KEY")
        }
        
        try:
            response = requests.get(URL, params=params)
            if response.status_code == 200:
                translated_text = response.json()['data']['translations'][0]['translatedText']
                # HTML entities decode karne ke liye
                translations[lang.upper()] = unicodedata.normalize("NFKD", translated_text)
                print(f"Translated to {lang.upper()}: {translations[lang.upper()]}")
                print(f"Response: {response.status_code} - {response.text}")
            else:
                translations[lang.upper()] = f"[Error: {response.status_code}]"
        except Exception as e:
            translations[lang.upper()] = "[Error]"
            
    return translations
