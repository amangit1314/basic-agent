# """
# Browser Tool — The Agent's Hands
# ==================================

# LEARNING NOTE: What is a "Tool" in agent architecture?
# -------------------------------------------------------
# A tool is a function the agent can call to interact with the world.
# The agent (brain/LLM) decides WHICH tool to use and WHAT arguments to pass.
# The tool does the actual work — in this case, opening web pages and reading content.

# This browser tool provides three capabilities:
# 1. navigate(url)     → Get the rendered HTML of a page
# 2. get_text(url)     → Get the text content (handles HTML pages AND PDFs)
# 3. find_links(html)  → Find notice links matching keywords on a page

# TECH NOTE: Why Playwright instead of requests?
# -----------------------------------------------
# Many ARC websites use JavaScript to load content dynamically.
# `requests.get()` only gets the initial HTML — before JS runs.
# Playwright launches a real Chromium browser that executes JS,
# so we get the fully rendered page just like a human would see it.
# """

# import io
# from typing import List, Dict, Tuple
# from urllib.parse import urljoin

# from bs4 import BeautifulSoup
# from playwright.async_api import async_playwright

# from .config import logger

# # pypdf is optional — gracefully degrade if not installed
# try:
#     from pypdf import PdfReader
#     PYPDF_AVAILABLE = True
# except ImportError:
#     PYPDF_AVAILABLE = False


# class NoticeBrowser:
#     """
#     Headless browser for navigating ARC websites and extracting content.

#     LEARNING NOTE: This class uses the async context manager pattern.
#     You MUST call start() before using it and stop() when done.
#     The agent handles this lifecycle automatically.

#     Usage:
#         browser = NoticeBrowser()
#         await browser.start()
#         html = await browser.get_page_html("https://example.com")
#         await browser.stop()
#     """

#     def __init__(self):
#         self._pw = None
#         self._browser = None
#         self._context = None

#     async def start(self):
#         """Launch headless Chromium browser."""
#         self._pw = await async_playwright().start()
#         self._browser = await self._pw.chromium.launch(
#             headless=True,
#             args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
#         )
#         # Browser context = isolated session (cookies, storage, etc.)
#         self._context = await self._browser.new_context(
#             user_agent=(
#                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                 "AppleWebKit/537.36 (KHTML, like Gecko) "
#                 "Chrome/120.0.0.0 Safari/537.36"
#             ),
#             ignore_https_errors=True,
#         )
#         logger.info("Browser started")

#     async def stop(self):
#         """Shut down browser and release resources."""
#         if self._context:
#             await self._context.close()
#         if self._browser:
#             await self._browser.close()
#         if self._pw:
#             await self._pw.stop()
#         logger.info("Browser stopped")

#     # -------------------------------------------------------------------------
#     # Tool 1: Navigate — Get rendered HTML from a URL
#     # -------------------------------------------------------------------------

#     async def get_page_html(self, url: str) -> str:
#         """
#         Navigate to a URL and return the fully rendered HTML.

#         LEARNING NOTE: Each call opens a NEW tab (page), loads the URL,
#         waits for content, grabs the HTML, and closes the tab.
#         This prevents state leaking between page visits.
#         """
#         page = await self._context.new_page()
#         try:
#             await page.goto(url, wait_until="domcontentloaded", timeout=30000)
#             # Wait a bit for JS to finish rendering dynamic content
#             await page.wait_for_timeout(2000)
#             return await page.content()
#         except Exception as e:
#             logger.error(f"Failed to load {url}: {e}")
#             return ""
#         finally:
#             await page.close()

#     # -------------------------------------------------------------------------
#     # Tool 2: Get Text — Read content from a URL (handles HTML + PDF)
#     # -------------------------------------------------------------------------

#     async def get_page_text(self, url: str) -> Tuple[str, str, List[str]]:
#         """
#         Get text content from a URL. Automatically detects PDF vs HTML.

#         Returns:
#             (text_content, content_type, nested_links) 
#             where content_type is "PDF" or "HTML" and nested_links is a list of URLs found on the page.

#         LEARNING NOTE: This is where the agent handles different document types.
#         A notice link might point to:
#         1. An HTML page → we extract the visible text AND any relevant nested links
#         2. A PDF file (url ends in .pdf) → we download and parse it
#         3. A redirect to a PDF (content-type header says PDF) → same as #2
#         The agent doesn't need to know which — this tool handles it transparently.
#         """
#         # Fast path REMOVED: URL ending in .pdf will now go through Playwright
#         # to ensure cookies and session context are preserved.
        
