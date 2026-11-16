import os
import json
from fastapi import logger
from venv import logger
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import requests
from io import BytesIO
from bs4 import BeautifulSoup, NavigableString
from dotenv import load_dotenv
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def hide_table_borders(table):
    """
    Table ki borders ko invisible karne ka foolproof tareeka.
    """
    tbl = table._tbl
    # tblPr (Table Properties) ko access ya create karein
    tblPr = tbl.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        tbl.insert(0, tblPr)
        
    # Borders element banayein
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'nil')
        tblBorders.append(border)
    
    tblPr.append(tblBorders)
load_dotenv()

def parse_html_to_docx(parent_paragraph, soup_element):
    """
    Recursive function jo malformed tags aur bold logic ko handle karta hai.
    """
    for child in soup_element.contents:
        if isinstance(child, NavigableString):
            # Text ko directly add karein
            parent_paragraph.add_run(str(child))
        elif child.name in ['strong', 'b']:
            # Bold handle karein
            run = parent_paragraph.add_run(child.get_text())
            run.bold = True
        elif child.name in ['p', 'div', 'span']:
            # Nested structure check karein
            parse_html_to_docx(parent_paragraph, child)
            if child.name == 'p':
                parent_paragraph.add_run('\n')
        else:
            # Agar koi unknown tag hai toh uska text le lo
            parent_paragraph.add_run(child.get_text())

def add_html_content(container, html_str):
    if not html_str:
        return
    if "</strong>" in html_str and "<strong>" not in html_str:
        html_str = html_str.replace("</strong>", "<strong>", 1)

    soup = BeautifulSoup(html_str, "html.parser")
    
    if hasattr(container, 'paragraphs'):
        target_p = container.paragraphs[0]
    else:
        target_p = container
        
    parse_html_to_docx(target_p, soup)

def clean_html(html_content):
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator="\n").strip()

def create_survey_docx(all_data: dict):
    doc = Document()
    
    # --- PAGE 1: HEADER ---
    header_table = doc.add_table(rows=1, cols=3)
    # --- YE LINE ADD KAREIN BORDERS HIDE KARNE KE LIYE ---
    hide_table_borders(header_table)
    header_table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Width settings (Inches mein balance karne ke liye)
    header_table.columns[0].width = Inches(1.0) # Left space
    header_table.columns[1].width = Inches(4.5) # Center (Titles)
    header_table.columns[2].width = Inches(1.5) # Right (Logo)
    
    center_cell = header_table.rows[0].cells[1]
    right_cell = header_table.rows[0].cells[2]

    # --- Project Title ---
    p1 = center_cell.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER # Text alignment
    run1 = p1.add_run(str(all_data.get('project_title', 'Project Title')).upper())
    run1.bold = True
    run1.font.size = Pt(14)

    # --- Survey Title ---
    p2 = center_cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER # Text alignment
    run2 = p2.add_run(str(all_data.get('survey_title', 'Survey Title')))
    run2.bold = True
    run2.font.size = Pt(12)
    
    # --- Logo ---
    logo_url = all_data.get('survey_logo')
    if logo_url:
        try:
            response = requests.get(logo_url, timeout=10)
            if response.status_code == 200:
                p_logo = right_cell.paragraphs[0]
                p_logo.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                run_logo = p_logo.add_run()
                run_logo.add_picture(BytesIO(response.content), width=Inches(0.8))
        except:
            right_cell.text = "[LOGO]"
            right_cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # --- CONSENT SECTION ---
    # 'CONSENT FORM:' ko bold aur space dene ke liye
    doc.add_paragraph("\n") 
    consent_title = doc.add_paragraph()
    run_ct = consent_title.add_run("CONSENT FORM:")
    run_ct.bold = True
    run_ct.font.size = Pt(12)
    
    consent_p = doc.add_paragraph()
    add_html_content(consent_p, all_data.get('survey_consent', ''))
    
    doc.add_page_break()

    # --- PAGE 2: QUESTIONS ---
    survey_sections = all_data.get("survey_data") or all_data.get("survey_responses") or []
    global_q_no = 1

    for section_item in survey_sections:
        # Section name aur Data nikaalna
        sec_name_raw = section_item.get('Section') or section_item.get('section', 'General')
        items_list = section_item.get("Data") or section_item.get("data", [])

        if not items_list:
            continue

        # --- 1. Dynamic Heading Selection ---
        # Agar JSON mein index section hai tabhi "Index Questionnaires" likhega
        if "index" in str(sec_name_raw).lower():
            doc.add_heading("Index Questionnaires", level=1)
            is_index = True
        else:
            # Agar index nahi hai toh purana title
            doc.add_heading("Survey Questionnaire", level=1)
            is_index = False

        # --- 2. Table Creation ---
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        
        # Headers
        headers = ["Q No.", "Question", "Options", "Remarks"]
        for i, h_text in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = h_text
            cell.paragraphs[0].runs[0].bold = True

        # --- 3. Section Row Logic ---
        sec_row = table.add_row().cells
        display_name = str(sec_name_raw).upper()
        
        # Agar index section hai toh "SECTION:" prefix nahi lagayenge
        if is_index:
            sec_row[0].text = display_name
        else:
            sec_row[0].text = f"{display_name}"
            
        sec_row[0].paragraphs[0].runs[0].bold = True
        sec_row[0].merge(sec_row[3])

        # --- 4. Data Rows ---
        for item in items_list:
            row = table.add_row().cells
            row[0].text = str(global_q_no)
            
            # Question Text (Clean: No Language Labels)
            q_raw = item.get("question", {})
            q_text = ""
            try:
                q_obj = json.loads(q_raw) if isinstance(q_raw, str) else q_raw
                if isinstance(q_obj, dict):
                    q_text = "\n".join([str(v) for v in q_obj.values() if v])
                else:
                    q_text = str(q_raw)
            except:
                q_text = str(q_raw)
            
            add_html_content(row[1], q_text)

            # Options Text (Clean: No Language Labels)
            ans_raw = item.get("ans_json_data")
            if ans_raw:
                try:
                    ans_obj = json.loads(ans_raw) if isinstance(ans_raw, str) else ans_raw
                    if isinstance(ans_obj, dict):
                        opts = []
                        for lang_content in ans_obj.values():
                            if isinstance(lang_content, dict):
                                answers = lang_content.get("answer", [])
                                opts.extend([o.replace("|", ". ") for o in answers])
                        add_html_content(row[2], "\n".join(opts))
                except:
                    pass
            
            global_q_no += 1
        
        # Har section ke baad thoda gap
        doc.add_paragraph("\n")

    # --- FILENAME AUR SAVING LOGIC ---
    clean_title = "".join(x for x in str(all_data.get('survey_title', 'survey')) if x.isalnum())
    filename = f"{clean_title}_{all_data.get('survey_id', '0')}.docx"

    # 1. Asli path yahan manually set karein (Taki koi confusion na rahe)
    target_dir = "/var/www/researchnimbliai/storage/app/public/surveyword"

    # 2. Folder ensure karein (Just in case Python ko na mile)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    # 3. Full path banayein
    file_path = os.path.join(target_dir, filename)

    # 4. Save karein
    doc.save(file_path)
    
    # Debugging ke liye (Optional: aapke server logs mein dikhega)
    print(f"DEBUG: Word file saved at {file_path}")
    logger.info(f"Word file saved at {file_path}")
    
    return filename