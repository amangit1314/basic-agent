"""
Playwright-based browser automation for notice extraction.
Handles page navigation, link discovery, PDF downloads, and nested link following.
"""
import io
import re
from typing import List, Dict, Set, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from .config import logger

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


class NoticeBrowser:
    """Headless browser for navigating ARC websites and extracting notices."""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None

    async def start(self):
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
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
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("Browser stopped")

    async def get_page_html(self, url: str) -> str:
        """Navigate to URL and return rendered HTML."""
        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            return await page.content()
        except Exception as e:
            logger.error(f"Failed to load {url}: {e}")
            return ""
        finally:
            await page.close()

    async def get_page_text(self, url: str) -> Tuple[str, str]:
        """Get text from URL. Returns (text, type) where type is 'PDF' or 'HTML'."""
        if url.lower().endswith(".pdf"):
            text = await self._download_pdf_text(url)
            return text, "PDF"

        page = await self._context.new_page()
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            content_type = resp.headers.get("content-type", "") if resp else ""

            if "pdf" in content_type.lower():
                body = await resp.body()
                return self._extract_pdf_bytes(body), "PDF"

            await page.wait_for_timeout(1500)
            text = await page.inner_text("body")
            return text.strip(), "HTML"
        except Exception as e:
            logger.error(f"Failed to get text from {url}: {e}")
            return "", "HTML"
        finally:
            await page.close()

    async def _download_pdf_text(self, url: str) -> str:
        """Download PDF via HTTP and extract text."""
        import requests as req
        try:
            resp = req.get(
                url, timeout=60, verify=False,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                return self._extract_pdf_bytes(resp.content)
        except Exception as e:
            logger.error(f"PDF download failed for {url}: {e}")
        return ""

    def _extract_pdf_bytes(self, data: bytes) -> str:
        """Extract text from PDF bytes."""
        if not PYPDF_AVAILABLE:
            return "[PDF extraction unavailable - install pypdf]"
        try:
            reader = PdfReader(io.BytesIO(data))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e:
            logger.error(f"PDF parse error: {e}")
            return ""

    def discover_links(
        self, html: str, base_url: str, keywords: List[str]
    ) -> List[Dict]:
        """Find notice links on a page that match the given keywords.
        
        If keywords is empty, all valid links are included (no filtering).
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        all_links = soup.find_all("a", href=True)
        logger.info(f"Found {len(all_links)} total links on page")

        # Check if keyword filtering should be applied
        skip_keyword_filter = not keywords
        if skip_keyword_filter:
            logger.info("Keyword filtering disabled - including all valid links")

        results = []
        seen = set()
        kw_lower = [kw.lower() for kw in keywords] if keywords else []

        for a_tag in all_links:
            href = a_tag["href"]
            full_url = urljoin(base_url, href)

            if full_url in seen:
                continue
            if href.startswith(("#", "javascript:", "mailto:")):
                continue
            seen.add(full_url)

            link_text = a_tag.get_text(" ", strip=True)
            is_pdf = href.lower().endswith(".pdf")

            # Build context from link text + URL + parent element
            parent = a_tag.find_parent(["td", "li", "div", "tr", "p"])
            parent_text = parent.get_text(" ", strip=True) if parent else ""
            search_text = f"{link_text} {href} {parent_text}".lower()

            # Match keywords (or skip matching if no keywords provided)
            matched = []
            if not skip_keyword_filter:
                for kw, kwl in zip(keywords, kw_lower):
                    if kwl in search_text:
                        matched.append(kw)
                    else:
                        for sep in ["-", "_", "+", ""]:
                            if kwl.replace(" ", sep) in search_text:
                                matched.append(kw)
                                break

            # Include if: (1) no keyword filter OR (2) matched keywords OR (3) is PDF
            if skip_keyword_filter or matched or is_pdf:
                results.append({
                    "title": (link_text[:200] if link_text else "Notice").strip(),
                    "url": full_url,
                    "is_pdf": is_pdf,
                    "matched_keywords": matched,
                    "type": "PDF" if is_pdf else "HTML",
                })

        results.sort(
            key=lambda x: (len(x["matched_keywords"]), x["is_pdf"]),
            reverse=True,
        )
        kw_count = sum(1 for r in results if r["matched_keywords"])
        logger.info(f"Found {len(results)} relevant links ({kw_count} keyword matches)")
        return results

    async def follow_nested(
        self, url: str, depth: int, max_depth: int, visited: Set[str]
    ) -> List[Dict]:
        """Follow links within a notice page up to max_depth levels."""
        if depth >= max_depth or url in visited:
            return []
        visited.add(url)

        nested = []
        try:
            html = await self.get_page_html(url)
            if not html:
                return []

            soup = BeautifulSoup(html, "lxml")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                full_url = urljoin(url, href)
                if full_url in visited:
                    continue

                is_pdf = href.lower().endswith(".pdf")
                hint = a_tag.get_text(" ", strip=True).lower()
                is_relevant = is_pdf or any(
                    t in hint
                    for t in ["notice", "auction", "sale", "download", "view", "document"]
                )
                if not is_relevant:
                    continue

                visited.add(full_url)
                text, doc_type = await self.get_page_text(full_url)
                if text and len(text) > 50:
                    nested.append({
                        "url": full_url,
                        "type": doc_type,
                        "text": text[:10000],
                    })
                    if doc_type == "HTML" and depth + 1 < max_depth:
                        deeper = await self.follow_nested(
                            full_url, depth + 1, max_depth, visited
                        )
                        nested.extend(deeper)
        except Exception as e:
            logger.error(f"Nested link follow failed for {url}: {e}")

        return nested
