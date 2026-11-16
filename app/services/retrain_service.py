"""
Retrain FAISS (docs/templates) and/or template npy embeddings while API is live.
"""
import threading
from app.logger import get_logger
from app.core.config import settings, CONFIG

logger = get_logger()

_job_lock = threading.Lock()
_job_running = False
_last_result = {"status": "idle"}


def is_retrain_running():
    return _job_running


def get_last_retrain_result():
    return dict(_last_result)


def _reload_faiss():
    """Reload FAISS index into main.vector_db without restarting uvicorn."""
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    import app.main as main_app

    db_path = getattr(settings, "DB_OUTPUT_FOLDER", None) or getattr(
        settings, "DB_FOLDER", CONFIG["db_folder"]
    )
    embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
    main_app.vector_db = FAISS.load_local(
        db_path, embeddings, allow_dangerous_deserialization=True
    )
    logger.info(f"FAISS hot-reloaded from {db_path}")
    return db_path


def run_retrain(source: str = "templates", merge_docs: bool = True):
    """
    source:
      - templates: reload template DB embeddings + rebuild unified FAISS
      - docs: rebuild unified FAISS (templates + wordfiles)
      - all: same as both (template npy + unified FAISS)

    FAISS is always rebuilt with templates + docs when possible so one
    source never wipes the other.
    """
    global _job_running, _last_result

    if not _job_lock.acquire(blocking=False):
        return {"status": "busy", "message": "Retrain already running"}

    _job_running = True
    result = {"status": "ok", "source": source, "steps": {}}
    try:
        source = (source or "templates").lower().strip()
        if source not in ("templates", "docs", "all"):
            result = {"status": "error", "message": f"Unknown source: {source}"}
            _last_result = result
            return result

        # Template npy embeddings (used by /generate-questions)
        if source in ("templates", "all"):
            from app.train import reload_dataset_and_retrain
            result["steps"]["template_embeddings"] = reload_dataset_and_retrain(force=True)

        # Unified FAISS for /generate-survey-questions (templates + docs)
        from app.utils.builder_template import create_template_knowledge_base
        create_template_knowledge_base(merge_docs=True if merge_docs else (source in ("docs", "all")))
        result["steps"]["faiss"] = "rebuilt"
        result["steps"]["faiss_path"] = _reload_faiss()

        _last_result = result
        logger.info("Retrain finished: %s", result)
        return result
    except Exception as e:
        logger.exception("Retrain failed")
        result = {"status": "error", "message": str(e)}
        _last_result = result
        return result
    finally:
        _job_running = False
        _job_lock.release()


def start_retrain_async(source: str = "templates", merge_docs: bool = True):
    """Fire retrain in a background thread; return immediately."""
    if is_retrain_running():
        return {"status": "busy", "message": "Retrain already running"}

    thread = threading.Thread(
        target=run_retrain,
        kwargs={"source": source, "merge_docs": merge_docs},
        daemon=True,
        name="ai-retrain",
    )
    thread.start()
    return {"status": "started", "source": source, "merge_docs": merge_docs}
