"""
LLM Client — The Agent's Brain (Multi-Provider)
=================================================

- Supports Gemini / OpenAI / Claude
- Robust to Gemini quota/429 by retry + regex fallback extraction
- Prints last 6 chars of the API key used (helps verify you truly loaded the "fresh key")
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Literal, Optional

from .config import logger, MAX_TEXT_FOR_LLM
from .models import AmountInfo, DateInfo, NoticeData


# =============================================================================
# Prompt Templates (shared across all providers)
# =============================================================================

EXTRACTION_PROMPT = """Extract structured data from this ARC/NPA notice. Return ONLY valid JSON.

The notice may contain information about:
- Company/borrower being auctioned or whose assets are for sale
- Banks or financial institutions issuing the notice
- Various dates (auction date, possession date, publication date, deadline)
- Various amounts (reserve price, total dues, outstanding amount, EMD)
- Type of notice (SARFAESI, NPA Sale, DRT, Swiss Challenge, Auction)

Return this exact JSON structure:
{{
  "title": "Title or header of the notice or null",
  "company_name": "Name of the company/borrower or null",
  "borrower_name": "Name of borrower (may be same as company) or null",
  "bank": "Name of bank/institution or null",
  "notice_type": "SARFAESI / NPA Sale / DRT / Swiss Challenge / Auction / Other or null",
  "auction_date": "The specific auction/sale date (e.g. '27.02.2026') or null",
  "reserve_price": "The specific reserve price (e.g. 'Rs. 10.50 Cr') or null",
  "due_amount": "The specific total due amount (e.g. 'Rs. 123.45 Lakhs') or null",
  "dates": [
    {{"label": "what this date is (e.g. publication_date)", "value": "the date string"}},
    ...
  ],
  "amounts": [
    {{"label": "what this amount is (e.g. EMD)", "value": "amount with currency"}},
    ...
  ]
}}

IMPORTANT:
- Extract specific Title of the notice
- Extract specific Auction Date, Reserve Price, and Due Amount into their own fields
- Extract ALL other dates and amounts into the lists
- If a field is not found, use null (not "Not specified" or "N/A")
- Keep original formatting for dates and amounts

