import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import os
from urllib.parse import urljoin
import time
import random

class RGPVScraper:
    def __init__(self, db_path="rgpv_papers.db"):
        self.base_url = "https://www.rgpvonline.com/"
        self.db_path = db_path
        self.headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "upgrade-insecure-requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.rgpvonline.com/"
        }
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS papers")
        cursor.execute("DROP TABLE IF EXISTS subjects")
        cursor.execute("DROP TABLE IF EXISTS branches")
        
        cursor.execute("""
            CREATE TABLE branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                branch_id INTEGER,
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                UNIQUE(code, branch_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER,
                label TEXT NOT NULL UNIQUE,
                year INTEGER NOT NULL,
                month TEXT,
                html_url TEXT NOT NULL,
                pdf_url TEXT NOT NULL,
                FOREIGN KEY (subject_id) REFERENCES subjects(id)
            )
        """)
        conn.commit()
        conn.close()

    def fetch_page(self, url, retries=3):
        for i in range(retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                if response.status_code == 200:
                    return response.text
                if response.status_code in (520, 429, 503):
                    wait = 3 * (i + 1)
                    print(f"  Server error {response.status_code} for {url}. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"  Failed to fetch {url}: Status {response.status_code}")
            except Exception as e:
                print(f"  Error fetching {url}: {e}")
                time.sleep(2)
        return None

    def parse_metadata(self, label):
        """
        Extracts year, month, code, and name from a label.
        Handles complex multi-branch codes like:
          CS-CT-CO-IT-CI-302-DISCRETE-STRUCTURE-DEC-2023
          BT-204-BASIC-CIVIL-ENGINEERING-JUN-2022
          AD-AL-AI-304-ARTIFICIAL-INTELLIGENCE-JUN-2025
        """
        # Must end with a year >= 2021
        year_match = re.search(r'(\d{4})$', label)
        if not year_match:
            return None
        year = int(year_match.group(1))
        if year < 2021:
            return None

        # Extract month
        month_match = re.search(r'-(JUN|DEC|MAY|NOV|OCT|MAR|APR|FEB|JAN|SEP|AUG|JUL)-\d{4}$', label, re.I)
        month = month_match.group(1).upper() if month_match else "UNKNOWN"

        # Strip trailing month-year from label
        if month_match:
            clean_label = label[:month_match.start()]
        else:
            clean_label = label[:year_match.start()].strip('-')

        parts = clean_label.split('-')
        
        # Find the first pure-numeric part (e.g. 302, 401, 101)
        num_index = -1
        for i, p in enumerate(parts):
            if re.match(r'^\d{3,}$', p):
                num_index = i
                break

        if num_index == -1:
            # No numeric suffix found — skip
            return None

        # code is EXACTLY the original label up to and including the number (e.g. 'CS-CT-CO-302')
        code = "-".join(parts[:num_index + 1])
        name_parts = parts[num_index + 1:]
        name = " ".join(name_parts).replace('-', ' ').strip()

        return {
            "year": year,
            "month": month,
            "code": code,
            "name": name.title() if name else "Unknown Subject"
        }

    def scrape_branch(self, branch_id, branch_name, branch_code, url, conn):
        print(f"Scraping Branch: {branch_name} ({branch_code})")
        # Strip fragment from URL before fetching
        clean_url = url.split('#')[0]
        html = self.fetch_page(clean_url)
        if not html:
            return

        soup = BeautifulSoup(html, 'html.parser')
        
        # Search the ENTIRE page for all links — don't limit to a single div
        links = soup.find_all('a', href=True)

        cursor = conn.cursor()
        count = 0

        seen_hrefs = set()
        for a in links:
            href = a['href']
            label = a.get_text(strip=True)

            # Only paper links: must be .html paths under /be/ /btech/ etc.
            if not href.endswith('.html'):
                continue
            
            # Avoid branch navigation links (they contain 'question-papers')
            if 'question-papers' in href.lower():
                continue
            
            # Must be under a paper path
            if not any(x in href.lower() for x in ['/be/', '/btech/', '/bt/', '/bs/']):
                continue

            # Deduplicate by href on this branch scrape
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            meta = self.parse_metadata(label)
            if not meta:
                continue

            code = meta['code']  # Keep the FULL multi-branch code as-is (e.g. CS-CT-CO-302)

            # Insert subject using full code — allows shared papers to be matched by code later
            cursor.execute(
                "INSERT OR IGNORE INTO subjects (code, name, branch_id) VALUES (?, ?, ?)",
                (code, meta['name'], branch_id)
            )
            cursor.execute("SELECT id FROM subjects WHERE code = ? AND branch_id = ?", (code, branch_id))
            row = cursor.fetchone()
            if not row:
                continue
            subject_id = row[0]

            pdf_href = href.replace('.html', '.pdf')
            full_html_url = urljoin(self.base_url, href)
            full_pdf_url = urljoin(self.base_url, pdf_href)

            try:
                cursor.execute("""
                    INSERT INTO papers (subject_id, label, year, month, html_url, pdf_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (subject_id, label, meta['year'], meta['month'], full_html_url, full_pdf_url))
                count += 1
            except sqlite3.IntegrityError:
                pass  # Duplicate label (same paper linked from multiple branch pages)

        conn.commit()
        print(f"  Found {count} new papers.")
        time.sleep(random.uniform(0.5, 1.5))

    def run(self):
        print("Discovering all branches from homepage...")
        html = self.fetch_page(self.base_url)
        if not html:
            print("ERROR: Could not fetch homepage.")
            return

        soup = BeautifulSoup(html, 'html.parser')
        
        branch_links = []
        
        # Find the "Select BTECH Branch" section
        btech_header = soup.find(lambda tag: tag.name == "h2" and "Select BTECH Branch" in tag.text)
        if btech_header:
            card = btech_header.find_parent('div', class_='card')
            if card:
                for a in card.find_all('a', href=True):
                    name = a.get_text(strip=True)
                    url = urljoin(self.base_url, a['href'])

                    # Extract branch code: prefer (XX) pattern in name
                    code_match = re.search(r'\(([^)]+)\)', name)
                    if code_match:
                        code = code_match.group(1).strip().upper()
                    else:
                        # Use first word of name
                        code = name.split()[0].upper()
                    
                    # Special cases
                    if "1st Year" in name or "ALL Branch" in name:
                        code = "BT"
                    elif "E (" in name:  # "E (EC EE EEE EI EX)"
                        code = "ELEC"    # Use a single combined code

                    branch_links.append((name, code, url))

        print(f"Found {len(branch_links)} branches.\n")

        conn = sqlite3.connect(self.db_path)

        for name, code, url in branch_links:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO branches (name, code, url) VALUES (?, ?, ?)", (name, code, url))
            conn.commit()
            cursor.execute("SELECT id FROM branches WHERE code = ?", (code,))
            res = cursor.fetchone()
            if res:
                self.scrape_branch(res[0], name, code, url, conn)

        self.generate_report(conn)
        conn.close()
        print("\nAll done!")

    def generate_report(self, conn):
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM branches")
        bc = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM subjects")
        sc = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM papers")
        pc = cursor.fetchone()[0]
        print(f"\n--- Scrape Report ---")
        print(f"Branches: {bc}")
        print(f"Subjects: {sc}")
        print(f"Papers:   {pc}")


if __name__ == "__main__":
    scraper = RGPVScraper(db_path=".me/datamine/rgpv_papers.db")
    scraper.run()
