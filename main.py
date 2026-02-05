import os
import sys
import json
from datetime import datetime
from urllib.parse import urlparse
from src.pipeline import extract_notices_direct
from src.config import RELEVANT_KEYWORDS

def save_results(notices: list, url: str) -> str:
    """Save results to results/ folder with a unique name."""
    results_dir = os.path.join(os.getcwd(), "results")
    os.makedirs(results_dir, exist_ok=True)
    
    domain = urlparse(url).netloc.replace(".", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(results_dir, f"{domain}_{timestamp}.json")
    
    # notices is a list of NoticeBundle objects
    serializable_notices = [n.model_dump() for n in notices]
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(serializable_notices, f, indent=2, ensure_ascii=False)
    return filepath

def main():
    # Parse URLs and limit
    urls = []
    limit = None
    
    skip_next = False
    for i, arg in enumerate(sys.argv[1:], 1):
        if skip_next:
            skip_next = False
            continue
        if arg == "--limit":
            try:
                limit = int(sys.argv[i + 1])
                skip_next = True
            except:
                limit = 5
        elif not arg.startswith("--"):
            urls.append(arg)

    # Default URL if none provided
    if not urls:
        urls = ["https://sbi.bank.in/web/sbi-in-the-news/auction-notices/arc-drt"]

    print(f"\nKeywords: {', '.join(RELEVANT_KEYWORDS)}")
    print(f"Processing {len(urls)} target(s)...")
    
    for i, url in enumerate(urls, 1):
        print(f"\n--- [{i}/{len(urls)}] Target: {url} ---")
        try:
            notices = extract_notices_direct(url, limit=limit)
            
            if notices:
                path = save_results(notices, url)
                total_accounts = sum(n.account_count for n in notices)
                print(f"[OK] Extracted {len(notices)} notices (Total {total_accounts} accounts).")
                print(f"[OK] Saved to: {path}")
            else:
                print("[!] No notices found for this URL.")
        except Exception as e:
            print(f"[ERROR] Failed to process {url}: {e}")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
