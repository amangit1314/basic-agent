import re
from typing import List
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
