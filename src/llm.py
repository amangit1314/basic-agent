
# """
# LLM Client — Extraction Only (Multi-Provider)
# ===============================================

# - Supports Gemini / OpenAI / Claude
# - Robust to Gemini quota/429 by retry + regex fallback extraction
# - Smart text truncation: sends head + tail, not just head
# - Source URL passed as hint for company name extraction
# """

# from __future__ import annotations

# import json
# import os
# import re
# import time
# from typing import Optional

# from .config import logger, MAX_TEXT_FOR_LLM
# from .models import AmountInfo, DateInfo, NoticeData


# # =============================================================================
# # Extraction Prompt
# # =============================================================================

# EXTRACTION_PROMPT = """Extract structured data from this ARC/NPA notice. Return ONLY valid JSON.

# CRITICAL INSTRUCTIONS:
# - The COMPANY NAME is usually in a table or list — look for "Borrower", "Account Name", "Name of Borrower/Company"
# - Extract the FULL company name, not abbreviated (e.g. "Vivimed Labs Ltd" not just "Labs Ltd", "Prince Rice Mill Pvt Ltd" not just "Mills Pvt Ltd")
# - The title should be the SPECIFIC notice title, NOT the generic header like "Web Notice Transfer of..." or page boilerplate
# - For SBI/bank notices, the actual borrower data is often in a TABLE near the end of the document — look there first
# - Skip boilerplate text like "In terms of the Bank's Policy...", "1 | P a g e", page headers/footers
# - The source URL below may contain the company name as a hint — use it to verify your extraction

# Source URL (may contain company name): {source_url}

# Return this exact JSON structure:
# {{
#   "title": "Specific title of THIS notice (not generic header or boilerplate)",
#   "company_name": "FULL name of the company/borrower (check tables and URL for hints)",
#   "borrower_name": "Name of borrower if different from company, or null",
#   "bank": "Name of bank/institution",
#   "notice_type": "SARFAESI / Swiss Challenge / NPA Sale / DRT Sale / Auction / Other",
#   "auction_date": "The auction/sale date (e.g. '27.02.2026') or null",
#   "reserve_price": "Reserve price WITH UNIT (e.g. 'Rs. 10.50 Cr') or null",
#   "due_amount": "Total due amount WITH UNIT (e.g. 'Rs. 924.96 Cr') or null",
#   "dates": [
#     {{"label": "descriptive_label (e.g. publication_date, bid_deadline, submission_date)", "value": "date string"}}
#   ],
#   "amounts": [
#     {{"label": "descriptive_label (e.g. emd, reserve_price, outstanding_principal)", "value": "amount with currency and unit"}}
#   ]
# }}

# IMPORTANT:
# - due_amount and reserve_price MUST include unit (Cr/Lakhs/Lakh). "924.96" alone is WRONG — specify "Rs. 924.96 Cr"
# - reserve_price of "Rs. 100" in Swiss Challenge means Rs. 100 per unit of debt — note this as "Rs. 100 (per unit)"
# - If a field is not found, use null (not "Not specified" or "N/A")
# - Keep original formatting for dates
# - The notice may be in Hindi, Kannada, Tamil, or other Indian languages — extract ALL fields regardless of language

# Notice text:
# {text}"""


# # =============================================================================
# # Regex fallback extraction (works even when LLM quota=0)
# # =============================================================================

# _DATE_PATTERNS = [
#     re.compile(r"\b([0-3]?\d)[./-]([01]?\d)[./-]((?:19|20)\d{2})\b"),
#     re.compile(
#         r"\b([0-3]?\d)\s+(jan|january|feb|february|mar|march|apr|april|may|jun|june"
#         r"|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
#         r"\s+((?:19|20)\d{2})\b",
#         re.I,
#     ),
# ]

# _AMOUNT_RE = re.compile(
#     r"(?i)\b(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(cr|crore|lakhs?|lakh|mn|million|bn|billion)?\b"
# )

