# Empty Keywords Fix - Summary

## Problem
When `keywords: []` was sent to the API, the extractor returned zero notices instead of including all discovered notices.

## Solution
Modified the extractor to distinguish between:
- `None` → use default keywords
- `[]` → skip keyword filtering, include ALL notices
- `["keyword1", ...]` → filter by keywords (existing behavior)

## Files Changed

### 1. `src/extractor.py`
- **Lines 24-31**: Explicit handling for None vs empty list
- **Lines 39-48**: Skip filtering when keywords is empty
- **Lines 128-137**: Fixed `keyword_matches` counter to sum matched_keywords

### 2. `src/browser.py`
- **Lines 121-129**: Added `skip_keyword_filter` flag and logging
- **Lines 166-177**: Conditional keyword matching
- **Line 180**: Updated inclusion condition

## Testing

Run `python test_empty_keywords.py` to verify:
1. Empty keywords returns ALL notices ✅
2. Keywords still filter correctly (backward compatible) ✅
3. `matched_keywords` is `[]` when no keywords provided ✅
4. `keyword_matches` counter is `0` when no keywords provided ✅

## API Behavior

| Request | Result |
|---------|--------|
| `{"url": "...", "keywords": null}` | Uses default keywords |
| `{"url": "...", "keywords": []}` | Returns ALL notices (no filter) |
| `{"url": "...", "keywords": ["NPA"]}` | Returns only NPA notices |

## No Breaking Changes
- API contract unchanged
- Response structure unchanged
- Fully backward compatible
