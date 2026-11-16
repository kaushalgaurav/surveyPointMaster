# app/models/question_model.py
import json
from sqlalchemy import text
from app.database import get_db_session
from app.logger import get_logger

logger = get_logger()
logger.info("Question Model module loaded")


def _parse_json_field(raw, qid, field_name):
    if not raw:
        return {} if field_name == "ques_title_json" else None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception as e:
        logger.error(f"Invalid {field_name} | qid={qid} | {e}")
        return {} if field_name == "ques_title_json" else None


def load_questions_from_db():
    """
    Load active template surveys + questions for embedding / FAISS training.

    Tables used:
      - template_survey
      - template_survey_data
      - template_survey_section  (section title/description context)
      - sector
    """
    session = get_db_session()
    dataset = {}

    query = text("""
        SELECT 
            s.sector_name AS sector,
            s.short_name AS sector_short,
            ts.id AS template_id,
            ts.title AS template_title,
            ts.template_desc AS template_description,
            tsd.qid,
            tsd.qtype,
            tsd.ques_title_json,
            tsd.ans_json_data,
            tsd.section_id,
            sec.title AS section_title,
            sec.description AS section_description
        FROM template_survey ts
        JOIN template_survey_data tsd ON ts.id = tsd.survey_id
        LEFT JOIN sector s ON ts.sector = s.short_name
        LEFT JOIN template_survey_section sec ON tsd.section_id = sec.id
        WHERE ts.status = 1
          AND COALESCE(ts.template, 1) = 1
          AND tsd.deleted_at IS NULL
          AND ts.deleted_at IS NULL
        ORDER BY s.sector_name, ts.id, tsd.section_id, tsd.qid;
    """)

    try:
        result = session.execute(query).mappings().all()
        logger.info(f"Fetched {len(result)} rows from template tables")

        for row in result:
            sector = row["sector"] or row["sector_short"] or "Unknown"
            template_id = row["template_id"]
            title = row["template_title"] or ""
            description = row["template_description"] or ""

            dataset.setdefault(sector, {})
            dataset[sector].setdefault(template_id, {
                # Keys used by train.py
                "template_title": title,
                "template_description": description,
                # Aliases kept for older callers
                "reference": title,
                "description": description,
                "sector_short": row["sector_short"] or "",
                "questions": []
            })

            q_title_json = _parse_json_field(row["ques_title_json"], row["qid"], "ques_title_json")
            ans_json_data = _parse_json_field(row["ans_json_data"], row["qid"], "ans_json_data")

            dataset[sector][template_id]["questions"].append({
                "qid": row["qid"],
                "qtype": row["qtype"],
                "q_title_json": q_title_json,
                "ans_json_data": ans_json_data,
                "section_id": row["section_id"],
                "section_title": row["section_title"] or "",
                "section_description": row["section_description"] or "",
            })

    except Exception:
        logger.exception("Failed DB query for template questions")
        raise
    finally:
        session.close()

    return dataset
