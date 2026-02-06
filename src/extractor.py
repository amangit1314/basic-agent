"""
Main extraction pipeline orchestrator.
Coordinates browser automation, content extraction, and AI summarization.
"""
import asyncio
from typing import List, Dict, Optional
from .browser import NoticeBrowser
from .gemini import GeminiSummarizer
from .utils import ExtractionUtils
from .config import logger, RELEVANT_KEYWORDS


async def extract_notices(
    url: str,
    keywords: List[str] = None,
    max_depth: int = 2,
    limit: Optional[int] = None,
) -> Dict:
    """
    Two-stage extraction pipeline:
      Stage 1 - Visit listing page, discover notice links matching keywords
      Stage 2 - Extract content from each notice, follow nested links, summarize with AI
    """
    # None = use defaults, empty list = no filtering
    if keywords is None:
        keywords = list(RELEVANT_KEYWORDS)
        logger.info(f"Using default keywords: {len(keywords)} keywords")
    elif not keywords:
        logger.info("Empty keyword list - keyword filtering disabled, will include all notices")
    else:
        logger.info(f"Using provided keywords: {len(keywords)} keywords")
    
    browser = NoticeBrowser()
    summarizer = GeminiSummarizer()

    try:
        await browser.start()

        # --- Stage 1: Discover notices ---
        logger.info(f"Stage 1: Scanning {url}")
        html = await browser.get_page_html(url)
        if not html:
            return _error_response("Failed to load listing page")

        all_links = browser.discover_links(html, url, keywords)
        total_found = len(all_links)

        # If keywords is empty, include all links (no filtering)
        if not keywords:
            keyword_links = all_links
            logger.info(f"No keyword filter applied - including all {total_found} discovered links")
        else:
            keyword_links = [l for l in all_links if l["matched_keywords"]]
            logger.info(f"Found {len(keyword_links)} keyword-matched links out of {total_found} total")
        
        if limit:
            keyword_links = keyword_links[:limit]
            logger.info(f"Applied limit: {limit}, processing {len(keyword_links)} notices")

        logger.info(
            f"Stage 2: Extracting {len(keyword_links)} notices "
            f"(of {total_found} total links found)"
        )

        # --- Stage 2: Extract each notice ---
        notices = []
        visited = {url}

        for i, link in enumerate(keyword_links):
            logger.info(f"[{i+1}/{len(keyword_links)}] {link['url']}")

            text, doc_type = await browser.get_page_text(link["url"])
            if not text or len(text) < 50:
                logger.warning(f"  Skipping - insufficient content ({len(text)} chars)")
                continue

            # Follow nested links for HTML pages
            nested_texts = []
            if doc_type == "HTML" and max_depth > 0:
                nested = await browser.follow_nested(
                    link["url"], 0, max_depth, visited
                )
                nested_texts = [n["text"] for n in nested]

            # Combine all text for summarization
            combined = text
            for nt in nested_texts:
                combined += "\n\n" + nt

            # AI summary with regex fallbacks
            summary = summarizer.summarize(combined)

            if not summary.get("auction_date"):
                dates = ExtractionUtils.extract_dates(combined)
                if dates:
                    summary["auction_date"] = dates[0]

            if not summary.get("reserve_price"):
                summary["reserve_price"] = ExtractionUtils.extract_reserve_price(
                    combined
                )

            if not summary.get("amount"):
                summary["amount"] = ExtractionUtils.extract_due_amount(combined)

            if not summary.get("notice_type"):
                summary["notice_type"] = ExtractionUtils.determine_notice_type(combined)

            notices.append({
                "title": link.get("title", "Notice"),
                "url": link["url"],
                "type": doc_type,
                "matched_keywords": link.get("matched_keywords", []),
                "summary": {
                    "borrower": summary.get("borrower"),
                    "amount": summary.get("amount"),
                    "property": summary.get("property"),
                    "auction_date": summary.get("auction_date"),
                    "reserve_price": summary.get("reserve_price"),
                    "bank": summary.get("bank"),
                    "notice_type": summary.get("notice_type"),
                },
                "full_text": combined[:5000],
            })

            await asyncio.sleep(1)  # Rate limiting

        # keyword_matches = sum of all matched keywords across all notices
        # This will be 0 if no keywords were provided (empty list)
        total_keyword_matches = sum(len(n["matched_keywords"]) for n in notices)
        
        return {
            "status": "success",
            "total_notices": total_found,
            "keyword_matches": total_keyword_matches,
            "notices": notices,
        }

    except Exception as e:
        logger.error(f"Extraction pipeline failed: {e}", exc_info=True)
        return _error_response(str(e))

    finally:
        await browser.stop()


def _error_response(message: str) -> Dict:
    return {
        "status": "error",
        "total_notices": 0,
        "keyword_matches": 0,
        "notices": [],
        "error": message,
    }