# _LABEL_HINTS = [
#     ("reserve", re.compile(r"(?i)\breserve\s+price\b")),
#     ("emd", re.compile(r"(?i)\bemd\b|\bearnest\s+money\b")),
#     ("due", re.compile(r"(?i)\b(total\s+)?dues?\b|\boutstanding\b|\bpayable\b")),
# ]

# _COMPANY_RE = re.compile(
#     r"(?i)\b(m/s\.?|m\.s\.?|ms\.?)\s*([A-Z][\w&.,()\- ]{3,80})"
# )
# _COMPANY_SUFFIX_RE = re.compile(
#     r"(?i)\b([A-Z][\w&.,()\- ]{3,80})\s+(ltd\.?|limited|pvt\.?\s*ltd\.?|private\s+limited|llp|inc\.?)\b"
# )

# _NOTICE_TYPE_HINTS = [
#     ("Swiss Challenge", re.compile(r"(?i)\bswiss\s+challenge\b")),
#     ("Auction", re.compile(r"(?i)\be-?auction\b|\bauction\b")),
#     ("NPA Sale", re.compile(r"(?i)\btransfer\s+of\s+stressed\b|\bstressed\s+loan\b|\bnpa\b")),
#     ("SARFAESI", re.compile(r"(?i)\bsarfaesi\b")),
#     ("DRT", re.compile(r"(?i)\bdrt\b|\bdebt\s+recovery\s+tribunal\b")),
# ]

# _BANK_RE = re.compile(r"(?i)\bstate\s+bank\s+of\s+india\b|\bSBI\b|\b(bank|financial\s+institution)\b")


# def _regex_extract(text: str) -> dict:
#     """Return a dict matching the JSON schema (best-effort)."""
#     if not text:
#         return {
#             "title": None, "company_name": None, "borrower_name": None,
#             "bank": None, "notice_type": None, "auction_date": None,
#             "reserve_price": None, "due_amount": None, "dates": [], "amounts": [],
#         }

#     t = " ".join(text.split())

#     # title
#     title = t[:140] if len(t) > 10 else None

#     # bank
#     bank = None
#     if re.search(r"(?i)\bstate\s+bank\s+of\s+india\b|\bSBI\b", text):
#         bank = "State Bank of India"
#     elif _BANK_RE.search(text):
#         bank = "Bank/Financial Institution"

#     # notice type
#     notice_type = None
#     for label, rgx in _NOTICE_TYPE_HINTS:
#         if rgx.search(text):
#             notice_type = label
#             break

#     # company name
#     company_name = None
#     m = _COMPANY_RE.search(text)
#     if m:
#         company_name = m.group(2).strip(" ,.-")
#     else:
#         m2 = _COMPANY_SUFFIX_RE.search(text)
#         if m2:
#             company_name = (m2.group(1) + " " + m2.group(2)).strip(" ,.-")

#     # dates
#     found_dates = []
#     for pat in _DATE_PATTERNS:
#         for mm in pat.finditer(text):
#             ds = mm.group(0)
#             if ds not in found_dates:
#                 found_dates.append(ds)

#     auction_date = None
#     m_auc = re.search(r"(?i)\b(e-?auction|auction)\b.{0,120}", text)
#     if m_auc:
#         for pat in _DATE_PATTERNS:
#             mdate = pat.search(m_auc.group(0))
#             if mdate:
#                 auction_date = mdate.group(0)
#                 break

#     dates = []
#     for d in found_dates:
#         label = "auction_date" if auction_date and d == auction_date else "date"
#         dates.append({"label": label, "value": d})

#     # amounts
#     found_amounts = []
#     for am in _AMOUNT_RE.finditer(text):
#         raw = am.group(0).strip()
#         if raw not in found_amounts:
#             found_amounts.append(raw)

#     reserve_price = None
#     due_amount = None
#     amounts = []

#     for raw in found_amounts:
#         idx = text.lower().find(raw.lower())
#         window = text[max(0, idx - 120): idx + 120] if idx >= 0 else text

