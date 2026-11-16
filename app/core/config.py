import os

# surveypointmaster/ root (parent of app/)
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Laravel project root (parent of surveypointmaster/)
_LARAVEL_ROOT = os.path.abspath(os.path.join(_BASE_DIR, ".."))


def _resolve_data_folder():
    """Pick wordfiles path for Windows local or Linux server."""
    env_path = os.getenv("WORDFILES_FOLDER") or os.getenv("DATA_FOLDER")
    if env_path and os.path.isdir(env_path):
        return env_path

    candidates = [
        # Windows / local Laravel storage
        os.path.join(_LARAVEL_ROOT, "storage", "app", "public", "wordfiles"),
        os.path.join(_LARAVEL_ROOT, "public", "storage", "wordfiles"),
        # Local copy inside surveypointmaster
        os.path.join(_BASE_DIR, "app", "raw_data2"),
        # Linux production server
        "/var/www/researchnimbliai/storage/app/public/wordfiles",
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    # Fallback: prefer local Laravel path even if missing (clearer warning)
    return candidates[0]


class Settings:
    DATA_FOLDER = _resolve_data_folder()
    DB_OUTPUT_FOLDER = "faiss_index_nfhs"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    # Subfolders under each sector that contain survey Word files
    SURVEY_TYPES = ("quantitative", "fgd", "idi", "other")

settings = Settings()

# --- CONFIGURATION ---
CONFIG = {
    "db_folder": "faiss_index_nfhs",
    "similarity_threshold": 1.15,
    "duplicate_ratio": 0.85,
    "demographics_count": 3,
    "demographics_query": "respondent name age address education religion family profile",
    # Avoid topic-killing terms like VACCINATION (breaks immunization surveys)
    "default_noise_words": ["BANK", "ACCOUNT", "INSURANCE", "HIV", "AIDS", "SCHEME", "MALARIA", "TB", "MOSQUITO", "NET", "CROP", "FARM"],
    # Minimum FAISS fetch sizes (generator scales up with no_of_questions)
    "fetch_limit_basic": 50,
    "fetch_limit_complex": 500,
    # Caps so very large requests stay bounded
    "fetch_limit_basic_max": 200,
    "fetch_limit_complex_max": 2000,
}
