"""
Batch Testing Script - Deep Dive Extraction (Modular Version)

Usage:
    python test_multiple.py
"""
import os
import sys

# Ensure current directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import extract_notices_direct
from main import save_results

# List of URLs to test
URLS = [
    "https://sbi.bank.in/web/sbi-in-the-news/auction-notices/arc-drt",
    "https://sbi.bank.in/web/sbi-in-the-news/auction-notices/sarfaesi",
]

def main():
    print("\n" + "=" * 70)
    print("  DEEP DIVE EXTRACTOR - MODULAR BATCH TEST")
    print("=" * 70)
    
    # Set limit for testing
    TEST_LIMIT = 2
    
    for i, url in enumerate(URLS, 1):
        print(f"\n[{i}/{len(URLS)}] Processing: {url}")
        print("-" * 70)
        
        try:
            notices = extract_notices_direct(url, limit=TEST_LIMIT)
            
            if notices:
                filepath = save_results(notices, url)
                print(f"    [OK] Extracted: {len(notices)} notices")
                print(f"    [OK] Saved to: {filepath}")
            else:
                print(f"    [!] No relevant notices found matching keywords.")
                
        except Exception as e:
            print(f"    [X] Error: {e}")
    
    print("\n" + "=" * 70)
    print("  BATCH TEST COMPLETE")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    main()
