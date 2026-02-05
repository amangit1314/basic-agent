import re
from typing import List, Optional
from .config import DATE_PATTERNS

class ExtractionUtils:
    """Helper class for extraction logic (dates/entities/types)"""
    
    @staticmethod
    def extract_dates(text: str) -> List[str]:
        dates = []
        for pattern in DATE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                normalized = re.sub(r'[-/]', '.', match.strip())
                parts = normalized.split('.')
                if len(parts) == 3:
                    day, month, year = parts
                    if len(year) == 2: year = f"20{year}" if int(year) < 50 else f"19{year}"
                    norm_date = f"{day.zfill(2)}.{month.zfill(2)}.{year}"
                    if norm_date not in dates: dates.append(norm_date)
        return dates

    @staticmethod
    def extract_entities(text: str) -> List[str]:
        entities = []
        seen = set()
        
        # M/s Companies
        ms_pattern = r'M[/\\][Ss]\.?\s*([A-Z][A-Za-z0-9\s&.,()\'"-]+?)(?:\s*(?:Private|Pvt\.?)\s*(?:Limited|Ltd\.?)|\s*(?:Limited|Ltd\.?)|\s*,|\s*\(|$)'
        for match in re.findall(ms_pattern, text):
            name = f"M/s {match.strip().rstrip(',.')}".strip()
            if name.lower() not in seen and len(name) > 5:
                seen.add(name.lower()); entities.append(name)
        
        # Individuals
        ind_pattern = r'(?:Sh\.|Smt\.|Shri|Mr\.|Mrs\.)\s+([A-Za-z][A-Za-z\s]+?)(?:\s*,|\s*$|\s*[a-h]\))'
        for match in re.findall(ind_pattern, text):
            name = match.strip().rstrip(',')
            if name.lower() not in seen and len(name) > 2:
                seen.add(name.lower()); entities.append(name)
        return entities

    @staticmethod
    def determine_notice_type(text: str) -> str:
        type_patterns = [
            (r'DRT\s+SALE', "DRT Sale Notice"),
            (r'SARFAESI', "SARFAESI Notice"),
            (r'Swiss\s+Challenge', "Swiss Challenge Notice"),
            (r'Stressed\s+(?:Loan|Asset)', "Sale of Stressed Assets"),
            (r'NPA', "NPA Sale Notice")
        ]
        for pattern, label in type_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return label
        return "Auction Notice"

    @staticmethod
    def extract_due_amount(text: str) -> Optional[str]:
        # Exclude dates from being captured as amounts
        def is_date(s: str) -> bool:
            return bool(re.search(r'\d{1,2}[./-]\d{1,2}[./-]\d{2,4}', s))

        # Specialized pattern for "(Total dues)" and amount like "177.28(924.96)"
        table_pattern = r'Total\s*dues\s*\).*?([\d,.]{2,})\s*\(([\d,.]{2,})\)'
        match = re.search(table_pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            val = match.group(2).strip()
            if not is_date(val): return val

        # Better patterns that look for amounts, prioritizing those with suffixes
        patterns = [
            r'(?:Outstanding|Total\s+Dues?|Total\s+Dues?\s+as\s+on)\s*[:|-]?\s*(?:[\s\w()#]*?)\s*(?:Rs\.?|INR)?\s*\(([\d,.]{2,}(?:\s*(?:crore|lakh|cr))?)\)', # Priority to parenthesized amounts like (924.96)
            r'(?:Outstanding|Total\s+Dues?)\s*[:|-]?\s*[\s\w()]*?\s*(?:Rs\.?|INR)?\s*([\d,.]{2,}(?:\s*(?:crore|lakh|cr))?)',
            r'Principal\s+O/s\s*[:|-]?\s*[\s\w()]*?\s*(?:Rs\.?|INR)?\s*([\d,.]{2,}(?:\s*(?:crore|lakh|cr))?)'
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
                val = match.group(1).strip()
                if not is_date(val) and len(val) > 1:
                    return val
        return None

    @staticmethod
    def extract_reserve_price(text: str) -> Optional[str]:
        segments = text.split('\n')
        pattern = r'Reserve\s+Price\s*?[\s\w%]*?\s*[:|-]?\s*(?:Rs\.?|INR)?\s*([\d,.]{2,}(?:\s*(?:crore|lakh|cr))?)'
        
        candidates = []
        for segment in segments:
            # Exclude lines that describe mark-up or starting price or examples
            lower_seg = segment.lower()
            if "example" in lower_seg or "e.g." in lower_seg or "mark-up" in lower_seg or "starting" in lower_seg:
                continue
            
            match = re.search(pattern, segment, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                if val != '100' and len(val) > 1:
                    candidates.append(val)
        
        if candidates:
            # Prefer the one with 'Cr'
            with_cr = [c for c in candidates if 'cr' in c.lower() or 'crore' in c.lower()]
            if with_cr: return with_cr[0]
            # If several, the first one that looked like a clean "Reserve Price: X" is usually best
            return candidates[0]
            
        # Global fallback avoiding "example/mark-up" word in window
        matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            window = text[max(0, match.start()-60):min(len(text), match.end()+60)].lower()
            if "example" not in window and "e.g." not in window and "mark-up" not in window:
                val = match.group(1).strip()
                if val != '100': return val
                
        return None