#         page = await self._context.new_page()
#         try:
#             resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
#             content_type = resp.headers.get("content-type", "") if resp else ""

#             # Server returned a PDF (even though URL doesn't end in .pdf)
#             if "pdf" in content_type.lower():
#                 body = await resp.body()
#                 return self._extract_pdf_bytes(body), "PDF", []

#             # It's HTML — wait for rendering, then get visible text and links
#             await page.wait_for_timeout(1500)
            
#             # Extract text
#             text = await page.inner_text("body")
            
#             # Extract nested links (simple extraction of all hrefs)
#             # We use BeautifulSoup on the full content to get reliable links
#             html = await page.content()
#             soup = BeautifulSoup(html, "lxml")
#             links = []
#             for a in soup.find_all("a", href=True):
#                 href = a["href"]
#                 full_url = urljoin(url, href)
#                 # Filter out obvious non-content links
#                 if not href.startswith(("#", "javascript:", "mailto:")):
#                      links.append(full_url)
            
#             # De-duplicate
#             links = list(set(links))
            
#             return text.strip(), "HTML", links
            
#         except Exception as e:
#             logger.error(f"Failed to get text from {url}: {e}")
#             return "", "HTML", []
#         finally:
#             await page.close()



#     def _extract_pdf_bytes(self, data: bytes) -> str:
#         """
#         Extract text from raw PDF bytes.

#         LEARNING NOTE: pypdf reads PDFs page by page. We concatenate all pages
#         into a single string. This works for most ARC notice PDFs which are
#         text-based. For scanned/image PDFs, you'd need OCR (tesseract) —
#         that's a future enhancement.
#         """
#         if not PYPDF_AVAILABLE:
#             return "[PDF extraction unavailable - install pypdf]"
#         try:
#             reader = PdfReader(io.BytesIO(data))
#             return "\n".join(p.extract_text() or "" for p in reader.pages)
#         except Exception as e:
#             logger.error(f"PDF parse error: {e}")
#             return ""

#     # -------------------------------------------------------------------------
#     # Tool 3: Find Links — Discover notice links matching keywords
#     # -------------------------------------------------------------------------

#     def discover_links(
#         self, html: str, base_url: str, keywords: List[str]
#     ) -> List[Dict]:
#         """
#         Scan a page's HTML for links that match the given keywords.

#         LEARNING NOTE: This is the "perception" part of the agent for listing pages.
#         It looks at every <a> tag and checks if the link text, URL, or surrounding
#         context contains any of our keywords. Links are scored and sorted by relevance.

#         Args:
#             html: Raw HTML of the page
#             base_url: Base URL for resolving relative links (e.g. "./notice.pdf" → full URL)
#             keywords: List of keywords to match against

#         Returns:
#             List of dicts with keys: title, url, is_pdf, matched_keywords, type
#         """
#         if not html:
#             return []

#         soup = BeautifulSoup(html, "lxml")
#         all_links = soup.find_all("a", href=True)
#         logger.info(f"Found {len(all_links)} total links on page")

#         # If no keywords provided, include all valid links (no filtering)
#         skip_keyword_filter = not keywords
#         if skip_keyword_filter:
#             logger.info("No keywords provided — including all valid links")

#         results = []
#         seen: set = set()
#         kw_lower = [kw.lower() for kw in keywords] if keywords else []

#         for a_tag in all_links:
#             href = a_tag["href"]
#             full_url = urljoin(base_url, href)

#             # Skip duplicates and non-navigable links
#             if full_url in seen:
#                 continue
#             if href.startswith(("#", "javascript:", "mailto:")):
#                 continue
#             seen.add(full_url)

#             link_text = a_tag.get_text(" ", strip=True)
#             is_pdf = href.lower().endswith(".pdf")

#             # Build search context: link text + URL + parent element text
#             parent = a_tag.find_parent(["td", "li", "div", "tr", "p"])
#             parent_text = parent.get_text(" ", strip=True) if parent else ""
#             search_text = f"{link_text} {href} {parent_text}".lower()

#             # Match keywords (with variant checking for hyphens, underscores, etc.)
#             matched = []
#             if not skip_keyword_filter:
#                 for kw, kwl in zip(keywords, kw_lower):
#                     if kwl in search_text:
#                         matched.append(kw)
#                     else:
#                         for sep in ["-", "_", "+", ""]:
#                             if kwl.replace(" ", sep) in search_text:
#                                 matched.append(kw)
#                                 break

