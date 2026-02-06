"""
Google Gemini AI integration for structured notice summarization.
"""
import os
import json
from typing import Dict
from .config import logger

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


SUMMARY_PROMPT = (
    "Extract the following information from this auction/sale notice. "
    "Return ONLY valid JSON (no markdown fences, no extra text) with these fields:\n"
    "{\n"
    '  "borrower": "Name of borrower or company (string or null)",\n'
    '  "amount": "Total amount due/outstanding with currency (string or null)",\n'
    '  "property": "Description of property/asset for sale (string or null)",\n'
    '  "auction_date": "Date of auction in DD.MM.YYYY format (string or null)",\n'
    '  "reserve_price": "Reserve price with currency (string or null)",\n'
    '  "bank": "Name of bank or financial institution (string or null)",\n'
    '  "notice_type": "Type: SARFAESI/NPA/DRT/Swiss Challenge/Auction (string or null)"\n'
    "}\n\n"
    "Notice text:\n"
)


class GeminiSummarizer:
    """Uses Google Gemini to extract structured notice summaries."""

    def __init__(self):
        self._model = None
        self._init()

    def _init(self):
        if not GEMINI_AVAILABLE:
            logger.warning("google-generativeai not installed. AI summaries disabled.")
            return

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning(
                "No Gemini API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY env var."
            )
            return

        try:
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel("gemini-2.0-flash")
            logger.info("Gemini AI initialized (gemini-2.0-flash)")
        except Exception as e:
            logger.error(f"Gemini init failed: {e}")

    @property
    def available(self) -> bool:
        return self._model is not None

    def summarize(self, text: str) -> Dict:
        """Extract structured fields from notice text. Returns dict or empty dict."""
        if not self._model or not text:
            return {}

        prompt = SUMMARY_PROMPT + text[:8000]

        try:
            response = self._model.generate_content(prompt)
            raw = response.text.strip()

            # Strip markdown code fences if Gemini wraps the output
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:])
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"Gemini returned invalid JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"Gemini summarization error: {e}")
            return {}
