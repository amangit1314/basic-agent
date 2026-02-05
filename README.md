# Auction Notice Extractor Agent (Modular Deep Dive)

An autonomous agent for extracting auction notices from bank/ARC sites. Refactored for **Separation of Concerns** to be lightweight and maintainable.

## Project Structure

```
///
basic-agent/
├── src/                    # Modular Source Code
│   ├── config.py           # Configuration (Keywords, Patterns, Logger)
│   ├── models.py           # Pydantic Schemas for Tools
│   ├── utils.py            # Extraction Logic (Regex, Processing)
│   ├── tools.py            # CrewAI Tools
│   └── pipeline.py         # core extraction logic
├── main.py                 # Clean entry point
├── test_multiple.py        # Batch testing script
└── results/                # Extraction outputs (JSON)
```

## Quick Start

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Run Extraction
```powershell
# Default URL (SBI ARC/DRT)
python main.py

# Specific URL with limit
python main.py "https://example.com/auctions" --limit 5
```

## Developer Guide

- **Adding Keywords**: Update `src/config.py`.
- **Modifying Tools**: Edit `src/tools.py`.
- **Changing Logic**: Modify `src/pipeline.py` or `src/utils.py`.

## Features
- **Two-Stage Extraction**: List processing followed by deep-dive URL visits.
- **PDF Support**: Automatic text extraction from PDF notices.
- **Modular Design**: Easy to understand and extend for fast-developing environments.



<!-- company name, amount due -->
