#!/usr/bin/env python
"""Build the final literature-review table with all fields filled.

Usage:
    python build_final_table.py <classified.json> <related_dir> <curated.json> <out.json>

Inputs:
  classified.json — output of build_lit_table_v2.py: {"rows":[{"file","dimension","method"}]}
  related_dir     — folder containing the related papers (enumerated to build the row set)
  curated.json    — YOUR curated metadata keyed by filename. Each value may have:
                       authors, year, title, title_translated, journal, finding
                     Any field you omit defaults to "؟" — fill them in for a clean table.
  out.json        — where to write the final {"rows":[...]}

Notes:
  - "title_translated" is the translated title (e.g. into Persian) shown in its own column.
    For papers already in the target language, copy the title into this field.
  - "finding" should be a ONE-sentence key finding in the target language.
  - Relevance labels come from relevance_map.json (see build_excel_final.py for the column order).
  - Goal: zero "؟" in the final table.
"""
import sys, os, json, re

def parse_filename(fn):
    """Best-effort author/year/title from filename (fallback only)."""
    fn = os.path.splitext(fn)[0]
    fn = re.sub(r'^\d+_', '', fn)
    m = re.match(r'^(.+?)[_ ]((?:19|20)\d{2})[_ ](.+)$', fn)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return "؟", "؟", fn

def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def main():
    if len(sys.argv) < 5:
        print("Usage: python build_final_table.py <classified.json> <related_dir> <curated.json> <out.json>")
        sys.exit(1)
    classified_json, related_dir, curated_json, out_path = sys.argv[1:5]

    classified = load_json(classified_json)
    classified_map = {r['file']: r for r in classified['rows']}
    curated = load_json(curated_json)

    # Optional relevance label map: <related_dir>/../relevance_map.json
    rel_map_path = os.path.join(os.path.dirname(os.path.abspath(related_dir)), "relevance_map.json")
    relevance_map = load_json(rel_map_path) if os.path.exists(rel_map_path) else {}

    files = sorted(os.listdir(related_dir))
    files = [f for f in files if f.lower().endswith(('.pdf', '.docx'))]

    rows = []
    for fn in files:
        c = classified_map.get(fn, {'dimension': '؟', 'method': '؟'})
        cur = curated.get(fn, {})
        fa, fy, ft = parse_filename(fn)
        dim = c.get('dimension', '؟')
        rows.append({
            "file": fn,
            "authors": cur.get("authors", fa),
            "year": cur.get("year", fy),
            "title": cur.get("title", ft),
            "title_fa": cur.get("title_translated", cur.get("title", "؟")),
            "journal": cur.get("journal", "؟"),
            "dimension": dim,
            "method": c.get('method', '؟'),
            "finding": cur.get("finding", "؟"),
            "relevance": relevance_map.get(dim, "؟"),
        })

    rows.sort(key=lambda r: (r['dimension'], r['file']))

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_path}")
    print(f"Total: {len(rows)}")

    q_count = 0
    for r in rows:
        for field in ['authors', 'year', 'journal', 'title_fa', 'finding', 'relevance']:
            if '؟' in str(r[field]):
                q_count += 1
                print(f"  ؟ in {r['file']} -> {field}: {str(r[field])[:50]}")
    print(f"Remaining ؟ count: {q_count}")

if __name__ == "__main__":
    main()
