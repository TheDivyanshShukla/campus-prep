import requests
import os
import sqlite3

def download_samples(db_path="rgpv_papers.db", count=3):
    os.makedirs("samples", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT label, pdf_url FROM papers LIMIT ?", (count,))
    papers = cursor.fetchall()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for label, url in papers:
        filename = f"samples/{label}.pdf"
        print(f"Downloading {label}...")
        try:
            # Try direct download
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(r.content)
                print(f"  Saved to {filename}")
            else:
                # Try relative-to-base if direct fails (some URLs might be messed up)
                print(f"  Failed with status {r.status_code}")
        except Exception as e:
            print(f"  Error: {e}")
    
    conn.close()

if __name__ == "__main__":
    download_samples()
