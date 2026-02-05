import json
import requests
import io
from typing import Type, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
from firecrawl import FirecrawlApp
from .config import logger, RELEVANT_KEYWORDS
from .models import WebScraperInput, ListingAnalyzerInput, ContentFetcherInput
from dotenv import load_dotenv

load_dotenv()
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

def get_firecrawl_app():
    if not FIRECRAWL_API_KEY:
        logger.warning("FIRECRAWL_API_KEY not found in environment.")
        return None
    return FirecrawlApp(api_key=FIRECRAWL_API_KEY)

# PDF Support
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

# CrewAI Support
try:
    from crewai.tools import BaseTool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    class BaseTool: pass

class WebScraperTool(BaseTool if CREWAI_AVAILABLE else object):
    name: str = "web_scraper"
    description: str = "Fetches HTML content from a given URL."
    args_schema: Type = WebScraperInput
    
    def _run(self, url: str) -> str:
        app = get_firecrawl_app()
        # Always try traditional scrape first for speed/reliability on simple listing pages
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        try:
            logger.info(f"WebScraper: Attempting traditional scrape for {url}")
            resp = requests.get(url, headers=headers, timeout=20, verify=False)
            if resp.status_code == 200 and len(resp.text) > 1000:
                logger.info(f"WebScraper: Traditional scrape successful ({len(resp.text)} bytes).")
                return resp.text
            logger.warning(f"Traditional scrape returned code {resp.status_code} and {len(resp.text)} bytes.")
        except Exception as e:
            logger.warning(f"Traditional scrape failed for {url}: {e}")

        # Firecrawl fallback
        if app:
            try:
                logger.info(f"WebScraper: Scraping {url} via Firecrawl")
                scrape_result = app.scrape_url(url, params={'formats': ['html']})
                html = scrape_result.get('html', "")
                if html:
                    logger.info(f"WebScraper: Firecrawl scrape successful ({len(html)} bytes).")
                    return html
            except Exception as e:
                logger.error(f"Firecrawl Scrape Error: {e}")
                
        return "ERROR: Scrape failed."

class ListingAnalyzerTool(BaseTool if CREWAI_AVAILABLE else object):
    name: str = "listing_analyzer"
    description: str = "Scans HTML for links matching relevant keywords."
    args_schema: Type = ListingAnalyzerInput
    
    def _run(self, html_content: str, base_url: str) -> str:
        """Find notice links that match keywords in their text, URL, or parent context."""
        relevant_links = {}

        # Function to match flexible keywords (handles "Web+Notice", "Web_Notice", etc)
        def matches_keyword(text: str) -> Optional[str]:
            if not text: return None
            text_lower = text.lower()
            for kw in RELEVANT_KEYWORDS:
                kw_lower = kw.lower()
                if kw_lower in text_lower: return kw
                # Delimiter variants
                for d in ["+", "_", "-", ""]:
                    variant = kw_lower.replace(" ", d)
                    if variant and variant in text_lower: return kw
            return None

        # Parse HTML with BeautifulSoup
        if not html_content or html_content.startswith("ERROR"):
            logger.error("ListingAnalyzer: Invalid HTML content")
            return json.dumps([])
        
        try:
            logger.info(f"ListingAnalyzer: Parsing {len(html_content)} bytes of HTML")
            soup = BeautifulSoup(html_content, 'lxml')
            all_links = soup.find_all('a', href=True)
            logger.info(f"ListingAnalyzer: Found {len(all_links)} total links")
            
            for a_tag in all_links:
                href = a_tag['href']
                full_url = urljoin(base_url, href)
                link_text = a_tag.get_text(" ", strip=True)
                
                # Check keyword in: 1) link text, 2) URL, 3) parent element text
                found_keyword = matches_keyword(link_text) or matches_keyword(href)
                
                if not found_keyword and len(link_text) < 30:
                    parent = a_tag.find_parent(['td', 'li', 'div', 'tr', 'p'])
                    if parent:
                        parent_text = parent.get_text(" ", strip=True)
                        found_keyword = matches_keyword(parent_text)
                
                if found_keyword:
                    relevant_links[full_url] = {
                        "title": link_text[:100] if link_text else "Notice",
                        "url": full_url,
                        "keyword_found": found_keyword
                    }
            
            logger.info(f"ListingAnalyzer: {len(relevant_links)} links matched keywords")
            
            if not relevant_links:
                sample = [a['href'][:50] for a in all_links[:5]]
                logger.info(f"ListingAnalyzer Sample: {sample}")
                
        except Exception as e:
            logger.error(f"ListingAnalyzer Error: {e}")

        return json.dumps(list(relevant_links.values()))

