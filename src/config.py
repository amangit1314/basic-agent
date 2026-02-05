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

# Extraction Keywords
RELEVANT_KEYWORDS = [
    'Stressed Loan', 'NPA', 'Showcause', 'Swiss Challenge', 
    'Sale of Accounts', 'Sale of Financial Assets', 'Assignment of Debt',
    'Sale of Stressed', 'SARFAESI', 'Auction Notice', 'Web Notice'
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