#         label = "amount"
#         for lbl, rgx in _LABEL_HINTS:
#             if rgx.search(window):
#                 label = lbl
#                 break

#         amounts.append({"label": label, "value": raw})

#         if label == "reserve" and reserve_price is None:
#             reserve_price = raw
#         if label == "due" and due_amount is None:
#             due_amount = raw

#     return {
#         "title": title,
#         "company_name": company_name,
#         "borrower_name": company_name,
#         "bank": bank,
#         "notice_type": notice_type,
#         "auction_date": auction_date,
#         "reserve_price": reserve_price,
#         "due_amount": due_amount,
#         "dates": dates,
#         "amounts": amounts,
#     }


# # =============================================================================
# # Smart Text Truncation
# # =============================================================================

# def _prepare_text_for_extraction(text: str, max_chars: int = MAX_TEXT_FOR_LLM) -> str:
#     """
#     Send the LLM the USEFUL parts of the document, not just the beginning.

#     Bank PDFs (especially SBI) have 2-3 pages of boilerplate before the
#     actual borrower table. If we send only text[:8000], the LLM sees
#     boilerplate and misses company names, amounts, etc.

#     Strategy: head (context/header) + tail (tables/data)
#     """
#     if len(text) <= max_chars:
#         return text

#     # Head: first 2000 chars — gives context (bank name, notice type)
#     # Tail: last 6000 chars — where tables and actual data usually are
#     head_size = 2000
#     tail_size = max_chars - head_size

#     head = text[:head_size]
#     tail = text[-tail_size:]

#     return f"{head}\n\n[...boilerplate omitted — data section below...]\n\n{tail}"


# # =============================================================================
# # Company Name from URL (hint extraction)
# # =============================================================================

# def _extract_company_hint_from_url(url: str) -> Optional[str]:
#     """
#     Many PDF URLs contain the company name. Extract it as a hint.

#     Examples:
#       .../Transfer+of+Stressed+Loan+Exposure+-+Vivimed+Labs+Ltd.pdf → "Vivimed Labs Ltd"
#       .../Web+Notice+for+sale+-+Prince+Rice+Mill+Pvt+Ltd.pdf → "Prince Rice Mill Pvt Ltd"
#     """
#     if not url:
#         return None

#     # Get the filename part
#     from urllib.parse import urlparse, unquote
#     path = unquote(urlparse(url).path)
#     filename = path.split("/")[-1].replace("+", " ").replace("%20", " ")

#     # Remove file extension
#     filename = re.sub(r"\.(pdf|html?)$", "", filename, flags=re.I)

#     # Try to find company-like name after common separators
#     # Pattern: "...Transfer of Stressed Loan Exposure - COMPANY NAME (1)"
#     m = re.search(r"[-–—]\s*(.+?)(?:\s*\(\d+\))?\s*$", filename)
#     if m:
#         candidate = m.group(1).strip()
#         # Clean up common noise
#         candidate = re.sub(r"^\d+_?", "", candidate).strip()
#         if len(candidate) > 3:
#             return candidate

#     return None


# # =============================================================================
# # Providers: Gemini / OpenAI / Claude
# # =============================================================================

# def _init_gemini() -> object | None:
#     try:
#         import google.generativeai as genai
#     except ImportError:
#         logger.warning("google-generativeai not installed. Run: pip install google-generativeai")
#         return None

#     api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
#     if not api_key:
#         logger.warning("No Gemini API key. Set GEMINI_API_KEY in .env")
#         return None

#     logger.info(f"Gemini key loaded (ends with): {api_key[-6:]}")
#     try:
#         genai.configure(api_key=api_key)
#         model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")
#         model = genai.GenerativeModel(model_name)
#         logger.info(f"LLM initialized: Gemini ({model_name})")
#         return model
#     except Exception as e:
#         logger.error(f"Gemini init failed: {e}")
#         return None


