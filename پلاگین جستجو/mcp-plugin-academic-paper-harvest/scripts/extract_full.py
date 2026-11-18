#!/usr/bin/env python
"""Extracts text (up to 8 pages) from all PDFs/docx in a folder into JSONL."""
import sys, os, json
from pypdf import PdfReader

def extract_pdf(path, max_chars=8000):
    try:
        r = PdfReader(path)
        parts = []
        for i, page in enumerate(r.pages):
            if i >= 8: break
            try: parts.append(page.extract_text() or "")
            except Exception: parts.append("")
        return "\n".join(parts)[:max_chars]
    except Exception as e:
        return f"[PDF ERROR: {e}]"

def extract_docx(path, max_chars=8000):
    try:
        import docx
        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs[:200])[:max_chars]
    except Exception as e:
        return f"[DOCX ERROR: {e}]"

def main():
    root, out = sys.argv[1], sys.argv[2]
    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            low = fn.lower()
            if low.endswith(".pdf"): text = extract_pdf(full)
            elif low.endswith(".docx"): text = extract_docx(full)
            else: continue
            rows.append({"file": fn, "size": os.path.getsize(full), "text": text})
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"DONE: {len(rows)} files -> {out}")

if __name__ == "__main__":
    main()
