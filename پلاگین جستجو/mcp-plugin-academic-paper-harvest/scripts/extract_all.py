#!/usr/bin/env python
"""Extracts text from all PDFs/docx in the tree and writes a JSONL file of first-page text + filenames.
Usage: python extract_all.py <rootDir> <outJsonl>
"""
import sys, os, json
from pypdf import PdfReader

def extract_pdf(path, max_chars=4000):
    try:
        r = PdfReader(path)
        parts = []
        for i, page in enumerate(r.pages):
            if i >= 4: break  # first 4 pages enough for abstract/intro
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                parts.append("")
        return "\n".join(parts)[:max_chars]
    except Exception as e:
        return f"[PDF ERROR: {e}]"

def extract_docx(path, max_chars=4000):
    try:
        import docx
        d = docx.Document(path)
        text = "\n".join(p.text for p in d.paragraphs[:120])
        return text[:max_chars]
    except Exception as e:
        return f"[DOCX ERROR: {e}]"

def main():
    root, out = sys.argv[1], sys.argv[2]
    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            low = fn.lower()
            text = None
            if low.endswith(".pdf"):
                text = extract_pdf(full)
            elif low.endswith(".docx"):
                text = extract_docx(full)
            elif low.endswith(".txt"):
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        text = f.read(4000)
                except Exception as e:
                    text = f"[TXT ERROR: {e}]"
            else:
                continue
            rows.append({"rel": rel, "size": os.path.getsize(full), "text": text})
            print(f"extracted: {rel} ({len(text)} chars)", file=sys.stderr)
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"DONE: {len(rows)} files -> {out}")

if __name__ == "__main__":
    main()
