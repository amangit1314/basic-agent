"""
ARC Notice Extractor - FastAPI Application
Accepts a URL + keywords from Spring Boot, returns structured notice JSON.
"""
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from src.extractor import extract_notices
from src.config import logger, RELEVANT_KEYWORDS


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Notice Extractor API starting")
    yield
    logger.info("Notice Extractor API shutting down")


app = FastAPI(
    title="ARC Notice Extractor", 
    description="Autonomous agent for extracting and summarizing ARC notices",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request / Response Models ---

class ExtractionRequest(BaseModel):
    url: str = Field(..., description="URL of the ARC/bank listing page")
    keywords: List[str] = Field(
        default_factory=lambda: list(RELEVANT_KEYWORDS),
        description="Keywords to filter notices (case-insensitive)",
    )
    max_depth: int = Field(default=2, ge=0, le=3, description="Max nested link depth")
    limit: Optional[int] = Field(default=None, ge=1, description="Max notices to extract")


class NoticeSummary(BaseModel):
    borrower: Optional[str] = None
    amount: Optional[str] = None
    property: Optional[str] = None
    auction_date: Optional[str] = None
    reserve_price: Optional[str] = None
    bank: Optional[str] = None
    notice_type: Optional[str] = None


class NoticeResult(BaseModel):
    title: str
    url: str
    type: str
    matched_keywords: List[str]
    summary: NoticeSummary
    full_text: str


class ExtractionResponse(BaseModel):
    status: str
    total_notices: int
    keyword_matches: int
    notices: List[NoticeResult]
    error: Optional[str] = None


# --- Endpoints ---

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "notice-extractor", "version": "1.0.0"}


@app.post("/extract", response_model=ExtractionResponse)
async def extract(request: ExtractionRequest):
    logger.info(f"Extraction request: url={request.url}, keywords={len(request.keywords)}")
    try:
        result = await asyncio.wait_for(
            extract_notices(
                url=request.url,
                keywords=request.keywords,
                max_depth=request.max_depth,
                limit=request.limit,
            ),
            timeout=300,
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Extraction timed out for {request.url}")
        raise HTTPException(status_code=504, detail="Extraction timed out (5 min limit)")
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
