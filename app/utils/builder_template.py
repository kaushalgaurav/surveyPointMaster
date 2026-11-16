"""
Build FAISS knowledge base from template_* MySQL tables
(same indexing approach as builder.py uses for .docx files).

Usage (from surveypointmaster/):
  python -m app.utils.builder_template
  python -m app.utils.builder_template --merge-docs   # also include wordfiles
"""
import argparse
import os
import re

from langchain.schema import Document as LangChainDocument
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from app.core.config import settings
from app.logger import get_logger
from app.models.question_model import load_questions_from_db
from app.utils.builder import classify_question
from app.utils.format import normalize_sector

logger = get_logger()


def _question_text_from_json(q_title_json) -> str:
    if q_title_json is None:
        return ""
    if isinstance(q_title_json, (int, float, bool)):
        return str(q_title_json).strip()
    if isinstance(q_title_json, str):
        return q_title_json.strip()
    if isinstance(q_title_json, dict):
        for key in ("english", "en", "English"):
            val = q_title_json.get(key)
            if val not in (None, ""):
                return str(val).strip()
        for value in q_title_json.values():
            if value not in (None, ""):
                return str(value).strip()
    return str(q_title_json).strip()


def _options_from_ans_json(ans_json_data) -> str:
    """Convert ans_json_data into the same Options: block style used by doc builder."""
    if not ans_json_data or not isinstance(ans_json_data, dict):
        return ""

    answers = None
    for key in ("english", "en", "English"):
        block = ans_json_data.get(key)
        if isinstance(block, dict) and block.get("answer"):
            answers = block["answer"]
            break
        if isinstance(block, list):
            answers = block
            break

    if answers is None:
        for block in ans_json_data.values():
            if isinstance(block, dict) and block.get("answer"):
                answers = block["answer"]
                break
            if isinstance(block, list):
                answers = block
                break

    if not answers:
        return ""

    lines = []
    for i, ans in enumerate(answers, start=1):
        text = str(ans).strip()
        if "|" in text:
            code, label = text.split("|", 1)
            lines.append(f"- {label.strip()} ({code.strip()})")
        else:
            lines.append(f"- {text} ({i})")
    return "\n".join(lines)


def documents_from_templates(global_hashes=None):
    """
    Convert template_survey + template_survey_data (+ section) into
    LangChain documents matching the doc-file FAISS schema.
    """
    if global_hashes is None:
        global_hashes = set()

    sector_data = load_questions_from_db()
    documents = []
    skipped = 0

    for sector, templates in sector_data.items():
        sector_tag = normalize_sector(sector)
        for template_id, tpl in templates.items():
            title = tpl.get("template_title") or tpl.get("reference") or ""
            for q in tpl.get("questions", []):
                q_text = _question_text_from_json(q.get("q_title_json"))
                if not q_text or len(q_text) < 3:
                    skipped += 1
                    continue

                q_hash = re.sub(r"\s+", "", q_text.lower())
                if q_hash in global_hashes:
                    skipped += 1
                    continue
                global_hashes.add(q_hash)

                opts = _options_from_ans_json(q.get("ans_json_data"))
                final_text = q_text
                if opts:
                    final_text += f"\nOptions:\n{opts}"

                tag = classify_question(q_text)
                section_title = q.get("section_title") or ""
                page_content = f"[{tag}] {final_text}"

                documents.append(
                    LangChainDocument(
                        page_content=page_content,
                        metadata={
                            "origin": "template",
                            "source_type": f"template_{template_id}",
                            "complexity": tag,
                            "sector": sector_tag,
                            # Templates are not tied to doc survey_type folders
                            "survey_type": "template",
                            "template_id": str(template_id),
                            "template_title": title,
                            "qtype": q.get("qtype") or "",
                            "qid": str(q.get("qid") or ""),
                            "section_title": section_title,
                            "full_path": f"db://template_survey/{template_id}",
                        },
                    )
                )

    logger.info(
        f"Template FAISS docs: {len(documents)} questions "
        f"({skipped} skipped empty/duplicate) across {len(sector_data)} sectors"
    )
    print(
        f"Template FAISS docs: {len(documents)} questions "
        f"({skipped} skipped) across {len(sector_data)} sectors"
    )
    return documents


def create_template_knowledge_base(merge_docs: bool = False):
    """
    Train/rebuild FAISS index from template tables (optionally merge word docs).
    Output folder: settings.DB_OUTPUT_FOLDER (same as doc training).
    """
    global_hashes = set()
    all_documents = documents_from_templates(global_hashes)

    if merge_docs:
        logger.info("Also scanning wordfiles (merge-docs)...")
        print("Also scanning wordfiles (merge-docs)...")
        # Reuse doc walk by temporarily collecting via create_knowledge_base path:
        # Prefer calling the same folder walk if DATA_FOLDER exists.
        if os.path.exists(settings.DATA_FOLDER):
            from app.utils.builder import process_file_final

            allowed_types = {t.lower() for t in settings.SURVEY_TYPES}
            allow_all_types = "*" in allowed_types or not allowed_types
            for root, _dirs, files in os.walk(settings.DATA_FOLDER):
                rel_path = os.path.relpath(root, settings.DATA_FOLDER)
                path_parts = rel_path.split(os.sep)
                if len(path_parts) < 2 or path_parts[0] == ".":
                    continue
                survey_type_tag = path_parts[1].lower()
                if not allow_all_types and survey_type_tag not in allowed_types:
                    continue
                sector_tag = normalize_sector(path_parts[0])
                for filename in files:
                    if not filename.endswith(".docx") or filename.startswith("~"):
                        continue
                    path = os.path.join(root, filename)
                    file_tag = os.path.splitext(filename)[0].lower()
                    try:
                        data = process_file_final(path)
                        if not data:
                            continue
                        for item in data:
                            q_hash = re.sub(r"\s+", "", item["text"].split("\n")[0].lower())
                            if q_hash in global_hashes:
                                continue
                            global_hashes.add(q_hash)
                            all_documents.append(
                                LangChainDocument(
                                    page_content=f"[{item['tag']}] {item['text']}",
                                    metadata={
                                        "source_type": file_tag,
                                        "complexity": item["tag"],
                                        "sector": sector_tag,
                                        "survey_type": survey_type_tag,
                                        "full_path": path,
                                    },
                                )
                            )
                    except Exception as e:
                        logger.error(f"Error processing file {filename}: {e}")
        else:
            logger.warning(f"DATA_FOLDER not found, skip merge-docs: {settings.DATA_FOLDER}")

    if not all_documents:
        logger.warning("No template (or doc) questions found — FAISS not updated.")
        print("No template (or doc) questions found — FAISS not updated.")
        return

    logger.info(f"Indexing {len(all_documents)} items into FAISS...")
    print(f"Indexing {len(all_documents)} items into FAISS...")
    embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
    vector_db = FAISS.from_documents(all_documents, embeddings)
    vector_db.save_local(settings.DB_OUTPUT_FOLDER)
    logger.info(f"FAISS rebuilt at {settings.DB_OUTPUT_FOLDER}")
    print(f"FAISS rebuilt at {settings.DB_OUTPUT_FOLDER}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train FAISS from template DB tables")
    parser.add_argument(
        "--merge-docs",
        action="store_true",
        help="Also include wordfiles from DATA_FOLDER (same as builder.py)",
    )
    args = parser.parse_args()
    create_template_knowledge_base(merge_docs=args.merge_docs)
