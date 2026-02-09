"""
ARC Notice Extraction Agent
============================
Autonomous agent for extracting structured data from ARC/NPA notices.

Architecture:
- pipeline.py   → pipeline (the flow)
- browser.py → Playwright browser tools (the hands)
- llm.py  → Multi LLM client (the brain)
- models.py  → Pydantic data models (the vocabulary)
- config.py  → Settings and keywords
- utils.py   → Regex fallback extractors
"""

from .pipeline import NoticeExtractionPipeline
from .config import logger