Notice text:
{text}
"""


# =============================================================================
# Regex fallback extraction (works even when LLM quota=0)
# =============================================================================

_DATE_PATTERNS = [
    # 27.02.2026 or 27-02-2026 or 27/02/2026
    re.compile(r"\b([0-3]?\d)[./-]([01]?\d)[./-]((?:19|20)\d{2})\b"),
    # 27 Feb 2026 / 27 February 2026
    re.compile(r"\b([0-3]?\d)\s+(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+((?:19|20)\d{2})\b", re.I),
]

_AMOUNT_RE = re.compile(
    r"(?i)\b(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(cr|crore|lakhs?|lakh|mn|million|bn|billion)?\b"
)

# common labels near amounts
_LABEL_HINTS = [
    ("reserve", re.compile(r"(?i)\breserve\s+price\b")),
    ("emd", re.compile(r"(?i)\bemd\b|\bearnest\s+money\b")),
    ("due", re.compile(r"(?i)\b(total\s+)?dues?\b|\boutstanding\b|\bpayable\b")),
]

# company-ish patterns
_COMPANY_RE = re.compile(
    r"(?i)\b(m/s\.?|m\.s\.?|ms\.?)\s*([A-Z][\w&.,()\- ]{3,80})"
)
_COMPANY_SUFFIX_RE = re.compile(
    r"(?i)\b([A-Z][\w&.,()\- ]{3,80})\s+(ltd\.?|limited|pvt\.?\s*ltd\.?|private\s+limited|llp|inc\.?)\b"
)

_NOTICE_TYPE_HINTS = [
    ("Swiss Challenge", re.compile(r"(?i)\bswiss\s+challenge\b")),
    ("Auction", re.compile(r"(?i)\be-?auction\b|\bauction\b")),
    ("NPA Sale", re.compile(r"(?i)\btransfer\s+of\s+stressed\b|\bstressed\s+loan\b|\bnpa\b")),
    ("SARFAESI", re.compile(r"(?i)\bsarfaesi\b")),
    ("DRT", re.compile(r"(?i)\bdrt\b|\bdebt\s+recovery\s+tribunal\b")),
]

_BANK_RE = re.compile(r"(?i)\bstate\s+bank\s+of\s+india\b|\bSBI\b|\b(bank|financial\s+institution)\b")


def _regex_extract(text: str) -> dict:
    """Return a dict matching the JSON schema (best-effort)."""
    if not text:
        return {
            "title": None,
            "company_name": None,
            "borrower_name": None,
            "bank": None,
            "notice_type": None,
            "auction_date": None,
            "reserve_price": None,
            "due_amount": None,
            "dates": [],
            "amounts": [],
        }

    t = " ".join(text.split())  # normalize whitespace

    # title: first line-ish (best effort)
    title = None
    # try to pick first 140 chars as title candidate
    if len(t) > 10:
        title = t[:140]

    # bank
    bank = None
    if _BANK_RE.search(text):
        # If SBI mentioned, set SBI
        if re.search(r"(?i)\bstate\s+bank\s+of\s+india\b|\bSBI\b", text):
            bank = "State Bank of India"
        else:
            bank = "Bank/Financial Institution"

    # notice type
    notice_type = None
    for label, rgx in _NOTICE_TYPE_HINTS:
        if rgx.search(text):
            notice_type = label
            break

    # company name
    company_name = None
    m = _COMPANY_RE.search(text)
    if m:
        company_name = m.group(2).strip(" ,.-")
    else:
        m2 = _COMPANY_SUFFIX_RE.search(text)
        if m2:
            company_name = (m2.group(1) + " " + m2.group(2)).strip(" ,.-")

    # dates
    dates = []
    found_dates = []
    for pat in _DATE_PATTERNS:
        for mm in pat.finditer(text):
            ds = mm.group(0)
            if ds not in found_dates:
                found_dates.append(ds)

    # try label auction date: look near "auction"
    auction_date = None
    auction_window = None
    m_auc = re.search(r"(?i)\b(e-?auction|auction)\b.{0,120}", text)
    if m_auc:
        auction_window = m_auc.group(0)
        for pat in _DATE_PATTERNS:
            mdate = pat.search(auction_window)
            if mdate:
                auction_date = mdate.group(0)
                break

    for d in found_dates:
        label = "date"
        if auction_date and d == auction_date:
            label = "auction_date"
        dates.append({"label": label, "value": d})

    # amounts
    amounts = []
    found_amounts = []
    for am in _AMOUNT_RE.finditer(text):
        raw = am.group(0).strip()
        if raw not in found_amounts:
            found_amounts.append(raw)

    reserve_price = None
    due_amount = None

    # label amounts by nearby context (best-effort)
    for raw in found_amounts:
        # find first occurrence and check 120 chars around it
        idx = text.lower().find(raw.lower())
        window = text[max(0, idx - 120): idx + 120] if idx >= 0 else text

        label = "amount"
        for lbl, rgx in _LABEL_HINTS:
            if rgx.search(window):
                label = lbl
                break

        amounts.append({"label": label, "value": raw})

        if label == "reserve" and reserve_price is None:
            reserve_price = raw
        if label == "due" and due_amount is None:
            due_amount = raw

    # borrower name: if not separate, reuse company
    borrower_name = company_name

    return {
        "title": title,
        "company_name": company_name,
        "borrower_name": borrower_name,
        "bank": bank,
        "notice_type": notice_type,
        "auction_date": auction_date,
        "reserve_price": reserve_price,
        "due_amount": due_amount,
        "dates": dates,
        "amounts": amounts,
    }


# =============================================================================
# Provider: Gemini (google-generativeai legacy)
# =============================================================================

def _init_gemini() -> object | None:
    """Initialize Google Gemini model."""
    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("google-generativeai not installed. Run: pip install google-generativeai")
        return None

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("No Gemini API key. Set GEMINI_API_KEY in .env")
        return None

    # Helpful debug: confirm which key is loaded (no secrets)
    logger.info(f"Gemini key loaded (ends with): {api_key[-6:]}")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash"))
        logger.info(f"LLM initialized: Gemini ({os.getenv('GEMINI_MODEL_NAME', 'gemini-2.0-flash')})")
        return model
    except Exception as e:
        logger.error(f"Gemini init failed: {e}")
        return None


def _call_gemini(model, prompt: str) -> str:
    """
    Call Gemini and return raw text response.
    Retries on 429 with backoff.
    """
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            resp = model.generate_content(prompt)
            return resp.text
        except Exception as e:
            last_err = e
            msg = str(e)

            # If API sends "Please retry in XXs", respect it
            if "429" in msg or "quota" in msg.lower():
                wait_s = 2 ** attempt
                m = re.search(r"retry in\s+([0-9]+(\.[0-9]+)?)s", msg, flags=re.I)
                if m:
                    try:
                        wait_s = max(wait_s, float(m.group(1)))
                    except Exception:
                        pass
                logger.warning(f"Gemini 429/quota hit. Retry in ~{wait_s:.1f}s (attempt {attempt+1}/3)")
                time.sleep(wait_s)
                continue

            # Not a quota error → do not retry aggressively
            break

    raise last_err or RuntimeError("Gemini call failed")


# =============================================================================
# Provider: OpenAI
# =============================================================================

def _init_openai() -> object | None:
    """Initialize OpenAI client."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai not installed. Run: pip install openai")
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("No OpenAI API key. Set OPENAI_API_KEY in .env")
        return None

    try:
        client = OpenAI(api_key=api_key)
        logger.info(f"LLM initialized: OpenAI ({os.getenv('OPENAI_MODEL_NAME','gpt-4o-mini')})")
        return client
    except Exception as e:
        logger.error(f"OpenAI init failed: {e}")
        return None


