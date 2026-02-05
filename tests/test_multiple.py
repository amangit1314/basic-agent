"""
Batch Testing Script - Test extraction from multiple URLs

Usage:
    python test_multiple.py

Edit the URLS list below to add your own URLs to test.
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auction_notice_extractor import extract_notices_direct, save_results

# =============================================================================
# EDIT THIS LIST TO ADD YOUR OWN URLS
# =============================================================================
URLS = [
    # SBI URLs
    "https://sbi.bank.in/web/sbi-in-the-news/auction-notices/arc-drt",
    "https://sbi.bank.in/web/sbi-in-the-news/auction-notices/sarfaesi",
    
    # Add more URLs here:
    # "https://www.bankofbaroda.in/tenders-auctions",
    # "https://www.pnbindia.in/auction-notices.html",
]
# =============================================================================


def main():
    print("\n" + "=" * 70)
    print("  AUCTION NOTICE EXTRACTOR - BATCH TEST")
    print("=" * 70)
    print(f"\n  Testing {len(URLS)} URL(s)...\n")
    
    results_summary = []
    
    for i, url in enumerate(URLS, 1):
        print("-" * 70)
        print(f"[{i}/{len(URLS)}] {url[:65]}{'...' if len(url) > 65 else ''}")
        print("-" * 70)
        
        try:
            notices = extract_notices_direct(url)
            
            if notices:
                filepath = save_results(notices, url)
                print(f"\n    [OK] Extracted: {len(notices)} notices")
                print(f"    [OK] With dates: {sum(1 for n in notices if n.get('auction_dates'))}")
                print(f"    [OK] With entities: {sum(1 for n in notices if n.get('entities'))}")
                print(f"\n    [OK] Saved to:")
                print(f"        {filepath}")
                
                results_summary.append({
                    "url": url,
                    "status": "OK",
                    "notices": len(notices),
                    "file": filepath
                })
            else:
                print("\n    [!] No notices found")
                results_summary.append({
                    "url": url,
                    "status": "EMPTY",
                    "notices": 0,
                    "file": None
                })
                
        except Exception as e:
            print(f"\n    [X] Error: {e}")
            results_summary.append({
                "url": url,
                "status": "ERROR",
                "notices": 0,
                "file": None,
                "error": str(e)
            })
        
        print()
    
    # Print summary
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"\n  Total URLs tested: {len(URLS)}")
    print(f"  Successful: {sum(1 for r in results_summary if r['status'] == 'OK')}")
    print(f"  Empty: {sum(1 for r in results_summary if r['status'] == 'EMPTY')}")
    print(f"  Errors: {sum(1 for r in results_summary if r['status'] == 'ERROR')}")
    print(f"  Total notices: {sum(r['notices'] for r in results_summary)}")
    
    print("\n" + "-" * 70)
    print("  RESULT FILES:")
    print("-" * 70)
    for r in results_summary:
        if r['file']:
            print(f"\n  {r['file']}")
    
    print("\n" + "=" * 70)
    print("  BATCH TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
