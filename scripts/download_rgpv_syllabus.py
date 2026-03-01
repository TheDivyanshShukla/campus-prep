import os
import re
import httpx
from playwright.sync_api import sync_playwright

# Configuration
BASE_URL = "https://www.rgpv.ac.in/Uni/frm_ViewScheme.aspx"
DOWNLOAD_DIR = "downloads"

# Strict mapping for known links (derived using LLM reasoning on the site data)
# This ensures zero mixing for known titles.
STRICT_MAPPING = {
    # AD
    "BTech Artificial Intelligence and Data Science": "AD",
    "Artificial Intelligence and Data Science VII Sem": "AD",
    "Syllabus BTech AIDS VIII Semester": "AD",
    "Syllabus Artificial Intelligence and Data Science": "AD",
    "Artificial Intelligence and Data Science": "AD",
    "BTech Artificial Intelligence and Data Science VII Sem": "AD",
    
    # AIML
    "BTech AI and Machine Learning": "AIML",
    "Artificial Intelligence and Machine Learning": "AIML",
    "Syallbus Artificial Intelligence Machine Learning": "AIML",
    "Syllabus BTech AIML VII Semester": "AIML",
    "Syllabus BTech AIML VIII Semester": "AIML",
    "Syllabus Btech CSE AI VIII Semester": "AIML",
    "Syllabus BTech CSE Artificial Intelligence VI Sem": "AIML",
    "Syllabus BTech V Sem CSE Artificial Intelligence": "AIML",
    "Syllabus BTech CSE Artificial Intelligence III Sem": "AIML",
    "Syllabus Btech CSE AI VII Semester": "AIML",
    "CSE Artificial Intelligence and Machine Learning": "AIML",

    # CY
    "B.Tech. SYllabus Cyber Security": "CY",
    "CSE Cyber Security": "CY",
    "Syllabus Cyber Security": "CY",
    "syllabus BTech Cyber security VI Semester": "CY",
    "Syllabus BTech Cyber Security VII Semester": "CY",
    "Syllabus BTech CSE Cyber Security VII Sem": "CY",
    "Syllabus BTech Cyber Security VIII Semester": "CY",
    "Cyber Security": "CY",

    # first_year
    "Sy BTech Common To all AB Group for 2022 Admitted": "first_year",
    "B.Tech Common To all A/B Group for 2017 Admitted": "first_year",
    "B.Tech Common To all A/B Group for 2018 Admitted": "first_year",

    # ECE - Strict to avoid mixing with "ECS" (Electronics and Computer Science)
    "B.Tech Electronics and communication Engg": "ECE",
    "Syllabus Electronics and communication Engg": "ECE",
    "Syllabus BTech Electronics and communication Engg": "ECE",

    # IT - Strict to avoid mixing with "CSIT"
    "B.Tech Information Technology": "IT",
    "BTech Information Technology Syllabus": "IT",
    "Syllabus Information Technology": "IT",
    "Syllabus B.Tech Information Technology": "IT",
    "B.Tech. Information Technology": "IT",
}

# Fallback configuration for other links
# Format: (folder_name, whitelist_regex, blacklist_list)
BRANCH_CONFIG = [
    ("first_year", r"Common To all A/B Group|Common To all AB Group", []),
    ("AD", r"Artificial\s*Intelligence\s*(and|&)?\s*Data\s*Science|\bAD\b", []),
    ("AIML", r"AI\s*(and|&)?\s*Machine\s*Learning|Artificial\s*Intelligence\s*(and|&)?\s*Machine\s*Learning|\bAIML\b", ["Robotics"]),
    ("CY", r"Cyber\s*Security", ["IOT", "Block Chain"]),
    ("ECE", r"Electronics\s*(and|&|-)?\s*communication\s*Engg", ["Computer Science"]),
    ("EX", r"Electrical\s*Electronics\s*Engineering|Electrical\s*(and|&)?\s*Electronics", []),
    ("CE", r"\bCivil\s*Engineering\b", []),
    ("ME", r"\bMechanical\s*Engineering\b", []),
    ("IT", r"\bInformation\s*Technology\b", ["Computer Science"]),
    # CSE matches MUST exclude specialized tags to avoid pollution
    ("CSE", r"\bComputer\s*Science\s*(and|&)?\s*Engineering\b|\bComputer\s*Science\s*Engg\b", ["IOT", "Cyber", "Data Science", "Business", "Design", "CSBS", "CSIT", "AI", "Machine Learning"])
]

