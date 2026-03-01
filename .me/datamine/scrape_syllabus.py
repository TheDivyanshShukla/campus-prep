import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=0, i",
    "sec-ch-ua": "\"Opera GX\";v=\"127\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "Referer": "https://career-shiksha.com/"
}

def fetch_url(url, referer=None):
    headers = HEADERS.copy()
    if referer:
        headers["Referer"] = referer
        
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_main_page(html):
    soup = BeautifulSoup(html, "html.parser")
    branches = []
    
    # Find the main container (Parent 5 logic from analysis)
    # We look for a known header to locate the container
    header = soup.find(lambda t: t.name == 'h2' and "Mechanical Engineering" in t.get_text())
    if not header:
        print("Could not find main structure.")
        return []
        
    curr = header
    for i in range(5):
        curr = curr.parent
        if not curr: break
    parent_container = curr
    
    current_branch_name = None
    
    for child in parent_container.children:
        if child.name != 'div': continue
        
        # Check for headers
        headers = child.find_all("h2")
        for h in headers:
            text = h.get_text(strip=True)
            # Heuristic to identify branch headers
            if "Engineering" in text or "CS" in text or "AI" in text or "Information" in text:
                current_branch_name = text
                # Check if branch already exists (to avoid duplicates if structure is weird)
                if not any(b['name'] == current_branch_name for b in branches):
                    branches.append({
                        "name": current_branch_name,
                        "semesters": []
                    })
        
        # Check for buttons
        buttons = child.find_all("a", class_="elementor-button")
        if buttons and current_branch_name:
            # Add semesters to the current branch
            branch_obj = next((b for b in branches if b['name'] == current_branch_name), None)
            if branch_obj:
                for btn in buttons:
                    sem_name = btn.get_text(strip=True)
                    link = btn.get("href")
                    # Avoid duplicates
                    if not any(s['name'] == sem_name for s in branch_obj['semesters']):
                        branch_obj['semesters'].append({
                            "name": sem_name,
                            "link": link
                        })
                        
    return branches

def parse_semester_page(html):
    soup = BeautifulSoup(html, "html.parser")
    subjects = []
    
    # Find all h2 headers that look like subject headers
    # Pattern: "Syllabus of CODE (Name)"
    headers = soup.find_all("h2")
    
    for h2 in headers:
        text = h2.get_text(strip=True)
        if "Syllabus of" in text:
            # Parse subject info
            # Remove zero-width space if present
            text = text.replace('\u200b', '').strip()
            
            # Extract Code and Name
            # Example: Syllabus of BT-301 (Mathematics-III)
            match = re.search(r"Syllabus of\s+([A-Z0-9-]+)\s*\((.+)\)", text)
            if match:
                code = match.group(1)
                name = match.group(2)
            else:
                code = "UNKNOWN"
                name = text.replace("Syllabus of", "").strip()
            
            subject = {
                "code": code,
                "name": name,
                "pdf_url": None,
                "modules": []
            }
            
            # Parse content following the header
            curr = h2.next_sibling
            current_module = None
            module_content = []
            
            while curr:
                if not curr: break
                
                # Check if we hit the next subject header
                if curr.name == 'h2' and "Syllabus of" in curr.get_text(strip=True):
                    break
                
                # Skip NavigableStrings
                if isinstance(curr, str):
                     # If it's a significant text node, add it to content
                     if len(curr.strip()) > 5:
                         module_content.append(curr.strip())
                     curr = curr.next_sibling
                     continue
                
                if curr.name == 'div' and 'wp-block-file' in curr.get('class', []):
                    # PDF Link
                    a_tag = curr.find("a")
                    if a_tag:
                        subject['pdf_url'] = a_tag.get('href')
                
                elif curr.name == 'p':
                    p_text = curr.get_text(strip=True)
                    # Check if it's a module header
                    if "MODULE" in p_text.upper() or "UNIT" in p_text.upper():
                        # Save previous module
                        if current_module:
                            current_module['topics'] = module_content
                            subject['modules'].append(current_module)
                            module_content = []
                            
                        current_module = {
                            "title": p_text,
                            "topics": []
                        }
                    else:
                        # Regular paragraph, treat as content/topic
                        if len(p_text) > 5:
                            module_content.append(p_text)
                            
                elif curr.name == 'ul':
                    # List of topics
                    items = [li.get_text(strip=True) for li in curr.find_all("li")]
                    module_content.extend(items)
                    
                    # If we don't have a current module, create a default one
                    if not current_module:
                        current_module = {"title": "Topics", "topics": []}

                curr = curr.next_sibling
            
            # Append the last module
            if current_module:
                current_module['topics'] = module_content
                subject['modules'].append(current_module)
            elif module_content:
                subject['modules'].append({"title": "General", "topics": module_content})
            
            subjects.append(subject)
            
    return subjects

def main():
    print("Fetching main syllabus page...")
    main_url = "https://career-shiksha.com/syllabus-btech-rgpv/"
    html = fetch_url(main_url)
    if not html:
        return
    
    print("Parsing main page...")
    branches = parse_main_page(html)
    print(f"Found {len(branches)} branches.")
    
    # Iterate branches and semesters
    for branch in branches:
        print(f"\nProcessing Branch: {branch['name']}")
        for sem in branch['semesters']:
            print(f"  Fetching {sem['name']} -> {sem['link']}")
            
            # Skip if link is invalid or same page anchor
            if not sem['link'] or sem['link'].startswith("#"):
                print("    Skipping invalid link")
                continue
                
            sem_html = fetch_url(sem['link'], referer=main_url)
            if sem_html:
                subjects = parse_semester_page(sem_html)
                sem['subjects'] = subjects
                print(f"    Found {len(subjects)} subjects.")
            
            # Be polite
            time.sleep(1)
            
    # Save to JSON
    with open("rgpv_syllabus_data.json", "w", encoding="utf-8") as f:
        json.dump({"branches": branches}, f, indent=2, ensure_ascii=False)
        
    print("\nData saved to rgpv_syllabus_data.json")

if __name__ == "__main__":
    main()