# def _call_gemini(model, prompt: str) -> str:
#     last_err: Optional[Exception] = None
#     for attempt in range(3):
#         try:
#             resp = model.generate_content(prompt)
#             return resp.text
#         except Exception as e:
#             last_err = e
#             msg = str(e)
#             if "429" in msg or "quota" in msg.lower():
#                 wait_s = 2 ** attempt
#                 m = re.search(r"retry in\s+([0-9]+(\.[0-9]+)?)s", msg, flags=re.I)
#                 if m:
#                     try:
#                         wait_s = max(wait_s, float(m.group(1)))
#                     except Exception:
#                         pass
#                 logger.warning(f"Gemini 429/quota hit. Retry in ~{wait_s:.1f}s (attempt {attempt+1}/3)")
#                 time.sleep(wait_s)
#                 continue
#             break
#     raise last_err or RuntimeError("Gemini call failed")


# def _init_openai() -> object | None:
#     try:
#         from openai import OpenAI
#     except ImportError:
#         logger.warning("openai not installed. Run: pip install openai")
#         return None

#     api_key = os.getenv("OPENAI_API_KEY")
#     if not api_key:
#         logger.warning("No OpenAI API key. Set OPENAI_API_KEY in .env")
#         return None

#     try:
#         client = OpenAI(api_key=api_key)
#         logger.info(f"LLM initialized: OpenAI ({os.getenv('OPENAI_MODEL_NAME', 'gpt-4o-mini')})")
#         return client
#     except Exception as e:
#         logger.error(f"OpenAI init failed: {e}")
#         return None


# def _call_openai(client, prompt: str) -> str:
#     response = client.chat.completions.create(
#         model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.1,
#     )
#     return response.choices[0].message.content


# def _init_claude() -> object | None:
#     try:
#         from anthropic import Anthropic
#     except ImportError:
#         logger.warning("anthropic not installed. Run: pip install anthropic")
#         return None

#     api_key = os.getenv("ANTHROPIC_API_KEY")
#     if not api_key:
#         logger.warning("No Anthropic API key. Set ANTHROPIC_API_KEY in .env")
#         return None

#     try:
#         client = Anthropic(api_key=api_key)
#         logger.info("LLM initialized: Claude (claude-sonnet-4-20250514)")
#         return client
#     except Exception as e:
#         logger.error(f"Claude init failed: {e}")
#         return None


# def _call_claude(client, prompt: str) -> str:
#     response = client.messages.create(
#         model=os.getenv("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-20250514"),
#         max_tokens=2048,
#         messages=[{"role": "user", "content": prompt}],
#     )
#     return response.content[0].text


# PROVIDERS = {
#     "gemini": {"init": _init_gemini, "call": _call_gemini},
#     "openai": {"init": _init_openai, "call": _call_openai},
#     "claude": {"init": _init_claude, "call": _call_claude},
# }


# # =============================================================================
# # Unified LLM Client
# # =============================================================================

# class LLMClient:
#     """
#     Multi-provider LLM client for extraction only.

#     Key changes from previous version:
#     - No more decide_next_action() — pipeline handles flow
#     - Smart text truncation (head + tail)
#     - Source URL passed as company name hint
#     - Regex fallback always computed first for robustness
#     """

#     def __init__(self, provider: str = "gemini"):
#         self._provider_name = provider
#         self._model = None
#         self._call_fn = None
#         self._init_provider(provider)

#     def _init_provider(self, provider: str):
#         if provider not in PROVIDERS:
#             logger.error(f"Unknown provider '{provider}'. Available: {', '.join(PROVIDERS.keys())}")
#             return
#         entry = PROVIDERS[provider]
#         self._model = entry["init"]()
#         if self._model:
#             self._call_fn = entry["call"]

#     @property
#     def available(self) -> bool:
#         return self._model is not None

#     @property
#     def provider(self) -> str:
#         return self._provider_name

#     def _call_llm(self, prompt: str) -> str:
#         return self._call_fn(self._model, prompt)