#             # Include if: no filter, OR matched keywords, OR is a PDF
#             if skip_keyword_filter or matched or is_pdf:
#                 results.append({
#                     "title": (link_text[:200] if link_text else "Notice").strip(),
#                     "url": full_url,
#                     "is_pdf": is_pdf,
#                     "matched_keywords": matched,
#                     "type": "PDF" if is_pdf else "HTML",
#                 })

#         # Sort: most keyword matches first, PDFs prioritized
#         results.sort(
#             key=lambda x: (len(x["matched_keywords"]), x["is_pdf"]),
#             reverse=True,
#         )
#         kw_count = sum(1 for r in results if r["matched_keywords"])
#         logger.info(f"Found {len(results)} relevant links ({kw_count} keyword matches)")
#         return results


"""
Browser Tool — The Agent's Hands
==================================

LEARNING NOTE: What is a "Tool" in agent architecture?
-------------------------------------------------------
A tool is a function the agent can call to interact with the world.
The agent (brain/LLM) decides WHICH tool to use and WHAT arguments to pass.
The tool does the actual work — in this case, opening web pages and reading content.

This browser tool provides three capabilities:
1. get_page_html(url)     → Get the rendered HTML of a page
2. get_page_text(url)     → Get the text content (handles HTML pages AND PDFs)
3. discover_links(html)   → Find notice links matching keywords on a page

TECH NOTE: Why Playwright instead of requests?
-----------------------------------------------
Many ARC websites use JavaScript to load content dynamically.
`requests.get()` only gets the initial HTML — before JS runs.
Playwright launches a real Chromium browser that executes JS,
so we get the fully rendered page just like a human would see it.
"""

import io
import re
from typing import List, Dict, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .config import logger

# pypdf is optional — gracefully degrade if not installed
try:
    from pypdf import PdfReader

    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


