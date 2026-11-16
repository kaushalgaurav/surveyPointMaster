import openai
import os
import json
from typing import Dict, List
from dotenv import load_dotenv
import re
import logging

# 1. Create a custom logger for chart generation
logger = logging.getLogger("ChartGenerator")
logger.setLevel(logging.INFO)

# 2. Create a file handler that logs messages to a file
log_file = "chart_generation.log"
file_handler = logging.FileHandler(log_file, mode='a')
file_handler.setLevel(logging.INFO)

# 3. Create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 4. Add the handler to the logger
if not logger.handlers:
    logger.addHandler(file_handler)

# Optional: Add a StreamHandler if you still want to see logs in the console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

logger.info("Chart generation logger initialized. Logging to chart_generation.log")

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_PRIVATE_KEY"))
logger.info("OpenAI client initialized successfully.")

def clean_html(raw_html):
    """HTML tags aur entities ko remove karne ke liye helper function."""
    if not raw_html:
        return ""
    # 1. HTML tags (<p>, <ul>, etc.) remove karein
    clean_text = re.sub(r'<[^>]*>', ' ', raw_html)
    # 2. HTML entities (&nbsp;, &amp;, etc.) remove karein
    clean_text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', clean_text)
    # 3. Extra spaces ko single space mein convert karein
    return " ".join(clean_text.split())

