# """
# Notice Extraction Pipeline — Simple, Linear, Cheap
# """

# import asyncio
# import json
# import os
# from datetime import datetime
# from urllib.parse import urlparse
# from typing import List, Optional

# from .browser import NoticeBrowser
# from .llm import LLMClient  # renamed from gemini.py
# from .models import NoticeData, ExtractionResult
# from .utils import ExtractionUtils
# from .config import RELEVANT_KEYWORDS, PAGE_DELAY_SECONDS, logger


# class NoticeExtractionPipeline:
#     """
#     Linear pipeline: crawl → filter → extract → done.
#     No ReAct loop. No LLM reasoning calls. No state machine.
#     """

#     def __init__(
#         self,
#         url: str,
#         keywords: Optional[List[str]] = None,
#         limit: Optional[int] = None,
#         provider: str = "gemini",
#     ):
#         self.url = url
#         self.keywords = keywords or list(RELEVANT_KEYWORDS)
#         self.limit = limit
#         self.browser = NoticeBrowser()
#         self.llm = LLMClient(provider=provider)

#     async def run(self) -> ExtractionResult:
#         """
#         The whole pipeline. No decisions, no state machine.
#         Just: crawl → filter → extract → done.
#         """
#         notices = []
#         failed_urls = []

#         await self.browser.start()

#         try:
#             # Step 1: Get listing page HTML
#             logger.info(f"Step 1: Loading listing page: {self.url}")
#             html = await self.browser.get_page_html(self.url)
#             if not html:
#                 logger.error(f"Failed to load {self.url}")
#                 return self._build_result(notices)

#             # Step 2: Find + filter links by keywords
#             logger.info("Step 2: Discovering notice links")
#             all_links = self.browser.discover_links(html, self.url, self.keywords)
            
#             # Remove listing page itself
#             links = [l for l in all_links if l["url"] != self.url]
            
#             # Apply limit
#             if self.limit:
#                 links = links[:self.limit]

#             logger.info(f"Found {len(all_links)} links, processing {len(links)}")

#             if not links:
#                 logger.info("No matching links found")
#                 return self._build_result(notices)

#             # Step 3: Visit each link and extract data
#             logger.info(f"Step 3: Extracting data from {len(links)} notices")
            
#             for i, link in enumerate(links, 1):
#                 logger.info(f"  [{i}/{len(links)}] {link['title'][:60]}...")
                
#                 try:
#                     notice = await self._process_single_notice(link)
#                     if notice:
#                         notices.append(notice)
#                 except Exception as e:
#                     logger.error(f"  Failed: {link['url']} — {e}")
#                     failed_urls.append(link["url"])

#                 await asyncio.sleep(PAGE_DELAY_SECONDS)

#         finally:
#             await self.browser.stop()

#         result = self._build_result(notices)
#         result.failed_urls = failed_urls
#         return result

#     async def _process_single_notice(self, link: dict) -> Optional[NoticeData]:
#         """Read one notice page and extract structured data."""
        
#         # Read content (handles HTML + PDF transparently)
#         text, doc_type, nested_links = await self.browser.get_page_text(link["url"])

#         if not text or len(text) < 50:
#             logger.info(f"  Skipping — insufficient content ({len(text)} chars)")
#             return None

#         # LLM extraction (the ONLY LLM call per notice)
#         notice = self.llm.extract_notice_data(
#             text=text,
#             source_url=link["url"],
#             source_type=doc_type,
#         )

#         # Regex fallbacks for missing fields
#         notice = self._apply_regex_fallbacks(notice, text)
#         notice.nested_links = nested_links or []

#         name = notice.company_name or notice.borrower_name or "Unknown"
#         logger.info(f"  ✓ Extracted: {name}")

#         return notice

#     def _apply_regex_fallbacks(self, notice: NoticeData, text: str) -> NoticeData:
#         """Same as your existing code — this part is good."""
#         # ... (keep your existing _apply_regex_fallbacks exactly as-is)
#         # Just move it here from agent.py
#         from .models import DateInfo, AmountInfo

#         regex_dates = ExtractionUtils.extract_dates(text)
#         if not notice.dates:
#             for i, d in enumerate(regex_dates[:5]):
#                 label = "auction_date" if i == 0 else f"date_{i + 1}"
#                 notice.dates.append(DateInfo(label=label, value=d))

#         if not notice.auction_date and regex_dates:
#             notice.auction_date = regex_dates[0]

#         has_reserve = any("reserve" in a.label.lower() for a in notice.amounts)
#         regex_reserve = ExtractionUtils.extract_reserve_price(text)
#         if not has_reserve and regex_reserve:
#             notice.amounts.append(AmountInfo(label="reserve_price", value=regex_reserve))
#         if not notice.reserve_price and regex_reserve:
#             notice.reserve_price = regex_reserve