class NoticeBrowser:
    """
    Headless browser for navigating ARC websites and extracting content.

    Usage:
        browser = NoticeBrowser()
        await browser.start()
        html = await browser.get_page_html("https://example.com")
        text, kind, links = await browser.get_page_text("https://example.com/notice")
        await browser.stop()
    """

    PDF_URL_RE = re.compile(r"\.pdf(\b|/|\?|#)", re.IGNORECASE)

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None

    async def start(self):
        """Launch headless Chromium browser."""
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        # Browser context = isolated session (cookies, storage, etc.)
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,
        )
        logger.info("Browser started")

    async def stop(self):
        """Shut down browser and release resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("Browser stopped")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _looks_like_pdf(self, url: str) -> bool:
        """
        True if URL likely points to a PDF.

        Handles SBI-style links like:
          ...something.pdf/<uuid>?t=...
        """
        return bool(self.PDF_URL_RE.search(url))

    async def _fetch_bytes_via_context(self, url: str) -> bytes:
        """
        Fetch bytes using Playwright context request (shares cookies/session).
        This avoids Page.goto() download errors for PDFs.
        """
        resp = await self._context.request.get(
            url,
            timeout=30000,
            headers={
                "Accept": "*/*",
                "Referer": "https://bank.sbi/",
            },
        )
        if not resp.ok:
            raise RuntimeError(f"Request failed {resp.status} for {url}")
        return await resp.body()

    def _canonicalize_url(self, url: str) -> str:
        """
        Canonicalize for de-duplication:
        - drop querystring (SBI uses ?t=... cache busters)
        - keep path (including ...pdf/<uuid>)
        """
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    # -------------------------------------------------------------------------
    # Tool 1: Navigate — Get rendered HTML from a URL
    # -------------------------------------------------------------------------

    async def get_page_html(self, url: str) -> str:
        """Navigate to a URL and return the fully rendered HTML."""
        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait a bit for JS to finish rendering dynamic content
            await page.wait_for_timeout(2000)
            return await page.content()
        except Exception as e:
            logger.error(f"Failed to load {url}: {e}")
            return ""
        finally:
            await page.close()

    # -------------------------------------------------------------------------
    # Tool 2: Get Text — Read content from a URL (handles HTML + PDF)
    # -------------------------------------------------------------------------

    async def get_page_text(self, url: str) -> Tuple[str, str, List[str]]:
        """
        Get text content from a URL. Automatically detects PDF vs HTML.

        Returns:
            (text_content, content_type, nested_links)
            where content_type is "PDF" or "HTML"
        """
        page = await self._context.new_page()
        try:
            # ✅ If it looks like a PDF, don't page.goto() (SBI triggers download)
            if self._looks_like_pdf(url):
                body = await self._fetch_bytes_via_context(url)
                return self._extract_pdf_bytes(body).strip(), "PDF", []

            resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            content_type = resp.headers.get("content-type", "") if resp else ""
            if resp and "pdf" in content_type.lower():
                # server returned PDF even if URL doesn't clearly show it
                body = await resp.body()
                return self._extract_pdf_bytes(body).strip(), "PDF", []

            # It's HTML — wait for rendering, then get visible text and links
            await page.wait_for_timeout(1500)

            text = await page.inner_text("body")

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith(("#", "javascript:", "mailto:")):
                    continue
                links.append(urljoin(url, href))

            links = list(set(links))
            return text.strip(), "HTML", links

        except Exception as e:
            msg = str(e)

            # ✅ Fallback: if Playwright says "download is starting", fetch bytes directly
            if "Download is starting" in msg or "download" in msg.lower():
                try:
                    body = await self._fetch_bytes_via_context(url)
                    text = self._extract_pdf_bytes(body).strip()
                    if text:
                        return text, "PDF", []
                except Exception as e2:
                    logger.error(f"Download fallback failed for {url}: {e2}")

            logger.error(f"Failed to get text from {url}: {e}")
            return "", "HTML", []
        finally:
            await page.close()

    def _extract_pdf_bytes(self, data: bytes) -> str:
        """
        Extract text from raw PDF bytes.
        """
        if not PYPDF_AVAILABLE:
            return "[PDF extraction unavailable - install pypdf]"
        try:
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:
            logger.error(f"PDF parse error: {e}")
            return ""

    # -------------------------------------------------------------------------
    # Tool 3: Discover Links — Discover notice links matching keywords
    # -------------------------------------------------------------------------

    def discover_links(self, html: str, base_url: str, keywords: List[str]) -> List[Dict]:
        """
        Scan a page's HTML for links that match the given keywords.

        Returns:
            List of dicts with keys: title, url, is_pdf, matched_keywords, type
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        all_links = soup.find_all("a", href=True)
        logger.info(f"Found {len(all_links)} total links on page")

        # If no keywords provided, include all valid links (no filtering)
        skip_keyword_filter = not keywords
        if skip_keyword_filter:
            logger.info("No keywords provided — including all valid links")

        results: List[Dict] = []
        seen: set = set()
        kw_lower = [kw.lower() for kw in keywords] if keywords else []

        for a_tag in all_links:
            href = a_tag["href"]

            # Skip non-navigable
            if href.startswith(("#", "javascript:", "mailto:")):
                continue

            full_url = urljoin(base_url, href)
            canonical = self._canonicalize_url(full_url)

            # De-dupe (drop query params like ?t=...)
            if canonical in seen:
                continue
            seen.add(canonical)

            link_text = a_tag.get_text(" ", strip=True)
            href_l = href.lower()

            # ✅ SBI-safe PDF detection
            is_pdf = (".pdf" in href_l) or self._looks_like_pdf(full_url)

            # Build search context: link text + URL + parent element text
            parent = a_tag.find_parent(["td", "li", "div", "tr", "p"])
            parent_text = parent.get_text(" ", strip=True) if parent else ""
            search_text = f"{link_text} {href} {parent_text}".lower()

            # Match keywords (with variant checking for hyphens, underscores, etc.)
            matched: List[str] = []
            if not skip_keyword_filter:
                for kw, kwl in zip(keywords, kw_lower):
                    if kwl in search_text:
                        matched.append(kw)
                    else:
                        for sep in ["-", "_", "+", ""]:
                            if kwl.replace(" ", sep) in search_text:
                                matched.append(kw)
                                break

            # Include if: no filter, OR matched keywords, OR is a PDF
            if skip_keyword_filter or matched or is_pdf:
                results.append(
                    {
                        "title": (link_text[:200] if link_text else "Notice").strip(),
                        "url": full_url,
                        "is_pdf": is_pdf,
                        "matched_keywords": matched,
                        "type": "PDF" if is_pdf else "HTML",
                    }
                )

        # Sort: most keyword matches first, PDFs prioritized
        results.sort(key=lambda x: (len(x["matched_keywords"]), x["is_pdf"]), reverse=True)

        kw_count = sum(1 for r in results if r["matched_keywords"])
        logger.info(f"Found {len(results)} relevant links ({kw_count} keyword matches)")
        return results