def analyze_with_ai(survey_payload: Dict, numeric_id: int, survey_url: str, workspace_id: str) -> Dict:
    questions = survey_payload.get("questions", [])
    research_context = survey_payload.get("research_context", {})
    
    # Clean Context - Ye AI ke liye 'Rules' ka kaam karenge
    objective = clean_html(research_context.get("research_objective", ""))
    area_of_inquiry = clean_html(research_context.get("area_of_inquiry", ""))
    protocol = clean_html(research_context.get("analytical_protocol", ""))

    # --- STEP 1: Flexible Metadata Extraction ---
    full_metadata = []
    for q in questions:
        full_metadata.append({
            "id": q.get("data_id"),
            "lbl": q.get("ques_title_json"), 
            "typ": q.get("qtype"),
            "opt": q.get("ans_json_data")
        })

    # --- STEP 2: The "Heuristic Analyst" System Prompt ---
    system_instruction = f"""
        You are a Senior Data Analyst. Analyze the provided survey and the ANALYTICAL PROTOCOL and a massive survey of {len(questions)} questions to generate 50 most impactful chart ideas.
        Each idea must be justified with a clear reasoning statement that ties back to the protocol and the main objective.

        ### Protocol-Driven Analysis (Highest Priority)
        Deeply study the provided ANALYTICAL PROTOCOL, RESEARCH OBJECTIVE, and AREA OF INQUIRY. Identify all primary indicators it specifies (e.g., Difference-in-Differences, Knowledge-Attitude-Practice gaps, socioeconomic disparities, behavioral drivers).
        Every chart idea must serve the stated MAIN OBJECTIVE. Rank ideas by how directly and significantly they advance this objective.
        Do not assume sectors or question priorities—let the protocol determine what matters.
        
        ### Correlation-Heavy Design
        Link Drivers (demographics, knowledge levels, frontline worker interaction, exposure) to Outcomes (behavioral intention, actual practice, participation rates).
        Treat the entire survey as interconnected—correlate questions regardless of their survey position. Look for non-obvious connections that reveal causal patterns.

        ### SELECTION CRITERIA:
        - Priority 1: Align with the PROTOCOL ({protocol}) and directly address the MAIN OBJECTIVE ({objective}) and AREA OF INQUIRY ({area_of_inquiry}).
        - Priority 2: Use the most appropriate chart for the data type.
        - Priority 3: Maintain visual diversity across the 50 selections.

        ### CHART LOGIC:
            - TEXT (stextbox, text, number, decimal) -> 'word_cloud' (graph_type='word_cloud').
            - SINGLE CATEGORICAL (MCQ/Radio) -> Rotate between ['pie_chart', 'donut_chart', 'radial_chart', 'polar_chart','column_chart', 'bar_chart','treemap_chart']. (graph_type='chart').
            - COMPARISONS/RANKING -> Use 'column_chart' or 'bar_chart'.
            - CORRELATIONS (Two Questions) -> Rotate between ['stack_chart', 'column_chart', 'bar_chart', 'area_chart', 'scatter_chart', 'bubble_chart', 'table', 'line_chart', 'frequency', 'radar_chart', 'heatmap_chart', 'box_plot_chart'].
            Choose based on context:
                -Standard Correlations: 'stack_chart', 'column_chart', 'bar_chart'.
                -Advanced Analytics: 'radar_chart', 'heatmap_chart', 'box_plot_chart'.
                -Distribution/Patterns: 'area_chart', 'scatter_chart', 'bubble_chart'.
            - NUMERIC RELATIONSHIPS -> Use 'scatter_chart' or 'bubble_chart'.
            - TRENDS/SCALES -> 'line_chart' or 'frequency'.
            - TABLE -> graph_type='table'. Set col_id (cannot be null) & row_id (cannot be text).
            - RAW DATA/COMPLEX DISTRIBUTIONS -> 'table' or 'frequency'.
            - FREQUENCY -> Set graph_type='table'.

        ### STRICT CHART MAPPING:
        1. **Single MCQ/Radio :** Rotate Between ['pie_chart', 'donut_chart', 'radial_chart', 'polar_chart', 'treemap_chart']. Set col_id to null.
        2. **Drivers to Outcomes :** Rotate Between ['stack_chart', 'column_chart', 'bar_chart', 'area_chart'].
        3. **Statistical Patterns :** Rotate Between ['scatter_chart', 'bubble_chart', 'radar_chart', 'box_plot_chart'].
        4. **Trends & Distributions :** Rotate Between ['line_chart', 'frequency', 'heatmap_chart', 'table'].

        ### THE "CROSSTAB-FIRST" MANDATE (CRITICAL):
        1. **80/20 Rule:** 40 Charts MUST be Correlations (col_id != null). Only 10 (or fewer) should be Single-Variable (col_id = null).
        2. **Protocol Mapping:** Identify 'Drivers' (Caste, Education, FLW interaction, Gender) and 'Outcomes' (Vaccination Status, Intention, FIC). Every correlation must link a Driver to an Outcome as per the ANALYTICAL PROTOCOL: {protocol}.
        3. **Global Connectivity:** Link questions from any part of the survey (e.g., Section B demographics with Section J outcomes).
        
        ### CONSTRAINTS:
        - IDs: Use ONLY long hashes (e.g., 'ut3oqV...'). NO short codes/numbers.
        - Col_id: Set to null if no correlation. 
        - Allowed graph_type: ['chart', 'word_cloud', 'table']
        - Allowed chart_type: [
                'stack_chart','pie_chart','line_chart','column_chart','donut_chart',
                'word_cloud','table','frequency','radial_chart','treemap_chart', 
                'polar_chart','area_chart', 'scatter_chart','bubble_chart','bar_chart','box_plot_chart','heatmap_chart'
            ]

    ### OUTPUT FORMAT (List of Objects):
    Return a JSON object with key "chart_ideas" containing a list of objects exactly like this:
    
    {{
      "chart_ideas": [
        {{
          "row_id": "ut3oqVlubUfzRMAOtKEj",  should match a valid 'data_id' from the questions list (not a short code or description)
          "col_id": null, 
          "suggested_chart_type": "pie_chart",
          "importance_score": 9,
          "reasoning": "Directly answers the main objective regarding user retention."
        }},
        {{
          "row_id": "ut3oqVlubUfzRMAOtKEj", should match a valid 'data_id' from the questions list (not a short code or description)
          "col_id": "r0gp5JCambqhMjmxZBOB", should match a valid 'data_id' from the questions list (not a short code or description)
          "suggested_chart_type": "stack_chart",
          "importance_score": 9,
          "reasoning": "Directly answers the main objective regarding user retention."
        }}
      ]
    }}
    """
    user_content = f"SURVEY_METADATA: {json.dumps(full_metadata)}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.2 # Strict adherence to logic and count
        )

        result = json.loads(response.choices[0].message.content)
        all_ideas = result.get('chart_ideas', [])

        # --- STEP 3: Smart Validation ---
        valid_ids = {q['data_id'] for q in questions}
        final_selection = []
        for idea in all_ideas:
            # Check if AI used valid data_ids from the survey
            if idea.get('row_id') in valid_ids:
                if idea.get('col_id') is None or idea.get('col_id') in valid_ids:
                    final_selection.append(idea)

        final_selection.sort(key=lambda x: x.get('importance_score', 0), reverse=True)
        return build_final_payload(final_selection[:50], numeric_id, survey_url, questions)

    except Exception as e:
        logger.error(f"Global protocol analysis failed: {str(e)}")
        return {"error": "AI could not generate protocol-aligned charts", "details": str(e)}
    
    except openai.OpenAIError as api_error:
        logger.error(f"OpenAI API error during analysis: {str(api_error)}")
        return {"error": "OpenAI API error", "details": str(api_error)}
    
    except openai.RateLimitError as api_error:
        logger.error(f"limit exceeded: {str(api_error)}")
        return {"error": "OpenAI API error", "details": str(api_error)}
    
