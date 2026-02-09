"""
Configuration — Agent Settings & Constants
============================================

LEARNING NOTE: Why a separate config file?
-------------------------------------------
Hardcoding values like keywords, timeouts, and limits inside business logic
makes them impossible to change without editing code. A config file gives you
ONE place to tweak behavior. In production, these would come from environment
variables or a YAML file — but a Python module works great for a POC.
"""

import logging
import os

from dotenv import load_dotenv

# Load .env file (contains GEMINI_API_KEY, etc.)
load_dotenv()


# =============================================================================
# Logging
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("arc_agent")


# =============================================================================
# Agent Settings
# =============================================================================

# Maximum number of ReAct steps before the agent forcefully stops.
# This prevents infinite loops if the LLM keeps choosing actions.
MAX_AGENT_STEPS = 50

# Maximum number of notice links to process (None = no limit).
# Useful for testing — set to 3-5 to avoid processing 100+ notices.
DEFAULT_NOTICE_LIMIT: int | None = None

# Seconds to wait between page visits (rate limiting / politeness).
PAGE_DELAY_SECONDS = 1.0

# Maximum characters of text to send to Gemini for extraction.
# Gemini has a context window limit; we truncate long documents.
MAX_TEXT_FOR_LLM = 8000

# Minimum text length to consider a page "has content worth extracting".
MIN_CONTENT_LENGTH = 50


# =============================================================================
# Keywords for Notice Discovery
# =============================================================================
# These keywords are used to find notice links on listing pages.
# A link is considered relevant if its text, URL, or parent element
# contains any of these keywords (case-insensitive).

RELEVANT_KEYWORDS = [
    # Specific ARC/NPA notice types
    "Stressed Loan", "NPA", "Showcause", "Swiss Challenge",
    "Sale of Accounts", "Sale of Financial Assets", "Assignment of Debt",
    "Sale of Stressed", "SARFAESI", "Auction Notice", "Web Notice",
    # Generic auction/sale terms
    "e-auction", "E Auction", "DRT", "ARC", "Sale Notice",
    "Asset Sale", "Property Sale", "Recovery", "Possession Notice",
    "Public Notice", "Tender", "Bid", "Reserve Price",
]


# =============================================================================
# Date Extraction Patterns (for regex fallback)
# =============================================================================
# When the LLM fails to extract dates, these regex patterns are used.

DATE_PATTERNS = [
    r'E[-\s]?[Aa]uction\s+[Dd][Tt]\.?\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'E[-\s]?[Aa]uction\s+[Dd]ate\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'[Ee][-\s]?[Aa]uction\s+[Oo]n\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'[Aa]uction\s+[Dd][Tt]\.?\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'[Aa]uction\s+[Dd]ate\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'[Ss]ale\s+[Dd]ate\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'(?:dated?|on)\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
]