# Links containing these keywords are considered "useless" or redundant
USELESS_KEYWORDS = r"VLSI|Practical|Sessional|Redundant|ACT|Scheme\s*2017|Scheme\s*2018"

def cleanup_misplaced_files():
    """Removes files that were previously wrongly categorized according to new stricter rules."""
    print("Performing global cleanup of misplaced/mixed files...")
    
    # 1. Specialized branches found in CSE
    cse_dir = os.path.join(DOWNLOAD_DIR, "CSE")
    if os.path.exists(cse_dir):
        for root, dirs, files in os.walk(cse_dir):
            for file in files:
                f_upper = file.upper()
                if any(x in f_upper for x in ["IOT", "CYBER", "AIDS", "AIML", "DATA SCIENCE", "MACHINE LEARNING", "CSBS", "CSIT", "CS DESIGN", "DESIGN"]):
                    path = os.path.join(root, file)
                    print(f"  Removing mismatched specialization from CSE: {path}")
                    os.remove(path)

    # 2. Electronics and Computer Science found in ECE
    ece_dir = os.path.join(DOWNLOAD_DIR, "ECE")
    if os.path.exists(ece_dir):
        for root, dirs, files in os.walk(ece_dir):
            for file in files:
                if "COMPUTER SCIENCE" in file.upper():
                    path = os.path.join(root, file)
                    print(f"  Removing Electronics & CS from ECE: {path}")
                    os.remove(path)

    # 3. CSIT found in IT
    it_dir = os.path.join(DOWNLOAD_DIR, "IT")
    if os.path.exists(it_dir):
        for root, dirs, files in os.walk(it_dir):
            for file in files:
                if "COMPUTER SCIENCE" in file.upper():
                    path = os.path.join(root, file)
                    print(f"  Removing CSIT from IT: {path}")
                    os.remove(path)

def cleanup_duplicates_per_folder():
    """Ensures only the most relevant file remains if multiple were downloaded."""
    print("Performing per-folder duplicate resolution...")
    for root, dirs, files in os.walk(DOWNLOAD_DIR):
        if len(files) > 1:
            # We have multiple files in one folder (branch/semester)
            # Strategy: Keep the one that doesn't have extra buzzwords if a pure one exists
            branch_name = os.path.basename(os.path.dirname(root))
            
            # Find the "best" file
            # Primary choice: Filename matches branch code or name exactly
            scored_files = []
            for f in files:
                score = 0
                f_upper = f.upper()
                # A file with "IOT" or "CYBER" in a folder that isn't IOT/CYBER gets -10
                if branch_name not in ["CY", "AIML", "AD"] and any(x in f_upper for x in ["IOT", "CYBER", "BLOCK CHAIN"]):
                    score -= 10
                # A file with just the branch name or code gets +5
                if branch_name in f_upper:
                    score += 5
                # A file that seems like a "Scheme" or "Redundant" gets -5
                if any(x in f_upper for x in ["SCHEME", "PRACTICAL", "SESSIONAL"]):
                    score -= 5
                
                scored_files.append((f, score))
            
            # Sort by score descending
            scored_files.sort(key=lambda x: x[1], reverse=True)
            best_file = scored_files[0][0]
            
            for f, score in scored_files[1:]:
                path = os.path.join(root, f)
                print(f"  Removing redundant file in {root}: {f} (score {score}, kept {best_file})")
                os.remove(path)