#     def extract_notice_data(self, text: str, source_url: str, source_type: str) -> NoticeData:
#         """
#         Extract structured data from notice text.

#         Three-layer extraction:
#         1. URL hint — extract company name from PDF filename
#         2. LLM extraction — with smart truncation and improved prompt
#         3. Regex fallback — fills gaps if LLM misses fields or fails entirely
#         """
#         # Layer 1: Always compute regex fallback first (free, robust)
#         fallback = _regex_extract(text)

#         # Layer 1b: Try to get company name from URL
#         url_hint = _extract_company_hint_from_url(source_url)
#         if url_hint and not fallback.get("company_name"):
#             fallback["company_name"] = url_hint
#             fallback["borrower_name"] = url_hint

#         # If no LLM available, return fallback
#         if not self._model or not text:
#             return self._notice_from_dict(
#                 fallback,
#                 source_url=source_url,
#                 source_type=source_type,
#                 raw_text_snippet=text[:500] if text else "",
#             )

#         # Layer 2: LLM extraction with smart truncation
#         prepared_text = _prepare_text_for_extraction(text)
#         prompt = EXTRACTION_PROMPT.format(text=prepared_text, source_url=source_url)

#         try:
#             raw_response = self._call_llm(prompt)
#             raw = self._clean_json_response(raw_response)
#             data = json.loads(raw)

#             # Layer 3: Merge — LLM values win, fallback fills gaps
#             merged = {**fallback}
#             for k, v in data.items():
#                 if v not in (None, "", [], {}):
#                     merged[k] = v

#             # If LLM still missed company_name but URL has it, use URL hint
#             if not merged.get("company_name") and url_hint:
#                 merged["company_name"] = url_hint
#                 if not merged.get("borrower_name"):
#                     merged["borrower_name"] = url_hint

#             return self._notice_from_dict(
#                 merged,
#                 source_url=source_url,
#                 source_type=source_type,
#                 raw_text_snippet=text[:500],
#             )

#         except Exception as e:
#             logger.warning(f"{self._provider_name} extraction failed ({e}) → using regex fallback")

#             # Even on failure, try URL hint
#             if url_hint and not fallback.get("company_name"):
#                 fallback["company_name"] = url_hint
#                 fallback["borrower_name"] = url_hint

#             return self._notice_from_dict(
#                 fallback,
#                 source_url=source_url,
#                 source_type=source_type,
#                 raw_text_snippet=text[:500],
#             )

#     @staticmethod
#     def _notice_from_dict(d: dict, source_url: str, source_type: str, raw_text_snippet: str) -> NoticeData:
#         dates = []
#         for item in d.get("dates", []) or []:
#             if isinstance(item, dict) and item.get("label") and item.get("value"):
#                 dates.append(DateInfo(label=item["label"], value=item["value"]))

#         amounts = []
#         for item in d.get("amounts", []) or []:
#             if isinstance(item, dict) and item.get("label") and item.get("value"):
#                 amounts.append(AmountInfo(label=item["label"], value=item["value"]))

#         return NoticeData(
#             title=d.get("title"),
#             company_name=d.get("company_name"),
#             borrower_name=d.get("borrower_name"),
#             bank=d.get("bank"),
#             notice_type=d.get("notice_type"),
#             auction_date=d.get("auction_date"),
#             reserve_price=d.get("reserve_price"),
#             due_amount=d.get("due_amount"),
#             dates=dates,
#             amounts=amounts,
#             source_url=source_url,
#             source_type=source_type,
#             raw_text_snippet=raw_text_snippet,
#         )

#     @staticmethod
#     def _clean_json_response(raw: str) -> str:
#         raw = raw.strip()
#         if raw.startswith("```"):
#             lines = raw.split("\n")
#             lines = lines[1:]
#             if lines and lines[-1].strip() == "```":
#                 lines = lines[:-1]
#             raw = "\n".join(lines).strip()
#         return raw


