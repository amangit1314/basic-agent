"""
Test script to verify empty keywords handling fix.
Tests that empty keywords list returns ALL notices, not zero.
"""
import requests
import json

API_URL = "http://localhost:8080/extract"

def test_empty_keywords():
    """Test that empty keywords returns all notices"""
    print("=" * 60)
    print("TEST: Empty keywords should return ALL notices")
    print("=" * 60)
    
    payload = {
        "url": "https://www.omkaraarc.com/sale_process_note.php",
        "keywords": [],  # Empty list - should NOT filter
        "max_depth": 1,
        "limit": 5
    }
    
    print(f"\nRequest Payload:\n{json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(API_URL, json=payload, timeout=120)
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse Summary:")
            print(f"  Status: {data.get('status')}")
            print(f"  Total Notices Found: {data.get('total_notices')}")
            print(f"  Keyword Matches Count: {data.get('keyword_matches')}")
            print(f"  Notices Returned: {len(data.get('notices', []))}")
            
            # Verify fix
            if data.get('total_notices', 0) > 0 and len(data.get('notices', [])) > 0:
                print("\n✅ SUCCESS: Empty keywords returned notices")
                print(f"   Found {len(data.get('notices', []))} notices")
                
                # Check matched_keywords are empty
                first_notice = data.get('notices', [{}])[0]
                print(f"\n   First notice:")
                print(f"     Title: {first_notice.get('title', 'N/A')[:80]}")
                print(f"     URL: {first_notice.get('url', 'N/A')}")
                print(f"     Matched Keywords: {first_notice.get('matched_keywords', [])}")
                
                if first_notice.get('matched_keywords') == []:
                    print("\n✅ VERIFIED: matched_keywords is empty list (as expected)")
                else:
                    print("\n⚠️  WARNING: matched_keywords is not empty")
                    
                print(f"\n   keyword_matches counter: {data.get('keyword_matches')}")
                if data.get('keyword_matches') == 0:
                    print("✅ VERIFIED: keyword_matches is 0 (as expected)")
                    
            else:
                print("\n❌ FAILURE: Empty keywords returned zero notices")
                print("   This is the bug we're trying to fix!")
        else:
            print(f"\n❌ ERROR: API returned status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except requests.exceptions.Timeout:
        print("\n⏱️  TIMEOUT: Request took too long (>120s)")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        

def test_with_keywords():
    """Test that providing keywords still works (backward compatibility)"""
    print("\n\n" + "=" * 60)
    print("TEST: With keywords should filter as before")
    print("=" * 60)
    
    payload = {
        "url": "https://www.omkaraarc.com/sale_process_note.php",
        "keywords": ["NPA", "SARFAESI"],
        "max_depth": 1,
        "limit": 5
    }
    
    print(f"\nRequest Payload:\n{json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(API_URL, json=payload, timeout=120)
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse Summary:")
            print(f"  Status: {data.get('status')}")
            print(f"  Total Notices Found: {data.get('total_notices')}")
            print(f"  Keyword Matches Count: {data.get('keyword_matches')}")
            print(f"  Notices Returned: {len(data.get('notices', []))}")
            
            if len(data.get('notices', [])) > 0:
                first_notice = data.get('notices', [{}])[0]
                print(f"\n   First notice:")
                print(f"     Title: {first_notice.get('title', 'N/A')[:80]}")
                print(f"     Matched Keywords: {first_notice.get('matched_keywords', [])}")
                
                if len(first_notice.get('matched_keywords', [])) > 0:
                    print("\n✅ SUCCESS: Keywords filtering works correctly")
                else:
                    print("\n⚠️  WARNING: Notice has no matched keywords")
            else:
                print("\n⚠️  No notices returned with keyword filter")
        else:
            print(f"\n❌ ERROR: API returned status {response.status_code}")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")


if __name__ == "__main__":
    print("\n🔍 Testing ARC Notice Extractor - Empty Keywords Fix\n")
    
    # Check if server is running
    try:
        health = requests.get("http://localhost:8080/health", timeout=5)
        print(f"✅ Server is running: {health.json()}\n")
    except:
        print("❌ ERROR: Server is not running on http://localhost:8080")
        print("   Please start the server with: python app.py\n")
        exit(1)
    
    # Run tests
    test_empty_keywords()
    test_with_keywords()
    
    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)
