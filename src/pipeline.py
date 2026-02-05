import json
import time
from typing import List, Dict, Optional
from .config import logger
from .tools import WebScraperTool, ListingAnalyzerTool, ContentFetcherTool
from .utils import ExtractionUtils

def process_single_notice(link_data: Dict) -> Optional[Dict]:
    """Visit a single notice URL and extract details."""
    fetcher = ContentFetcherTool()
    content_text = fetcher._run(link_data['url'])
    if not content_text or len(content_text) < 50: return None
        
    return {
        "title": link_data['title'],
        "notice_type": ExtractionUtils.determine_notice_type(content_text),
        "matched_keyword": link_data['keyword_found'],
        "auction_dates": ExtractionUtils.extract_dates(content_text),
        "entities": ExtractionUtils.extract_entities(content_text),
        "source_url": link_data['url'],
        "content_excerpt": content_text[:500] + "..."
    }

def extract_notices_direct(url: str, limit: int = None) -> List[Dict]:
    """Execute the two-stage extraction pipeline."""
    logger.info(f"Starting Extraction Pipeline for {url}")
    
    # STAGE 1: Scan Listing Page
    scraper = WebScraperTool()
    html = scraper._run(url)
    if html.startswith("ERROR"): return []
    
    analyzer = ListingAnalyzerTool()
    links = json.loads(analyzer._run(html, url))
    
    if not links:
        logger.info("No relevant links found.")
        return []
        
    if limit:
        logger.info(f"Limiting to {limit} links.")
        links = links[:limit]
        
    results = []
    for i, link in enumerate(links):
        logger.info(f"[{i+1}/{len(links)}] Deep diving: {link['url']}")
        try:
            notice_data = process_single_notice(link)
            if notice_data: results.append(notice_data)
            time.sleep(1) # Rate limiting
        except Exception as e:
            logger.error(f"Failed {link['url']}: {e}")
            
    return results
