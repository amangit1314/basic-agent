"""
Pydantic Models — The Agent's Vocabulary
=========================================

LEARNING NOTE: Why Pydantic?
-----------------------------
Pydantic models are Python classes that validate data automatically.
Instead of passing around raw dicts (where a typo like "compnay_name" goes unnoticed),
Pydantic catches errors at runtime:

    data = NoticeData(company_name="Acme Corp", ...)  # Validated!
    data = NoticeData(compnay_name="Acme Corp", ...)  # TypeError!

They also:
- Auto-generate JSON schemas (useful for LLM prompts)
- Serialize to/from JSON with .model_dump() / .model_validate()
- Provide IDE autocomplete and type checking

ARCHITECTURE NOTE:
------------------
These models form three layers:
1. Agent Control — AgentAction, AgentState (how the agent thinks and tracks progress)
2. Domain Data  — NoticeData, DateInfo, AmountInfo (the actual extracted information)
3. Output        — ExtractionResult (what gets saved to disk)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# =============================================================================
# Layer 1: Agent Control Models
# =============================================================================
# These models control the agent's behavior — what it can do and what it remembers.

# class AgentAction(BaseModel):
#     """
#     Represents a single decision by the agent.

#     LEARNING NOTE: This is the output of the "Think" step in ReAct.
#     The LLM returns which tool to use, what arguments to pass, and WHY it chose this.
#     The 'reasoning' field is crucial for debugging — you can trace exactly
#     why the agent made each decision.
#     """

#     tool: Literal[
#         "navigate",       # Go to a URL and get the page HTML
#         "find_links",     # Scan current page for notice links matching keywords
#         "read_page",      # Visit a specific link and get its text content (HTML or PDF)
#         "extract_data",   # Use AI to extract structured data from text
#         "done",           # Agent is finished — all notices processed
#     ] = Field(..., description="Which tool the agent wants to use")

#     args: dict = Field(
#         default_factory=dict,
#         description="Arguments for the chosen tool (e.g. {'url': 'https://...'})",
#     )

#     reasoning: str = Field(
#         ...,
#         description="Why the agent chose this action — for debugging and transparency",
#     )

# class AgentState(BaseModel):
#     """
#     The agent's working memory — everything it knows and has done.

#     LEARNING NOTE: State management is critical for agents. Without state,
#     the agent would forget what it already visited and loop forever.
#     This model tracks:
#     - Where the agent has been (visited_urls)
#     - What it found (discovered_links, extracted_notices)
#     - What's left to do (pending_links)
#     - Safety limits (step_count vs max_steps)

#     The 'model_config' at the bottom allows set types (visited_urls) to be
#     serialized — Pydantic doesn't serialize sets by default.
#     """

#     target_url: str = Field(..., description="The original URL the user provided")
#     current_url: str | None = Field(None, description="URL the agent is currently on")
#     visited_urls: set[str] = Field(default_factory=set, description="URLs already visited")
#     last_read_nested_links: list[str] = Field(
#         default_factory=list, description="Nested links found on the last read page"
#     )
#     discovered_links: list[dict] = Field(
#         default_factory=list,
#         description="All notice links found on the listing page",
#     )
#     pending_links: list[dict] = Field(
#         default_factory=list,
#         description="Links not yet visited — the agent's work queue",
#     )
#     extracted_notices: list[NoticeData] = Field(
#         default_factory=list,
#         description="Successfully extracted notice data",
#     )
#     step_count: int = Field(0, description="How many actions the agent has taken")
#     max_steps: int = Field(50, description="Safety limit — agent stops after this many steps")
#     status: Literal[
#         "starting",    # Agent just initialized
#         "exploring",   # Scanning the listing page for links
#         "extracting",  # Visiting individual notices and extracting data
#         "done",        # All work complete
#         "error",       # Something went wrong
#     ] = Field("starting", description="Current phase of the agent")
#     log: list[str] = Field(
#         default_factory=list,
#         description="Human-readable log of agent actions",
#     )

