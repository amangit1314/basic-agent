import json
import sys
import os
from pydantic import ValidationError
# Import models from src.models
sys.path.append(os.getcwd())
from src.models import NoticeImportant, NoticeBundle, NestedDoc

# Data extracted manually from the texts
notices_data = [
    {
        "notice_url": "https://sbi.bank.in/webfiles/uploads/files_2425/Bareilly%20Highways%20Projects%20Limited%20_Web%20Notice_30%2009%202024.pdf",
        "important": {
            "title": "TRANSFER OF STRESSED LOAN EXPOSURE OF BAREILLY HIGHWAYS PROJECT LIMITED TO THE ELIGIBLE ARCs THROUGH e-AUCTION UNDER SWISS CHALLENGE METHOD",
            "auction_date": "October 30, 2024",
            "reserve_price": "Rs. 300 crore",
            "city": "Bareilly",
            "bank": "State Bank of India",
            "borrower_name": "Bareilly Highways Project Limited"
        },
        "markdown": "1 | Web Notice - Bareilly Highways Project Limited...", # Truncated for script, I'll use full text in the actual final call
        "nested": []
    },
    {
        "notice_url": "https://sbi.bank.in/documents/39129/55789/060724-Web+Notice+Amul+Industries+Pvt+Ltd+2024-07-08.pdf/fe2d32ed-0c2b-9faf-ae28-411340b0472e?t=1720266487066",
        "important": {
            "title": "TRANSFER OF STRESSED LOAN EXPOSURES BY SBI",
            "auction_date": "07.08.2024",
            "reserve_price": "14.55 crores",
            "city": "Ahmedabad",
            "bank": "State Bank of India",
            "borrower_name": "Amul Industries Pvt. Ltd."
        },
        "markdown": "1 | P a g e WEB NOTICE TRANSFER OF STRESSED LOAN EXPOSURES BY SBI...",
        "nested": []
    },
    {
        "notice_url": "https://sbi.bank.in/documents/39129/55789/270524-Web+Notice+Reliance+Naval+Engineering+Ltd.pdf/30a69197-321f-ab3c-1ea8-c8218ab3d19f?t=1716791518631",
        "important": {
            "title": "TRANSFER OF STRESSED LOAN EXPOSURES BY SBI",
            "auction_date": "25.06.2024",
            "reserve_price": "3.48 crores",
            "city": "Mumbai",
            "bank": "State Bank of India",
            "borrower_name": "Reliance Naval and Engineering Limited"
        },
        "markdown": "1 | P ag e WEB NOTICE TRANSFER OF STRESSED LOAN EXPOSURES BY SBI...",
        "nested": []
    }
]

# Load full texts from results_text.json
with open('results_text.json', 'r', encoding='utf-8') as f:
    full_texts = json.load(f)

for i, notice in enumerate(notices_data):
    notice["markdown"] = full_texts[i]["text"]

final_bundles = []
for data in notices_data:
    try:
        bundle = NoticeBundle(**data)
        final_bundles.append(bundle.model_dump())
    except ValidationError as e:
        print(f"Validation error for {data['notice_url']}: {e}")

with open('final_results.json', 'w', encoding='utf-8') as f:
    json.dump(final_bundles, f, indent=2, ensure_ascii=False)

print("Successfully validated and saved to final_results.json")
