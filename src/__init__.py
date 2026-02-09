"""
ARC Notice Extraction Agent
============================
Autonomous agent for extracting structured data from ARC/NPA notices.

Architecture:
- agent.py   → ReAct loop (the orchestrator)
- browser.py → Playwright browser tools (the hands)
- gemini.py  → Gemini AI client (the brain)
- models.py  → Pydantic data models (the vocabulary)
- config.py  → Settings and keywords
- utils.py   → Regex fallback extractors
"""

from .agent import NoticeExtractionPipeline
from .config import logger