#     model_config = {"arbitrary_types_allowed": True}

# =============================================================================
# Layer 2: Domain Data Models
# =============================================================================
# These models represent the actual data we're extracting from notices.

class DateInfo(BaseModel):
    """
    A single date extracted from a notice.

    LEARNING NOTE: Notices contain MANY dates — auction date, possession date,
    publication date, deadline date. Instead of guessing which is which,
    we extract ALL dates with their labels and let the consumer decide.
    """

    label: str = Field(
        ...,
        description="What this date represents (e.g. 'auction_date', 'publication_date')",
    )
    value: str = Field(
        ...,
        description="The date value (e.g. '27.02.2026', '13-Mar-2026')",
    )

class AmountInfo(BaseModel):
    """
    A single monetary amount extracted from a notice.

    LEARNING NOTE: Same principle as DateInfo — notices contain multiple amounts:
    reserve price, total dues, outstanding principal, EMD, etc.
    We capture all of them with labels.
    """

    label: str = Field(
        ...,
        description="What this amount represents (e.g. 'reserve_price', 'total_dues')",
    )
    value: str = Field(
        ...,
        description="The amount with currency (e.g. 'Rs. 17.50 Cr', 'INR 5,673.20 Crore')",
    )

class NoticeData(BaseModel):
    """
    Structured data extracted from a single ARC/NPA notice.

    This is the core output — one NoticeData per notice document.
    The AI extracts these fields; regex utils fill in gaps as fallback.
    """

    company_name: str | None = Field(
        None, description="Name of the company/borrower in the notice"
    )
    title: str | None = Field(
        None, description="Title or header of the notice"
    )
    borrower_name: str | None = Field(
        None, description="Name of the borrower (may differ from company)"
    )
    bank: str | None = Field(
        None, description="Bank or financial institution issuing the notice"
    )
    notice_type: str | None = Field(
        None,
        description="Type of notice: SARFAESI, NPA Sale, DRT, Swiss Challenge, Auction, etc.",
    )
    auction_date: str | None = Field(
        None, description="Date of the auction/sale"
    )
    reserve_price: str | None = Field(
        None, description="Reserve price amount"
    )
    due_amount: str | None = Field(
        None, description="Total due amount"
    )
    dates: list[DateInfo] = Field(
        default_factory=list,
        description="All dates found in the notice with their labels",
    )
    amounts: list[AmountInfo] = Field(
        default_factory=list,
        description="All monetary amounts found in the notice with their labels",
    )
    nested_links: list[str] = Field(
        default_factory=list, description="Links to nested documents (e.g. PDFs) found in this notice"
    )
    source_url: str = Field(..., description="URL where this notice was found")
    source_type: Literal["HTML", "PDF"] = Field(
        ..., description="Whether the source was an HTML page or PDF document"
    )
    raw_text_snippet: str = Field(
        "", description="First 500 chars of raw text — for reference/debugging"
    )

# =============================================================================
# Layer 3: Output Model
# =============================================================================
# This is what gets saved to the JSON file.

class ExtractionResult(BaseModel):
    """
    The final output of the agent — saved as JSON to the results/ folder.

    LEARNING NOTE: Notice that this wraps everything in a single object with
    metadata (timestamp, steps taken). This makes the output self-documenting —
    anyone reading the JSON file knows when it was created and how much work
    the agent did.
    """

    source_url: str = Field(..., description="The original URL that was processed")
    extraction_timestamp: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="When the extraction was performed",
    )
    agent_steps_taken: int = Field(
        0, description="How many ReAct steps the agent took"
    )
    total_notices_found: int = Field(
        0, description="Total number of notices successfully extracted"
    )
    notices: list[NoticeData] = Field(
        default_factory=list, description="All extracted notice data"
    )
    failed_urls: list[str] = Field(
        default_factory=list, description="URLs that failed to be processed"
    )