def _call_openai(client, prompt: str) -> str:
    """Call OpenAI and return raw text response."""
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return response.choices[0].message.content


# =============================================================================
# Provider: Claude (Anthropic)
# =============================================================================

def _init_claude() -> object | None:
    """Initialize Anthropic Claude client."""
    try:
        from anthropic import Anthropic
    except ImportError:
        logger.warning("anthropic not installed. Run: pip install anthropic")
        return None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No Anthropic API key. Set ANTHROPIC_API_KEY in .env")
        return None

    try:
        client = Anthropic(api_key=api_key)
        logger.info("LLM initialized: Claude (claude-sonnet-4-20250514)")
        return client
    except Exception as e:
        logger.error(f"Claude init failed: {e}")
        return None


def _call_claude(client, prompt: str) -> str:
    """Call Claude and return raw text response."""
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-20250514"),
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# =============================================================================
# Provider Registry
# =============================================================================

PROVIDERS = {
    "gemini": {"init": _init_gemini, "call": _call_gemini},
    "openai": {"init": _init_openai, "call": _call_openai},
    "claude": {"init": _init_claude, "call": _call_claude},
}


# =============================================================================
# Unified LLM Client
# =============================================================================

class LLMClient:
    """
    Multi-provider LLM client for extraction.

    Key behavior:
    - If provider fails (429/quota/etc), we return regex-extracted structure instead of "Unknown".
    """

    def __init__(self, provider: str = "gemini"):
        self._provider_name = provider
        self._model = None
        self._call_fn = None
        self._init_provider(provider)

    def _init_provider(self, provider: str):
        if provider not in PROVIDERS:
            logger.error(f"Unknown provider '{provider}'. Available: {', '.join(PROVIDERS.keys())}")
            return

        entry = PROVIDERS[provider]
        self._model = entry["init"]()
        if self._model:
            self._call_fn = entry["call"]

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def provider(self) -> str:
        return self._provider_name

    def _call_llm(self, prompt: str) -> str:
        return self._call_fn(self._model, prompt)

    def extract_notice_data(self, text: str, source_url: str, source_type: str) -> NoticeData:
        """
        Extract structured data from notice text.

        - Uses LLM when available
        - If LLM fails, uses regex fallback so your pipeline still produces useful output
        """
        # Always compute fallback first (cheap and makes output robust)
        fallback = _regex_extract(text)

        # If no model or no text -> return fallback-only
        if not self._model or not text:
            return self._notice_from_dict(
                fallback,
                source_url=source_url,
                source_type=source_type,
                raw_text_snippet=text[:500] if text else "",
            )

        prompt = EXTRACTION_PROMPT.format(text=text[:MAX_TEXT_FOR_LLM])

        try:
            raw_response = self._call_llm(prompt)
            raw = self._clean_json_response(raw_response)
            data = json.loads(raw)

            # Merge: prefer LLM values, fallback fills missing
            merged = {**fallback, **{k: v for k, v in data.items() if v not in (None, "", [], {})}}

            return self._notice_from_dict(
                merged,
                source_url=source_url,
                source_type=source_type,
                raw_text_snippet=text[:500],
            )

        except Exception as e:
            logger.warning(f"{self._provider_name} extraction failed ({e}) → using regex fallback")
            return self._notice_from_dict(
                fallback,
                source_url=source_url,
                source_type=source_type,
                raw_text_snippet=text[:500],
            )

    @staticmethod
    def _notice_from_dict(d: dict, source_url: str, source_type: str, raw_text_snippet: str) -> NoticeData:
        dates = []
        for item in d.get("dates", []) or []:
            if isinstance(item, dict) and item.get("label") and item.get("value"):
                dates.append(DateInfo(label=item["label"], value=item["value"]))

        amounts = []
        for item in d.get("amounts", []) or []:
            if isinstance(item, dict) and item.get("label") and item.get("value"):
                amounts.append(AmountInfo(label=item["label"], value=item["value"]))

        return NoticeData(
            title=d.get("title"),
            company_name=d.get("company_name"),
            borrower_name=d.get("borrower_name"),
            bank=d.get("bank"),
            notice_type=d.get("notice_type"),
            auction_date=d.get("auction_date"),
            reserve_price=d.get("reserve_price"),
            due_amount=d.get("due_amount"),
            dates=dates,
            amounts=amounts,
            source_url=source_url,
            source_type=source_type,
            raw_text_snippet=raw_text_snippet,
        )

    @staticmethod
    def _clean_json_response(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        return raw


# Backward-compatible alias
GeminiClient = LLMClient
