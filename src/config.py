import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logger configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("auction_extractor")

# Extraction Keywords - Broad list for notice discovery
RELEVANT_KEYWORDS = [
    # Specific auction types
    'Stressed Loan', 'NPA', 'Showcause', 'Swiss Challenge', 
    'Sale of Accounts', 'Sale of Financial Assets', 'Assignment of Debt',
    'Sale of Stressed', 'SARFAESI', 'Auction Notice', 'Web Notice',
    # Generic auction/sale terms
    'e-auction', 'E Auction', 'DRT', 'ARC', 'Sale Notice',
    'Asset Sale', 'Property Sale', 'Recovery', 'Possession Notice',
    'Public Notice', 'Tender', 'Bid', 'Reserve Price'
]

# Date extraction patterns
DATE_PATTERNS = [
    r'E[-\s]?[Aa]uction\s+[Dd][Tt]\.?\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'E[-\s]?[Aa]uction\s+[Dd]ate\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'[Ee][-\s]?[Aa]uction\s+[Oo]n\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'[Aa]uction\s+[Dd][Tt]\.?\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'[Aa]uction\s+[Dd]ate\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'[Ss]ale\s+[Dd]ate\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
    r'(?:dated?|on)\s*[:|-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
]
