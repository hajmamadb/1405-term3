#!/usr/bin/env python
"""Extract only first 2 pages (for metadata: author/year/journal) from all 54 papers."""
import sys, os, json
from pypdf import PdfReader

def extract_first2(path):
    try:
        r = PdfReader(path)
        parts = []
        for i, page in enumerate(r.pages):
            if i >= 2: break
            try: parts.append(page.extract_text() or "")
            except: pass
        return "\n".join(parts)[:3000]
    except Exception as e:
        return f"[ERROR: {e}]"

def main():
    root, out = sys.argv[1], sys.argv[2]
    rows = []
    for fn in sorted(os.listdir(root)):
        if not fn.lower().endswith(('.pdf', '.docx')): continue
        full = os.path.join(root, fn)
        if fn.lower().endswith('.pdf'):
            text = extract_first2(full)
        else:
            try:
                import docx
                d = docx.Document(full)
                text = "\n".join(p.text for p in d.paragraphs[:30])[:3000]
            except Exception as e:
                text = f"[ERROR: {e}]"
        rows.append({"file": fn, "text": text})
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"DONE: {len(rows)} files -> {out}")

if __name__ == "__main__":
    main()
