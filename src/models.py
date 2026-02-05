from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class WebScraperInput(BaseModel):
    """Input schema for WebScraperTool"""
    url: str = Field(..., description="The URL to scrape content from")

class ListingAnalyzerInput(BaseModel):
    """Input schema for ListingAnalyzerTool"""
    html_content: str = Field(..., description="Raw HTML content of listing page")
    base_url: str = Field(..., description="Base URL for resolving relative links")

class ContentFetcherInput(BaseModel):
    """Input schema for ContentFetcherTool"""
    url: str = Field(..., description="URL of the specific notice (HTML or PDF)")

class TextAnalysisInput(BaseModel):
    """Input schema for analysis tools"""
    text: str = Field(..., description="Text content to analyze")

class NoticeRow(BaseModel):
    """Schema for a single row in the listing page"""
    title: str = Field(..., description="Title of the notice")
    url: str = Field(..., description="Full URL to the notice detail page")
    date: Optional[str] = Field(None, description="Date of the notice if available")

class NoticeImportant(BaseModel):
    """Schema for critical information extracted from a notice page"""
    title: Optional[str] = Field(None, description="Detailed title of the notice")
    company_name: Optional[str] = Field(None, description="Name of the company involved")
    borrower_name: Optional[str] = Field(None, description="Name of the borrower/account holder")
    auction_date: Optional[str] = Field(None, description="Date of the auction")
    reserve_price: Optional[str] = Field(None, description="Reserve price for the auction")
    due_amount: Optional[str] = Field(None, description="Amount due or principal outstanding")
    city: Optional[str] = Field(None, description="City where the property/asset is located")
    bank: Optional[str] = Field(None, description="Name of the bank or financial institution")

class NestedDoc(BaseModel):
    """Schema for documents linked within a notice page"""
    url: str = Field(..., description="URL of the nested document")
    kind: str = Field(..., description="Type of document (pdf, doc, docx, html)")
    extracted_text: str = Field(..., description="Full text content of the document")
    important: Optional[NoticeImportant] = Field(None, description="Extracted important fields if applicable")

class NoticeBundle(BaseModel):
    """Complete bundle representing a notice and its associated data"""
    notice_url: str = Field(..., description="URL of the main notice page")
    important: NoticeImportant = Field(..., description="Primary or summary information")
    all_accounts: List[NoticeImportant] = Field(default_factory=list, description="List of all specific accounts found")
    account_count: int = Field(1, description="Number of accounts found in this notice")
    markdown: str = Field(..., description="Markdown content of the main notice page")
    nested: List[NestedDoc] = Field(default_factory=list, description="List of nested documents found")
