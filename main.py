import os
import sys
import json
from datetime import datetime
from urllib.parse import urlparse
from src.pipeline import extract_notices_direct
from src.config import RELEVANT_KEYWORDS

def save_results(notices: list, url: str) -> str:
    """Save results to results/ folder."""
    results_dir = os.path.join(os.getcwd(), "results")
    os.makedirs(results_dir, exist_ok=True)
    
    domain = urlparse(url).netloc.replace(".", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(results_dir, f"DEEP_{domain}_{timestamp}.json")
    
    data = {
        "metadata": {
            "source_url": url,
            "extraction_time": datetime.now().isoformat(),
            "keywords": RELEVANT_KEYWORDS,
            "count": len(notices)
        },
        "notices": notices
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath

def main():
    default_url = "https://sbi.bank.in/web/sbi-in-the-news/auction-notices/arc-drt"
    url = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else default_url
    
    limit = None
    if "--limit" in sys.argv:
        try: limit = int(sys.argv[sys.argv.index("--limit") + 1])
        except: limit = 5

    print(f"\nTarget: {url}")
    print(f"Keywords: {', '.join(RELEVANT_KEYWORDS)}")
    
    notices = extract_notices_direct(url, limit=limit)
    
    if notices:
        path = save_results(notices, url)
        print(f"\n[OK] Extracted {len(notices)} notices.")
        print(f"[OK] Saved to: {path}")
    else:
        print("\n[!] No notices found.")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
