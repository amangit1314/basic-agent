"""
Test Script for Auction Notice Extractor (CrewAI Implementation)

This script demonstrates and tests the extraction capabilities.

Two modes:
1. CrewAI Mode: Uses LLM-powered agent (requires OPENAI_API_KEY)
2. Direct Mode: Uses deterministic extraction pipeline (no LLM needed)
"""

import json
import os
import sys

# Add the current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auction_notice_extractor import (
    extract_notices_from_url,
    extract_notices_direct,
    CREWAI_AVAILABLE
)


def validate_notice_structure(notice: dict) -> bool:
    """Validate that a notice has the required structure."""
    required_fields = ['notice_type', 'auction_dates', 'entities', 'description', 'source_url']
    
    for field in required_fields:
        if field not in notice:
            print(f"  [X] Missing field: {field}")
            return False
    
    if not isinstance(notice['auction_dates'], list):
        print("  [X] auction_dates should be a list")
        return False
    
    if not isinstance(notice['entities'], list):
        print("  [X] entities should be a list")
        return False
    
    return True


def print_summary(notices: list):
    """Print a summary of extracted notices."""
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    
    print(f"\n[+] Total notices extracted: {len(notices)}")
    
    # Validate all notices
    valid_count = sum(1 for n in notices if validate_notice_structure(n))
    print(f"[+] Valid notices: {valid_count}/{len(notices)}")
    
    # Statistics
    with_dates = sum(1 for n in notices if n.get('auction_dates'))
    with_entities = sum(1 for n in notices if n.get('entities'))
    print(f"[+] Notices with dates: {with_dates}/{len(notices)}")
    print(f"[+] Notices with entities: {with_entities}/{len(notices)}")
    
    # Show sample notices
    if notices:
        print("\n" + "-" * 60)
        print("SAMPLE NOTICES (first 3):")
        print("-" * 60)
        
        for i, notice in enumerate(notices[:3]):
            print(f"\n[*] Notice {i+1}:")
            notice_type = notice.get('notice_type', '')
            print(f"   Type: {notice_type[:70]}{'...' if len(notice_type) > 70 else ''}")
            print(f"   Dates: {notice.get('auction_dates', [])}")
            entities = notice.get('entities', [])[:3]
            print(f"   Entities: {entities}{'...' if len(notice.get('entities', [])) > 3 else ''}")


def test_direct_extraction(url: str):
    """Test direct extraction mode (no LLM required)."""
    print("\n" + "=" * 60)
    print("TESTING DIRECT EXTRACTION MODE")
    print("=" * 60)
    print(f"\nURL: {url}")
    print("\nExtracting notices (this may take a few seconds)...")
    
    notices = extract_notices_direct(url)
    
    if notices:
        print(f"\n[OK] SUCCESS: Extracted {len(notices)} notices")
        print_summary(notices)
        return notices
    else:
        print("\n[FAIL] No notices extracted")
        return []


def test_crewai_extraction(url: str):
    """Test CrewAI agent extraction mode."""
    print("\n" + "=" * 60)
    print("TESTING CREWAI AGENT EXTRACTION MODE")
    print("=" * 60)
    
    if not CREWAI_AVAILABLE:
        print("\n[!] CrewAI not installed. Install with: pip install crewai crewai-tools")
        return []
    
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n[!] OPENAI_API_KEY not set. Set it to use CrewAI mode.")
        print("   Example: set OPENAI_API_KEY=your-api-key-here")
        return []
    
    print(f"\nURL: {url}")
    print("\nRunning CrewAI agent (this may take a minute)...")
    
    notices = extract_notices_from_url(url)
    
    if notices:
        print(f"\n[OK] SUCCESS: Extracted {len(notices)} notices")
        print_summary(notices)
        return notices
    else:
        print("\n[FAIL] No notices extracted")
        return []


def main():
    """
    Main test entry point.
    
    Usage:
        python test_extractor.py [URL] [--crewai] [--direct] [--json]
    
    Options:
        URL: The auction notices page URL
        --crewai: Use CrewAI agent mode (requires OPENAI_API_KEY)
        --direct: Use direct extraction mode (default)
        --json: Output only JSON (no human-readable summary)
    """
    print("\n" + "=" * 60)
    print("  AUCTION NOTICE EXTRACTOR - TEST SUITE")
    print("=" * 60)
    
    # Default URL
    default_url = "https://sbi.bank.in/web/sbi-in-the-news/auction-notices/arc-drt"
    
    # Parse arguments
    use_crewai = "--crewai" in sys.argv
    use_direct = "--direct" in sys.argv
    json_only = "--json" in sys.argv
    url = next((arg for arg in sys.argv[1:] if not arg.startswith("--")), default_url)
    
    # Default to direct mode
    if not use_crewai and not use_direct:
        use_direct = True
    
    # Run tests
    notices = []
    
    if use_direct:
        notices = test_direct_extraction(url)
    
    if use_crewai:
        notices = test_crewai_extraction(url)
    
    # Output JSON if requested
    if json_only and notices:
        print("\n" + "=" * 60)
        print("JSON OUTPUT:")
        print("=" * 60)
        print(json.dumps(notices, indent=2, ensure_ascii=False))
    
    # Final status
    print("\n" + "=" * 60)
    if notices:
        print("[OK] TEST COMPLETED SUCCESSFULLY")
    else:
        print("[FAIL] TEST FAILED - No notices extracted")
    print("=" * 60 + "\n")
    
    return len(notices) > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