# # Backward-compatible alias
# GeminiClient = LLMClient

"""
LLM Client — Extraction Only (Multi-Provider)
===============================================

- Supports Gemini / OpenAI / Claude
- Robust to Gemini quota/429 by retry + regex fallback extraction
- Smart text truncation: sends head + tail, not just head
- Source URL passed as hint for company name extraction
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from .config import logger, MAX_TEXT_FOR_LLM
from .models import AmountInfo, DateInfo, NoticeData


# =============================================================================
# Extraction Prompt
# =============================================================================

EXTRACTION_PROMPT = """Extract structured data from this ARC/NPA notice. Return ONLY valid JSON.

CRITICAL INSTRUCTIONS:
- The COMPANY NAME is usually in a table or list — look for "Borrower", "Account Name", "Name of Borrower/Company"
- Extract the FULL company name, not abbreviated (e.g. "Vivimed Labs Ltd" not just "Labs Ltd", "Prince Rice Mill Pvt Ltd" not just "Mills Pvt Ltd")
- The title should be the SPECIFIC notice title, NOT the generic header like "Web Notice Transfer of..." or page boilerplate
- For SBI/bank notices, the actual borrower data is often in a TABLE near the end of the document — look there first
- Skip boilerplate text like "In terms of the Bank's Policy...", "1 | P a g e", page headers/footers
- The source URL below may contain the company name as a hint — use it to verify your extraction
- IFCI, SBI, PNB, BOB, BOI, UCO, IDBI, Union Bank etc. are BANKS — they are NEVER the borrower/company_name
- company_name is the entity whose loan is stressed or whose assets are being sold, NOT the institution selling them
- If the document is an addendum/corrigendum/general circular with no specific borrower, set company_name to null

Source URL (may contain company name): {source_url}

Return this exact JSON structure:
{{
  "title": "Specific title of THIS notice (not generic header or boilerplate)",
  "company_name": "FULL name of the company/borrower (check tables and URL for hints)",
  "borrower_name": "Name of borrower if different from company, or null",
  "bank": "Name of bank/institution",
  "notice_type": "SARFAESI / Swiss Challenge / NPA Sale / DRT Sale / Auction / Other",
  "auction_date": "The auction/sale date (e.g. '27.02.2026') or null",
  "reserve_price": "Reserve price WITH UNIT (e.g. 'Rs. 10.50 Cr') or null",
  "due_amount": "Total due amount WITH UNIT (e.g. 'Rs. 924.96 Cr') or null",
  "dates": [
    {{"label": "descriptive_label (e.g. publication_date, bid_deadline, submission_date)", "value": "date string"}}
  ],
  "amounts": [
    {{"label": "descriptive_label (e.g. emd, reserve_price, outstanding_principal)", "value": "amount with currency and unit"}}
  ]
}}

IMPORTANT:
- due_amount and reserve_price MUST include unit (Cr/Lakhs/Lakh). "924.96" alone is WRONG — specify "Rs. 924.96 Cr"
- reserve_price of "Rs. 100" in Swiss Challenge means Rs. 100 per unit of debt — note this as "Rs. 100 (per unit)"
- If a field is not found, use null (not "Not specified" or "N/A")
- Keep original formatting for dates
- The notice may be in Hindi, Kannada, Tamil, or other Indian languages — extract ALL fields regardless of language

