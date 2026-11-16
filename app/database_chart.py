import os
import json
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

load_dotenv(override=True)

def fetch_survey_data(survey_url, workspace_id):
    # --- 1. Database Connection Setting up inside the function ---
    db_user = os.getenv("DB_USER")
    db_password = quote_plus(os.getenv("DB_PASSWORD"))
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", 3306)
    db_name = os.getenv("DB_NAME")

    # SQLAlchemy URL format for MySQL (using pymysql)
    # db_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    db_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    try:
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return None

    try:

        # --- 3. Get Research Objectives, Area of Inquiry, Analytical Protocol ---
        section_mapping = {
            4: "research_objective",
            5: "area_of_inquiry",
            11: "analytical_protocol"
        }
        
        context_data = {key: "" for key in section_mapping.values()}
        
        # FIX: Yahan WHERE clause mein workspace_id use ho raha hai
        context_query = text("""
            SELECT section_id, content 
            FROM section_contents 
            WHERE workspace_id = :workspace_id AND section_id IN (4, 5, 11)
        """)
        # FIX: Parameter mein sahi variable (workspace_id) pass kiya hai
        context_rows = db.execute(context_query, {"workspace_id": workspace_id}).fetchall()
        
        for row in context_rows:
            key = section_mapping.get(row._mapping['section_id'])
            if key:
                context_data[key] = row._mapping['content']

        # --- 4. Get Questions and Stats ---
        # Yeh bilkul sahi hai, survey_id se hi questions fetch ho rahe hain
        query = text("""
            SELECT 
                data_id, 
                qid, 
                qtype, 
                ques_title_json, 
                que_description, 
                ans_json_data 
            FROM `survey_data` 
            WHERE deleted_at IS NULL 
            AND survey_id = :survey_id 
            ORDER BY `id` ASC
        """)
        results = db.execute(query, {"survey_id": survey_url}).fetchall()

        if not results:
            if not any(context_data.values()):
                return None

        # --- 4. Final Payload Formatting ---
        formatted_data = {
            "numeric_id": survey_url,
            "survey_url": survey_url,
            "workspace_id": workspace_id,
            "research_context": context_data,
            "questions": []
        }

        for row in results:
            row_map = row._mapping
            
            try:
                title = json.loads(row_map["ques_title_json"]) if row_map["ques_title_json"] else row_map["ques_title_json"]
                stats = json.loads(row_map["ans_json_data"]) if row_map["ans_json_data"] else row_map["ans_json_data"]
            except json.JSONDecodeError:
                title = row_map["ques_title_json"]
                stats = row_map["ans_json_data"]

            formatted_data["questions"].append({
                "data_id": row_map["data_id"],
                "qid": row_map["qid"],
                "type": row_map["qtype"],
                "title": title,
                "stats": stats
            })

        return formatted_data

    except SQLAlchemyError as err:
        print(f"Database Error: {err}")
        return None
    finally:
        if 'db' in locals():
            db.close()