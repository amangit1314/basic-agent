from pypdf import PdfReader
import json
import os

pdfs = [
    r'C:\Users\MY pc\.gemini\antigravity\brain\20c17884-1b53-47f5-a135-0067478a2dd4\.tempmediaStorage\ab9197dbe13e7b3d.pdf',
    r'C:\Users\MY pc\.gemini\antigravity\brain\20c17884-1b53-47f5-a135-0067478a2dd4\.tempmediaStorage\ed7c8e7603046a8f.pdf',
    r'C:\Users\MY pc\.gemini\antigravity\brain\20c17884-1b53-47f5-a135-0067478a2dd4\.tempmediaStorage\e170bb6cea842bd7.pdf'
]

results = []
for path in pdfs:
    try:
        reader = PdfReader(path)
        text = "\n".join([p.extract_text() for p in reader.pages])
        results.append({"path": path, "text": text})
    except Exception as e:
        results.append({"path": path, "error": str(e)})

with open('results_text.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("Saved to results_text.json")
