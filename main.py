import argparse
import asyncio
from src.agent import NoticeExtractionPipeline

async def main():
    parser = argparse.ArgumentParser(description="ARC Notice Extractor")
    parser.add_argument("url")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--keywords", type=str, default=None)
    parser.add_argument("--provider", default="gemini", choices=["gemini", "openai", "claude"])
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

    pipeline = NoticeExtractionPipeline(
        url=args.url, keywords=keywords,
        limit=args.limit, provider=args.provider,
    )

    result = await pipeline.run()
    
    if result.notices:
        path = pipeline.save_results(result)
        print(f"✅ Extracted {len(result.notices)} notices → {path}")
    else:
        print("❌ No notices found")

if __name__ == "__main__":
    asyncio.run(main())

## Final Structure
# src/
# ├── pipeline.py    # Was agent.py — now ~120 lines instead of ~300
# ├── browser.py     # Unchanged
# ├── llm.py         # Was gemini.py — extraction only, no reasoning
# ├── models.py      # Minus AgentAction, AgentState
# ├── utils.py       # Unchanged
# └── config.py      # Unchanged
# main.py            # Half the size