def is_valid_hash(id_str: str) -> bool:
    """Check karta hai ki ID ek valid hash hai ya koi generic text."""
    if not id_str or not isinstance(id_str, str):
        return False
    # Agar ID mein spaces hain ya wo bahut choti hai, toh wo hash nahi hai
    if " " in id_str or len(id_str) < 10:
        return False
    # Sirf alphanumeric characters check karein
    return bool(re.match("^[a-zA-Z0-9_-]+$", id_str))

def build_final_payload(ideas_list: List[Dict], numeric_id: int, survey_url: str, questions: List[Dict]) -> Dict:
    logger.info(f"Building final payload. Total ideas: {len(ideas_list)}")
    # --- STEP 1: Create a Validation Map ---
    final_payload = {"analysis_results": []}
    valid_data_ids = {str(q.get('data_id')).strip().lower(): q.get('type', '').lower() for q in questions if q.get('data_id')}
    type_map = {str(q.get('data_id')).strip().lower(): q.get('type', '').lower() for q in questions if q.get('data_id')}
    text_types = ['stextbox', 'text', 'textarea', 'number', 'decimal']
    temp_list = []

    for idea in ideas_list:
        # AI se aayi hui IDs
        raw_row_id = str(idea.get('row_id', '')).strip().lower()
        raw_col_id = str(idea.get('col_id', '')).strip().lower() if idea.get('col_id') else None
        logger.info(f"Processing idea with row_id: {raw_row_id}, col_id: {raw_col_id}")
        logger.info(f"Valid data_ids from questions: {list(valid_data_ids.keys())[:5]}...")  
        # --- STEP 2: Strict Database Match Check ---
        
        # Check 1: Kya row_id database/questions mein hai?
        if raw_row_id not in valid_data_ids:
            logger.warning(f"DATABASE MISMATCH: row_id '{raw_row_id}' not found in questions. Skipping.")
            continue

        # Check 2: Agar col_id bheja hai, toh kya wo database mein hai?
        valid_col_id = None
        if raw_col_id:
            if raw_col_id in valid_data_ids:
                valid_col_id = raw_col_id
            else:
                # Agar col_id mismatch hai, toh pura idea discard (Strict policy)
                logger.warning(f"DATABASE MISMATCH: col_id '{raw_col_id}' not found. Skipping idea.")
                continue

        # --- STEP 3: Proceed with Chart Logic ---
        row_q_type = type_map.get(raw_row_id, '')
        col_q_type = type_map.get(valid_col_id, '') if valid_col_id else None

        ai_suggested = idea.get('suggested_chart_type')
        suggested_type = ai_suggested

        if not valid_col_id:
            if row_q_type in text_types:
                suggested_type = 'word_cloud'
            else:
                allowed_single = [
                    'pie_chart', 'donut_chart', 'radial_chart', 'polar_chart', 
                    'column_chart', 'bar_chart', 'treemap_chart'
                ]
                
                if ai_suggested in allowed_single:
                    suggested_type = ai_suggested
                else:
                    suggested_type = 'pie_chart' 
        else:
            # Correlations ke liye logic
            # ADDED: line_chart to allowed_multi
            allowed_multi = [
                'stack_chart', 'column_chart', 'bar_chart', 'area_chart', 
                'scatter_chart', 'bubble_chart', 'table', 'line_chart', 'frequency', 'radar_chart', 'heatmap_chart', 'box_plot_chart'
            ]
            
            if ai_suggested in allowed_multi:
                suggested_type = ai_suggested
            else:
                # Default fallback logic
                if row_q_type not in text_types and col_q_type not in text_types:
                    # Agar rating scale ya numeric hai toh line_chart fallback rakhein
                    if row_q_type in ['number', 'decimal', 'rating']:
                        suggested_type = 'line_chart'
                    else:
                        suggested_type = 'stack_chart'
                else:
                    suggested_type = 'column_chart'

        if suggested_type in ['stack_chart', 'table', 'scatter_chart', 'bubble_chart']:
            initial_show_type = 12  # Ye charts hamesha badi jagah mangte hain
        elif suggested_type in ['column_chart', 'bar_chart']:
            initial_show_type = 6
        else: 
            initial_show_type = 4

        # --- SPECIAL DYNAMIC RULES ---
        
        # 1. Word Cloud ko dynamic karein
        if suggested_type == 'word_cloud':
            # Agar text chota hai (stextbox) toh 6, agar bada hai (textarea) toh 12
            if row_q_type in ['stextbox', 'number']:
                initial_show_type = 6
            else:
                initial_show_type = 12

        # 2. Line/Area Chart Diversity
        if suggested_type in ['line_chart', 'area_chart']:
            # Single question ka trend hai toh 6 bhi chalega, multi-question hai toh 12
            initial_show_type = 12 if valid_col_id else 6

        # 3. Content Complexity Check (Agar options bahut zyada hain)

        stats_data = idea.get('stats', []) # Ye aapke payload se aayega
        if isinstance(stats_data, list) and len(stats_data) > 10:
            initial_show_type = 12

        graph_type, chart_draw_type = determine_types(suggested_type)
        dynamic_url = f"analytics/{graph_type}/{numeric_id}"
        current_row_type = None if (graph_type in ['table', 'word_cloud'] or suggested_type == 'frequency') else "count"

        temp_list.append({
            "id": len(temp_list) + 1,
            "survey_id": survey_url,
            "row_id": raw_row_id,
            "col_id": valid_col_id,
            "layer_id": None,
            "graph_type": graph_type,
            "chart_type": suggested_type,
            "chart_draw_type": chart_draw_type,
            "chart_row_type": current_row_type,
            "row_percent": 0,
            "col_percent": 0,
            "chart_url": dynamic_url,
            "layout_width": initial_show_type
        })

    # --- SEQUENTIAL GRID BALANCING LOGIC ---
    # Is logic se layout hamesha full-width (12) complete karega
    final_results = []
    i = 0
    while i < len(temp_list):
        current = temp_list[i]
        
        # Case 1: Full Width (12) - Seedha add karo
        if current["layout_width"] == 12:
            final_results.append(current)
            i += 1

        # Case 2: Half Width (6) - Pair dhundo
        elif current["layout_width"] == 6:
            if (i + 1) < len(temp_list) and temp_list[i+1]["layout_width"] == 6:
                final_results.append(current)
                final_results.append(temp_list[i+1])
                i += 2
            else:
                # Pair nahi mila toh full width kar do
                current["layout_width"] = 12
                final_results.append(current)
                i += 1

        # Case 3: One-Third Width (4) - Trio (3 items) dhundo
        elif current["layout_width"] == 4:
            if (i + 2) < len(temp_list) and temp_list[i+1]["layout_width"] == 4 and temp_list[i+2]["layout_width"] == 4:
                final_results.append(current)
                final_results.append(temp_list[i+1])
                final_results.append(temp_list[i+2])
                i += 3
            elif (i + 1) < len(temp_list) and temp_list[i+1]["layout_width"] == 4:
                # Do mile, toh dono ko 6-6 kar do (Half-Half)
                current["layout_width"] = 6
                temp_list[i+1]["layout_width"] = 6
                final_results.append(current)
                final_results.append(temp_list[i+1])
                i += 2
            else:
                # Akela bacha, full width kar do
                current["layout_width"] = 12
                final_results.append(current)
                i += 1

    # Final IDs assignment
    for index, item in enumerate(final_results):
        item["id"] = index + 1

    final_payload["analysis_results"] = final_results
    logger.info("total ideas processed for final payload: {}".format(len(ideas_list)))
    logger.info(f"Total ideas after layout balancing: {len(final_results)}")
    logger.info(f"Final payload built with {len(final_results)} insights.")
    logger.info(f"Final Payload Sample: {json.dumps(final_payload['analysis_results'][:3], indent=2)}")
    return final_payload


def determine_types(suggested_chart_type: str) -> tuple[str, str]:
    """
    User requirements ke basis par Graph Type aur Draw Type define karta hai.
    """
    if suggested_chart_type == 'word_cloud':
        return 'word_cloud', ''
    
    elif suggested_chart_type == 'table':
        return 'table', ''
    
    # NEW RULE: Frequency chart should have graph_type as 'table'
    elif suggested_chart_type == 'frequency':
        return 'table', ''
        
    else:
        graph_type = 'chart'
        draw_type = 'percent' if suggested_chart_type in ['pie_chart', 'donut_chart', 'radial_chart', 'polar_chart'] else 'count'
        return 'chart', draw_type