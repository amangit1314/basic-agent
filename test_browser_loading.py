"""Quick diagnostic to test if browser can load the ARC website"""
import asyncio
from src.browser import NoticeBrowser
from src.config import logger

async def test_browser_loading():
    url = "https://www.omkaraarc.com/sale_process_note.php"
    
    print(f"Testing browser loading for: {url}")
    print("=" * 60)
    
    browser = NoticeBrowser()
    try:
        await browser.start()
        print("✅ Browser started successfully")
        
        print(f"\n📄 Attempting to load page...")
        html = await browser.get_page_html(url)
        
        if html:
            print(f"✅ Page loaded successfully!")
            print(f"   HTML length: {len(html)} bytes")
            print(f"   Preview: {html[:200]}...")
        else:
            print("❌ Failed to load page (returned empty)")
            print("   Check the error logs above for details")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await browser.stop()
        print("\n✅ Browser stopped")

if __name__ == "__main__":
    asyncio.run(test_browser_loading())
