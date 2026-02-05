import json
import time
from typing import List, Dict, Optional
from .config import logger
from .tools import WebScraperTool, ListingAnalyzerTool, ContentFetcherTool, FirecrawlExtractorTool
from .utils import ExtractionUtils
from .models import NoticeImportant, NoticeBundle, NestedDoc

def process_single_notice(link_data: Dict) -> Optional[NoticeBundle]:
    """Visit a single notice URL and extract details using Firecrawl."""
    fetcher = ContentFetcherTool()
    extractor = FirecrawlExtractorTool()
    
    # Get raw content for fallback and display
    content_text = fetcher._run(link_data['url'])
    if not content_text or len(content_text) < 50: return None
    
    # Attempt high-accuracy LLM extraction via Firecrawl
    extracted_data = extractor._run(link_data['url'])
    
    # Map high-level fields or fallback to regex
    bank = extracted_data.get('bank') or "State Bank of India"
    title = extracted_data.get('title') or link_data.get('title')
    
    important = NoticeImportant(
        title=title,
        bank=bank,
        company_name=extracted_data.get('borrower_name'),
        borrower_name=extracted_data.get('borrower_name'),
        auction_date=extracted_data.get('auction_date'),
        reserve_price=extracted_data.get('reserve_price'),
        due_amount=extracted_data.get('due_amount'),
        city=extracted_data.get('city')
    )
    
    # Fallback to regex for missing critical fields
    if not important.auction_date:
        dates = ExtractionUtils.extract_dates(content_text)
        if dates: important.auction_date = dates[0]
    
    if not important.reserve_price:
        important.reserve_price = ExtractionUtils.extract_reserve_price(content_text)
    
    if not important.due_amount:
        important.due_amount = ExtractionUtils.extract_due_amount(content_text)

    # Handle multiple accounts if found
    all_accounts = []
    llm_accounts = extracted_data.get('accounts', [])
    if llm_accounts:
        for acc in llm_accounts:
            all_accounts.append(NoticeImportant(
                company_name=acc.get('company'),
                reserve_price=acc.get('reserve'),
                due_amount=acc.get('dues'),
                bank=bank,
                auction_date=important.auction_date
            ))
    
    if not all_accounts and important.company_name:
        all_accounts.append(important)

    return NoticeBundle(
        notice_url=link_data['url'],
        important=important,
        all_accounts=all_accounts,
        account_count=len(all_accounts),
        markdown=content_text,
        nested=[]
    )

def extract_notices_direct(url: str, limit: int = None) -> List[NoticeBundle]:
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
            bundle = process_single_notice(link)
            if bundle: results.append(bundle)
            time.sleep(1) # Rate limiting
        except Exception as e:
            logger.error(f"Failed {link['url']}: {e}")
            
    return results