class FirecrawlExtractorTool(BaseTool if CREWAI_AVAILABLE else object):
    name: str = "firecrawl_extractor"
    description: str = "Uses Firecrawl LLM-powered extraction to get structured fields from a URL."
    
    def _run(self, url: str) -> dict:
        app = get_firecrawl_app()
        if not app: return {}
        
        schema = {
            'type': 'object',
            'properties': {
                'bank': {'type': 'string', 'description': 'Name of the bank or institution'},
                'borrower_name': {'type': 'string', 'description': 'Name of the primary borrower or company'},
                'reserve_price': {'type': 'string', 'description': 'The reserve price for the auction (e.g. 175.00 Cr)'},
                'due_amount': {'type': 'string', 'description': 'Total dues or principal outstanding. Do not capture dates here.'},
                'auction_date': {'type': 'string', 'description': 'Date of the e-auction'},
                'accounts': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'company': {'type': 'string'},
                            'reserve': {'type': 'string'},
                            'dues': {'type': 'string'}
                        }
                    }
                }
            }
        }
        
        try:
            logger.info(f"FirecrawlExtractor: Extracting structured data from {url}")
            # Use scrape with extract format for highest accuracy
            extract_result = app.scrape_url(url, params={
                'formats': ['extract'],
                'extract': {'schema': schema}
            })
            if 'extract' in extract_result:
                return extract_result['extract']
            if 'data' in extract_result and 'extract' in extract_result['data']:
                return extract_result['data']['extract']
            return extract_result
        except Exception as e:
            logger.error(f"Firecrawl Extract Error: {e}")
            return {}

class ContentFetcherTool(BaseTool if CREWAI_AVAILABLE else object):
    name: str = "content_fetcher"
    description: str = "Fetches text from a notice URL (handles HTML and PDF)."
    args_schema: Type = ContentFetcherInput
    
    def _run(self, url: str) -> str:
        app = get_firecrawl_app()
        if not app or url.lower().endswith('.pdf'):
            # Fallback for PDFs or if firecrawl missing
            try:
                response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60, verify=False)
                if url.lower().endswith('.pdf') or 'application/pdf' in response.headers.get('Content-Type', '').lower():
                    return self._extract_pdf_text(response.content)
                return self._extract_html_text(response.text)
            except Exception as e:
                logger.error(f"Fallback Fetcher Error: {e}")
                return ""
        
        try:
            logger.info(f"ContentFetcher: Scraping markdown via Firecrawl for {url}")
            # Use 'scrape' method if 'scrape_url' missing, but my test showed 'scrape_url' works
            scrape_result = app.scrape_url(url, params={'formats': ['markdown']})
            # Firecrawl v1 returns data in 'data' field or direct?
            # My test script output will tell, but usually it's scrape_result['data']['markdown'] or similar.
            # Let's be defensive.
            if 'data' in scrape_result:
                return scrape_result['data'].get('markdown', "")
            return scrape_result.get('markdown', "")
        except Exception as e:
            logger.error(f"Firecrawl Content Error: {e}")
            return ""

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        if not PYPDF_AVAILABLE: return "ERROR: PDF Support not installed"
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            return "\n".join([page.extract_text() for page in reader.pages])
        except Exception as e:
            logger.error(f"PDF Error: {e}"); return ""

    def _extract_html_text(self, html: str) -> str:
        soup = BeautifulSoup(html, 'lxml')
        for tag in ['script', 'style', 'nav', 'header', 'footer']:
            for el in soup.find_all(tag): el.decompose()
        return soup.get_text(separator=' ', strip=True)
