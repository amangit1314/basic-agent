from pydantic import BaseModel, Field

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