#         has_dues = any("due" in a.label.lower() or "outstanding" in a.label.lower() for a in notice.amounts)
#         regex_dues = ExtractionUtils.extract_due_amount(text)
#         if not has_dues and regex_dues:
#             notice.amounts.append(AmountInfo(label="total_dues", value=regex_dues))
#         if not notice.due_amount and regex_dues:
#             notice.due_amount = regex_dues

#         if not notice.notice_type:
#             notice.notice_type = ExtractionUtils.determine_notice_type(text)

#         return notice

#     def _build_result(self, notices: list) -> ExtractionResult:
#         return ExtractionResult(
#             source_url=self.url,
#             total_notices_found=len(notices),
#             notices=notices,
#         )

#     def save_results(self, result: ExtractionResult) -> str:
#         """Save to JSON file."""
#         results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
#         os.makedirs(results_dir, exist_ok=True)

#         domain = urlparse(result.source_url).netloc.replace(".", "_")
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         filepath = os.path.join(results_dir, f"{domain}_{timestamp}.json")

#         with open(filepath, "w", encoding="utf-8") as f:
#             json.dump(
#                 result.model_dump(exclude={"notices": {"__all__": {"raw_text_snippet"}}}),
#                 f, indent=2, ensure_ascii=False,
#             )
#         return filepath


# ## What Changed and Why
# # --------------------------------------------
# # BEFORE (Your ReAct Agent):
# # ─────────────────────────────────────────────
# # Step 1:  LLM decides → "navigate"        💰 LLM call
# # Step 2:  LLM decides → "find_links"      💰 LLM call  
# # Step 3:  LLM decides → "read_page"       💰 LLM call
# # Step 4:  LLM decides → "extract_data"    💰 LLM call (useful!)
# # Step 5:  LLM decides → "read_page"       💰 LLM call
# # Step 6:  LLM decides → "extract_data"    💰 LLM call (useful!)
# # Step 7:  LLM decides → "done"            💰 LLM call

# # = 7 LLM calls for 2 notices (5 wasted on decisions)


# # AFTER (Linear Pipeline):
# # ─────────────────────────────────────────────
# # Step 1:  Navigate           (code, free)
# # Step 2:  Find links         (code, free)
# # Step 3:  Read page 1        (code, free)
# # Step 4:  Extract notice 1   💰 LLM call (useful!)
# # Step 5:  Read page 2        (code, free)
# # Step 6:  Extract notice 2   💰 LLM call (useful!)
# # Done.

# # = 2 LLM calls for 2 notices (0 wasted)


"""
Notice Extraction Pipeline — Simple, Linear, Cheap
"""

import asyncio
import json
import os
from datetime import datetime
from urllib.parse import urlparse
from typing import List, Optional

from .browser import NoticeBrowser
from .llm import LLMClient
from .models import NoticeData, ExtractionResult, DateInfo, AmountInfo
from .utils import ExtractionUtils
from .config import RELEVANT_KEYWORDS, PAGE_DELAY_SECONDS, logger


# At least 2 of these must appear in page text to consider it an NPA notice
RELEVANCE_SIGNALS = [
    "reserve price", "auction", "sarfaesi", "npa", "e-auction",
    "outstanding", "borrower", "possession", "stressed loan",
    "secured asset", "sale notice", "mortgagor", "drt",
    "swiss challenge", "non-performing", "recovery", "tender for sale",
    "sale of secured", "debt recovery", "assignment of debt",
    "total dues", "earnest money", "emd",
]

MIN_RELEVANCE_SIGNALS = 2


