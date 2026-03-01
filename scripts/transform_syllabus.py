
import json
import re
from pathlib import Path

def map_semester(sem_str):
    roman_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8}
    match = re.search(r'([IVXLC]+)', sem_str.upper())
    return roman_map.get(match.group(1)) if match else None

def extract_branch_info(name_str):
    match = re.search(r'^(.*?)\((.*?)\)$', name_str)
    if match:
        full_name = match.group(1).strip()
        code = match.group(2).strip()
        return full_name, code
    
    # Fallback mappings
    if "InformationTechnology" in name_str:
        return "Computer Science & Information Technology", "CSIT"
    if "Artificial Intelligence &Machine Learning" in name_str:
        return "Artificial Intelligence & Machine Learning", "AIML"
        
    return name_str.strip(), name_str.strip()[:10]

def extract_unit_number(title):
    match = re.search(r'(?:Module|Unit|UNIT)\s*[-:]?\s*(\d+)', title)
    return int(match.group(1)) if match else None

def transform_data(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    transformed = {}

    for b_data in data.get('branches', []):
        b_name, b_code = extract_branch_info(b_data['name'])
        
        if b_code not in transformed:
            transformed[b_code] = {
                "name": b_name,
                "semesters": {}
            }
        
        for sem_data in b_data.get('semesters', []):
            sem_num = map_semester(sem_data['name'])
            if not sem_num: continue
            
            sem_num_str = str(sem_num)
            if sem_num_str not in transformed[b_code]["semesters"]:
                transformed[b_code]["semesters"][sem_num_str] = {}
            
            for subj_data in sem_data.get('subjects', []):
                s_code = subj_data['code']
                s_name = subj_data['name']
                
                # Resolve UNKNOWN codes
                if s_code == "UNKNOWN":
                    # Try to find something like CS-801 or CSIT-302
                    code_match = re.search(r'([A-Z]{2,4}[- ]?\d{3}[A-Z]?)', s_name)
                    if code_match:
                        s_code = code_match.group(1).replace(" ", "-")
                    else:
                        # Fallback for lab only or special cases
                        s_code = f"UNK-{abs(hash(s_name)) % 10000}"

                # Clean up name if it contains the code
                s_name_clean = s_name
                if s_code in s_name:
                    s_name_clean = re.sub(rf'^.*{re.escape(s_code)}[ -:]*', '', s_name).strip()
                
                # Units/Modules
                units = []
                for mod in subj_data.get('modules', []):
                    u_num = extract_unit_number(mod['title'])
                    if u_num is not None:
                        units.append({
                            "number": u_num,
                            "name": mod['title'],
                            "topics": mod.get('topics', [])
                        })
                
                transformed[b_code]["semesters"][sem_num_str][s_code] = {
                    "name": s_name_clean or s_name,
                    "pdf_url": subj_data.get('pdf_url'),
                    "units": units
                }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(transformed, f, indent=2)
    
    print(f"Transformation complete. Saved to {output_path}")

if __name__ == '__main__':
    input_file = r'c:\Users\shukl\Desktop\code\rgpv-live\.me\datamine\rgpv_syllabus_data.json'
    output_file = r'c:\Users\shukl\Desktop\code\rgpv-live\.me\datamine\cleaned_syllabus.json'
    transform_data(input_file, output_file)
