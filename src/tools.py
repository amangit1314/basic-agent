import json
import requests
import io
from typing import Type
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .config import logger, RELEVANT_KEYWORDS
from .models import WebScraperInput, ListingAnalyzerInput, ContentFetcherInput

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
        logger.info(f"WebScraper: Fetching {url}")
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            response = requests.get(url, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"WebScraper Error: {e}")
            return f"ERROR: {str(e)}"

class ListingAnalyzerTool(BaseTool if CREWAI_AVAILABLE else object):
    name: str = "listing_analyzer"
    description: str = "Scans HTML for links matching relevant keywords."
    args_schema: Type = ListingAnalyzerInput
    
    def _run(self, html_content: str, base_url: str) -> str:
        soup = BeautifulSoup(html_content, 'lxml')
        relevant_links = []
        for a_tag in soup.find_all('a', href=True):
            link_text = a_tag.get_text(strip=True)
            full_url = urljoin(base_url, a_tag['href'])
            found_keyword = next((kw for kw in RELEVANT_KEYWORDS if kw.lower() in link_text.lower()), None)
            
            if not found_keyword and len(link_text) < 15:
                parent = a_tag.find_parent('li') or a_tag.find_parent('td')
                if parent:
                    parent_text = parent.get_text(strip=True)
                    found_keyword = next((kw for kw in RELEVANT_KEYWORDS if kw.lower() in parent_text.lower()), None)
            
            if found_keyword:
                relevant_links.append({"title": link_text or "Notice", "url": full_url, "keyword_found": found_keyword})
        
        unique_links = {link['url']: link for link in relevant_links}.values()
        return json.dumps(list(unique_links))

class ContentFetcherTool(BaseTool if CREWAI_AVAILABLE else object):
    name: str = "content_fetcher"
    description: str = "Fetches text from a notice URL (handles HTML and PDF)."
    args_schema: Type = ContentFetcherInput
    
    def _run(self, url: str) -> str:
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60, verify=False)
            if url.lower().endswith('.pdf') or 'application/pdf' in response.headers.get('Content-Type', '').lower():
                return self._extract_pdf_text(response.content)
            return self._extract_html_text(response.text)
        except Exception as e:
            logger.error(f"ContentFetcher Error: {e}")
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