def download_file(url, filepath):
    print(f"  Downloading from URL: {url}")
    try:
        with httpx.Client(verify=False, timeout=60.0) as client:
            response = client.get(url)
            response.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"  Successfully saved.")
            return True
    except Exception as e:
        print(f"  Error downloading via httpx: {e}")
        return False

def download_syllabus():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    cleanup_misplaced_files()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"Navigating to {BASE_URL}...")
        page.goto(BASE_URL)

        print("Selecting B.Tech...")
        page.locator("#ContentPlaceHolder1_drpProgram").select_option("24")
        page.wait_for_load_state("networkidle")
        
        print("Selecting Grading System...")
        try:
            grading_selector = "#ContentPlaceHolder1_drpSearchGrading"
            if page.locator(grading_selector).is_visible():
                page.locator(grading_selector).select_option(label="Grading System")
            else:
                page.locator("#ContentPlaceHolder1_drpGrading").select_option(label="Grading System")
        except:
            print("Warning: Could not select Grading System via label.")

        page.wait_for_load_state("networkidle")

        print("Selecting Syllabus...")
        page.locator("#ContentPlaceHolder1_drpUploadType").select_option("2")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        print("Parsing results grid...")
        rows = page.locator("#ContentPlaceHolder1_gvViewAct > tbody > tr").all()
        
        current_semester = "Unknown"
        
        for row in rows:
            sem_header = row.locator(".lblHeadingFontType")
            if sem_header.count() > 0:
                header_text = sem_header.first.inner_text().strip()
                if header_text:
                    current_semester = header_text
                    print(f"\n--- {current_semester} ---")
            
            links = row.locator("a.link2").all()
            for link in links:
                link_text = link.inner_text().strip()
                
                # Filter out useless links
                if re.search(USELESS_KEYWORDS, link_text, re.IGNORECASE):
                    continue

                matched_branch = None
                
                # 1. Check strict mapping first
                if link_text in STRICT_MAPPING:
                    matched_branch = STRICT_MAPPING[link_text]
                
                # 2. Fallback to regex
                if not matched_branch:
                    for branch_code, pattern, exclusions in BRANCH_CONFIG:
                        if re.search(pattern, link_text, re.IGNORECASE):
                            if any(re.search(ex, link_text, re.IGNORECASE) for ex in exclusions):
                                continue
                            matched_branch = branch_code
                            break
                
                if matched_branch:
                    print(f"Found: {link_text} -> mapping to {matched_branch} ({current_semester})")
                    
                    safe_sem = "".join(x for x in current_semester if x.isalnum() or x in " -_").strip()
                    target_dir = os.path.join(DOWNLOAD_DIR, matched_branch, safe_sem)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    clean_name = "".join(x for x in link_text if x.isalnum() or x in " -_").strip().replace(" ", "_")
                    filename = f"{clean_name}.pdf"
                    filepath = os.path.join(target_dir, filename)
                    
                    if os.path.exists(filepath):
                        print(f"  Skipping (already exists): {filename}")
                        continue
                        
                    print(f"  Triggering download for {link_text}...")
                    try:
                        with page.expect_popup(timeout=60000) as popup_info:
                            link.click()
                        
                        popup_page = popup_info.value
                        popup_page.wait_for_load_state("load")
                        
                        pdf_url = popup_page.url
                        popup_page.close()
                        
                        if pdf_url and "frm_download_file" in pdf_url:
                            download_file(pdf_url, filepath)
                        else:
                            print(f"  Unexpected URL format: {pdf_url}")

                    except Exception as e:
                        print(f"  Error processing {link_text}: {e}")

        browser.close()

    # Final resolution of duplicates
    cleanup_duplicates_per_folder()
    
    print("\nDownload process complete.")

if __name__ == "__main__":
    download_syllabus()