Notice text:
{text}"""


# =============================================================================
# Regex fallback extraction (works even when LLM quota=0)
# =============================================================================

_DATE_PATTERNS = [
    re.compile(r"\b([0-3]?\d)[./-]([01]?\d)[./-]((?:19|20)\d{2})\b"),
    re.compile(
        r"\b([0-3]?\d)\s+(jan|january|feb|february|mar|march|apr|april|may|jun|june"
        r"|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
        r"\s+((?:19|20)\d{2})\b",
        re.I,
    ),
]

_AMOUNT_RE = re.compile(
    r"(?i)\b(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(cr|crore|lakhs?|lakh|mn|million|bn|billion)?\b"
)

_LABEL_HINTS = [
    ("reserve", re.compile(r"(?i)\breserve\s+price\b")),
    ("emd", re.compile(r"(?i)\bemd\b|\bearnest\s+money\b")),
    ("due", re.compile(r"(?i)\b(total\s+)?dues?\b|\boutstanding\b|\bpayable\b")),
]

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
            "title": None, "company_name": None, "borrower_name": None,
            "bank": None, "notice_type": None, "auction_date": None,
            "reserve_price": None, "due_amount": None, "dates": [], "amounts": [],
        }

    t = " ".join(text.split())

    # title
    title = t[:140] if len(t) > 10 else None

    # bank
    bank = None
    if re.search(r"(?i)\bstate\s+bank\s+of\s+india\b|\bSBI\b", text):
        bank = "State Bank of India"
    elif _BANK_RE.search(text):
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
    found_dates = []
    for pat in _DATE_PATTERNS:
        for mm in pat.finditer(text):
            ds = mm.group(0)
            if ds not in found_dates:
                found_dates.append(ds)

    auction_date = None
    m_auc = re.search(r"(?i)\b(e-?auction|auction)\b.{0,120}", text)
    if m_auc:
        for pat in _DATE_PATTERNS:
            mdate = pat.search(m_auc.group(0))
            if mdate:
                auction_date = mdate.group(0)
                break

    dates = []
    for d in found_dates:
        label = "auction_date" if auction_date and d == auction_date else "date"
        dates.append({"label": label, "value": d})

    # amounts
    found_amounts = []
    for am in _AMOUNT_RE.finditer(text):
        raw = am.group(0).strip()
        if raw not in found_amounts:
            found_amounts.append(raw)

    reserve_price = None
    due_amount = None
    amounts = []

    for raw in found_amounts:
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

    return {
        "title": title,
        "company_name": company_name,
        "borrower_name": company_name,
        "bank": bank,
        "notice_type": notice_type,
        "auction_date": auction_date,
        "reserve_price": reserve_price,
        "due_amount": due_amount,
        "dates": dates,
        "amounts": amounts,
    }


# =============================================================================
# Smart Text Truncation
# =============================================================================

def _prepare_text_for_extraction(text: str, max_chars: int = MAX_TEXT_FOR_LLM) -> str:
    """
    Send the LLM the USEFUL parts of the document, not just the beginning.

    Bank PDFs (especially SBI) have 2-3 pages of boilerplate before the
    actual borrower table. If we send only text[:8000], the LLM sees
    boilerplate and misses company names, amounts, etc.

    Strategy: head (context/header) + tail (tables/data)
    """
    if len(text) <= max_chars:
        return text

    # Head: first 2000 chars — gives context (bank name, notice type)
    # Tail: last 6000 chars — where tables and actual data usually are
    head_size = 2000
    tail_size = max_chars - head_size

    head = text[:head_size]
    tail = text[-tail_size:]

    return f"{head}\n\n[...boilerplate omitted — data section below...]\n\n{tail}"


# =============================================================================
# Company Name from URL (hint extraction)
# =============================================================================

def _extract_company_hint_from_url(url: str) -> Optional[str]:
    """
    Many PDF URLs contain the company name. Extract it as a hint.

    Examples:
      .../Transfer+of+Stressed+Loan+Exposure+-+Vivimed+Labs+Ltd.pdf → "Vivimed Labs Ltd"
      .../Web+Notice+for+sale+-+Prince+Rice+Mill+Pvt+Ltd.pdf → "Prince Rice Mill Pvt Ltd"
    """
    if not url:
        return None

    # Get the filename part
    from urllib.parse import urlparse, unquote
    path = unquote(urlparse(url).path)
    filename = path.split("/")[-1].replace("+", " ").replace("%20", " ")

    # Remove file extension
    filename = re.sub(r"\.(pdf|html?)$", "", filename, flags=re.I)

    # Try to find company-like name after common separators
    # Pattern: "...Transfer of Stressed Loan Exposure - COMPANY NAME (1)"
    m = re.search(r"[-–—]\s*(.+?)(?:\s*\(\d+\))?\s*$", filename)
    if m:
        candidate = m.group(1).strip()
        # Clean up common noise
        candidate = re.sub(r"^\d+_?", "", candidate).strip()
        if len(candidate) > 3:
            return candidate

    return None


# =============================================================================
# Providers: Gemini / OpenAI / Claude
# =============================================================================

def _init_gemini() -> object | None:
    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("google-generativeai not installed. Run: pip install google-generativeai")
        return None

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("No Gemini API key. Set GEMINI_API_KEY in .env")
        return None

    logger.info(f"Gemini key loaded (ends with): {api_key[-6:]}")
    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")
        model = genai.GenerativeModel(model_name)
        logger.info(f"LLM initialized: Gemini ({model_name})")
        return model
    except Exception as e:
        logger.error(f"Gemini init failed: {e}")
        return None


def _call_gemini(model, prompt: str) -> str:
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            resp = model.generate_content(prompt)
            return resp.text
        except Exception as e:
            last_err = e
            msg = str(e)
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
            break
    raise last_err or RuntimeError("Gemini call failed")


def _init_openai() -> object | None:
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
        logger.info(f"LLM initialized: OpenAI ({os.getenv('OPENAI_MODEL_NAME', 'gpt-4o-mini')})")
        return client
    except Exception as e:
        logger.error(f"OpenAI init failed: {e}")
        return None


def _call_openai(client, prompt: str) -> str:
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return response.choices[0].message.content


def _init_claude() -> object | None:
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
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-20250514"),
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


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
    Multi-provider LLM client for extraction only.

    Key changes from previous version:
    - No more decide_next_action() — pipeline handles flow
    - Smart text truncation (head + tail)
    - Source URL passed as company name hint
    - Regex fallback always computed first for robustness
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

        Three-layer extraction:
        1. URL hint — extract company name from PDF filename
        2. LLM extraction — with smart truncation and improved prompt
        3. Regex fallback — fills gaps if LLM misses fields or fails entirely
        """
        # Layer 1: Always compute regex fallback first (free, robust)
        fallback = _regex_extract(text)

        # Layer 1b: Try to get company name from URL
        url_hint = _extract_company_hint_from_url(source_url)
        if url_hint and not fallback.get("company_name"):
            fallback["company_name"] = url_hint
            fallback["borrower_name"] = url_hint

        # If no LLM available, return fallback
        if not self._model or not text:
            return self._notice_from_dict(
                fallback,
                source_url=source_url,
                source_type=source_type,
                raw_text_snippet=text[:500] if text else "",
            )

        # Layer 2: LLM extraction with smart truncation
        prepared_text = _prepare_text_for_extraction(text)
        prompt = EXTRACTION_PROMPT.format(text=prepared_text, source_url=source_url)

        try:
            raw_response = self._call_llm(prompt)
            raw = self._clean_json_response(raw_response)
            data = json.loads(raw)

            # Layer 3: Merge — LLM values win, fallback fills gaps
            merged = {**fallback}
            for k, v in data.items():
                if v not in (None, "", [], {}):
                    merged[k] = v

            # If LLM still missed company_name but URL has it, use URL hint
            if not merged.get("company_name") and url_hint:
                merged["company_name"] = url_hint
                if not merged.get("borrower_name"):
                    merged["borrower_name"] = url_hint

            return self._notice_from_dict(
                merged,
                source_url=source_url,
                source_type=source_type,
                raw_text_snippet=text[:500],
            )

        except Exception as e:
            logger.warning(f"{self._provider_name} extraction failed ({e}) → using regex fallback")

            # Even on failure, try URL hint
            if url_hint and not fallback.get("company_name"):
                fallback["company_name"] = url_hint
                fallback["borrower_name"] = url_hint

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