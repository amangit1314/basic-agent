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

        def get_match_score(text: str, is_pdf: bool) -> int:
            score = 0
            if not text: return 0
            text_lower = text.lower()
            
            # Check for specific keywords
            for kw in RELEVANT_KEYWORDS:
                kw_lower = kw.lower()
                if kw_lower in text_lower:
                    score += 10
                    # Higher score for strong keywords
                    if kw_lower in ['npa', 'sale', 'auction', 'stressed']: score += 5
                    break # Count one keyword match
                
                # Check variants
                for d in ["+", "_", "-", ""]:
                    if kw.lower().replace(" ", d) in text_lower:
                        score += 8
                        break
            
            if is_pdf: score += 15
            if "view" in text_lower or "download" in text_lower: score += 2
            
            return score

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
                
                is_pdf = href.lower().endswith('.pdf') or "pdf" in href.lower()
                
                # Calculate score based on text, URL, and parent text
                score = get_match_score(link_text, is_pdf)
                score += get_match_score(href, is_pdf) # Add URL match score
                
                # If low score but looks like a file/action, check parent
                if score < 10 and (len(link_text) < 30 or is_pdf):
                    parent = a_tag.find_parent(['td', 'li', 'div', 'tr', 'p'])
                    if parent:
                        parent_text = parent.get_text(" ", strip=True)
                        parent_score = get_match_score(parent_text, False)
                        if parent_score > 0: score += parent_score

                # Threshold for relevance
                if score >= 10:
                    # Determine key matched (just for reporting)
                    keyword_found = "High Score Match"
                    for kw in RELEVANT_KEYWORDS:
                        if kw.lower() in (link_text + href).lower():
                            keyword_found = kw
                            break
                            
                    relevant_links[full_url] = {
                        "title": link_text[:100] if link_text else "Notice",
                        "url": full_url,
                        "keyword_found": keyword_found,
                        "score": score,
                        "is_pdf": is_pdf
                    }
            
            # Sort by score/priority
            sorted_links = sorted(relevant_links.values(), key=lambda x: x['score'], reverse=True)
            logger.info(f"ListingAnalyzer: {len(sorted_links)} relevant links found")
            
            if not sorted_links:
                 # Fallback: if minimal links found, look for *any* PDF on the page
                 pdfs = [l for l in all_links if l['href'].lower().endswith('.pdf')]
                 if pdfs:
                     logger.info(f"ListingAnalyzer: Fallback found {len(pdfs)} PDFs")
                     for p in pdfs[:5]:
                         full = urljoin(base_url, p['href'])
                         relevant_links[full] = {"title": "PDF Document", "url": full, "keyword_found": "PDF Fallback", "score": 5}
                     sorted_links = list(relevant_links.values())

            return json.dumps(sorted_links)
                
        except Exception as e:
            logger.error(f"ListingAnalyzer Error: {e}")
            return json.dumps([])

class FirecrawlExtractorTool(BaseTool if CREWAI_AVAILABLE else object):
    name: str = "firecrawl_extractor"
    description: str = "Uses Firecrawl LLM-powered extraction to get structured fields from a URL."
    
    def _run(self, url: str) -> dict:
        app = get_firecrawl_app()
        if not app: return {}
        
        schema = {
            'type': 'object',
            'properties': {
                'bank': {'type': 'string', 'description': 'Name of the bank or institution issuing the notice.'},
                'borrower_name': {'type': 'string', 'description': 'Name of the primary borrower or company.'},
                'reserve_price': {'type': 'string', 'description': 'The reserve price amount (e.g. "17.50 Cr", "Rs. 1,00,000"). If multiple, take the highest value.'},
                'due_amount': {'type': 'string', 'description': 'Total dues or principal outstanding amount. Exclude dates.'},
                'auction_date': {'type': 'string', 'description': 'Date of the e-auction (e.g. "27.02.2026").'},
                'accounts': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'company': {'type': 'string', 'description': 'Name of the company/borrower in this specific row/section.'},
                            'reserve': {'type': 'string', 'description': 'Reserve price for this specific account.'},
                            'dues': {'type': 'string', 'description': 'Dues amount for this specific account.'}
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