class NoticeExtractionPipeline:
    """
    Linear pipeline: crawl → filter → relevance check → extract → validate → done.
    """

    def __init__(
        self,
        url: str,
        keywords: Optional[List[str]] = None,
        limit: Optional[int] = None,
        provider: str = "gemini",
    ):
        self.url = url
        self.keywords = keywords or list(RELEVANT_KEYWORDS)
        self.limit = limit
        self.browser = NoticeBrowser()
        self.llm = LLMClient(provider=provider)

    async def run(self) -> ExtractionResult:
        notices = []
        failed_urls = []
        skipped_irrelevant = 0
        skipped_no_borrower = 0

        await self.browser.start()

        try:
            # Step 1: Get listing page HTML
            logger.info(f"Step 1: Loading listing page: {self.url}")
            html = await self.browser.get_page_html(self.url)
            if not html:
                logger.error(f"Failed to load {self.url}")
                return self._build_result(notices)

            # Step 2: Find + filter links by keywords
            logger.info("Step 2: Discovering notice links")
            all_links = self.browser.discover_links(html, self.url, self.keywords)

            # Remove listing page itself
            links = [l for l in all_links if l["url"] != self.url]

            # Apply limit
            if self.limit:
                links = links[:self.limit]

            logger.info(f"Found {len(all_links)} links, processing {len(links)}")

            if not links:
                logger.info("No matching links found")
                return self._build_result(notices)

            # Step 3: Visit each link, check relevance, extract data
            logger.info(f"Step 3: Extracting data from {len(links)} notices")

            for i, link in enumerate(links, 1):
                logger.info(f"  [{i}/{len(links)}] {link['title'][:60]}...")

                try:
                    notice = await self._process_single_notice(link)
                    if notice == "irrelevant":
                        skipped_irrelevant += 1
                    elif notice == "no_borrower":
                        skipped_no_borrower += 1
                    elif notice:
                        notices.append(notice)
                except Exception as e:
                    logger.error(f"  Failed: {link['url']} — {e}")
                    failed_urls.append(link["url"])

                await asyncio.sleep(PAGE_DELAY_SECONDS)

        finally:
            await self.browser.stop()

        # Log summary
        logger.info(
            f"Done: {len(notices)} extracted, "
            f"{skipped_irrelevant} skipped (irrelevant), "
            f"{skipped_no_borrower} skipped (no borrower), "
            f"{len(failed_urls)} failed"
        )

        result = self._build_result(notices)
        result.failed_urls = failed_urls
        return result

    async def _process_single_notice(self, link: dict):
        """
        Read one notice page and extract structured data.
        
        Returns:
            NoticeData — successful extraction
            "irrelevant" — page is not an NPA notice
            "no_borrower" — NPA notice but no company/borrower found
            None — insufficient content
        """
        # Read content (handles HTML + PDF transparently)
        text, doc_type, nested_links = await self.browser.get_page_text(link["url"])

        if not text or len(text) < 50:
            logger.info(f"  Skipping — insufficient content ({len(text or '')} chars)")
            return None

        # ── Relevance check (before LLM call — saves cost) ──
        text_lower = text.lower()
        matches = [s for s in RELEVANCE_SIGNALS if s in text_lower]
        if len(matches) < MIN_RELEVANCE_SIGNALS:
            logger.info(f"  Skipping — not an NPA notice (signals: {matches})")
            return "irrelevant"

        # ── LLM extraction (the ONLY LLM call per notice) ──
        notice = self.llm.extract_notice_data(
            text=text,
            source_url=link["url"],
            source_type=doc_type,
        )

        # Regex fallbacks for missing fields
        notice = self._apply_regex_fallbacks(notice, text)
        notice.nested_links = nested_links or []

        # ── Validation: must have a company/borrower ──
        if not notice.company_name and not notice.borrower_name:
            logger.info(f"  Skipping — no borrower identified")
            return "no_borrower"

        name = notice.company_name or notice.borrower_name
        logger.info(f"  ✓ Extracted: {name}")
        return notice

    def _apply_regex_fallbacks(self, notice: NoticeData, text: str) -> NoticeData:
        """Fill missing fields using regex patterns."""
        regex_dates = ExtractionUtils.extract_dates(text)
        if not notice.dates:
            for i, d in enumerate(regex_dates[:5]):
                label = "auction_date" if i == 0 else f"date_{i + 1}"
                notice.dates.append(DateInfo(label=label, value=d))

        if not notice.auction_date and regex_dates:
            notice.auction_date = regex_dates[0]

        has_reserve = any("reserve" in a.label.lower() for a in notice.amounts)
        regex_reserve = ExtractionUtils.extract_reserve_price(text)
        if not has_reserve and regex_reserve:
            notice.amounts.append(AmountInfo(label="reserve_price", value=regex_reserve))
        if not notice.reserve_price and regex_reserve:
            notice.reserve_price = regex_reserve

        has_dues = any(
            "due" in a.label.lower() or "outstanding" in a.label.lower()
            for a in notice.amounts
        )
        regex_dues = ExtractionUtils.extract_due_amount(text)
        if not has_dues and regex_dues:
            notice.amounts.append(AmountInfo(label="total_dues", value=regex_dues))
        if not notice.due_amount and regex_dues:
            notice.due_amount = regex_dues

        if not notice.notice_type:
            notice.notice_type = ExtractionUtils.determine_notice_type(text)

        return notice

    def _build_result(self, notices: list) -> ExtractionResult:
        return ExtractionResult(
            source_url=self.url,
            total_notices_found=len(notices),
            notices=notices,
        )

    def save_results(self, result: ExtractionResult) -> str:
        """Save to JSON file."""
        results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
        os.makedirs(results_dir, exist_ok=True)

        domain = urlparse(result.source_url).netloc.replace(".", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(results_dir, f"{domain}_{timestamp}.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                result.model_dump(exclude={"notices": {"__all__": {"raw_text_snippet"}}}),
                f, indent=2, ensure_ascii=False,
            )
        return filepath