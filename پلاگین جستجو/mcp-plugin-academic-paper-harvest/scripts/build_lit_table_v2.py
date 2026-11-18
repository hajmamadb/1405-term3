#!/usr/bin/env python
"""Build literature review table - cleaner version using filename metadata + text classification."""
import sys, os, json, re
from pypdf import PdfReader

def read_jsonl(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def classify_dimension(text):
    t = text[:4000].lower()
    dims = []
    a_kw = ['organizational memory', 'organizational forgetting', 'knowledge loss',
            'knowledge retention', 'knowledge transfer', 'collective memory',
            'transactive memory', 'knowledge management', 'tacit knowledge',
            'memory system', 'حافظه سازمانی', 'فراموشی سازمانی', 'مدیریت دانش',
            'انتقال دانش', 'از دست دادن دانش', 'نگهداشت دانش', 'knowledge repository',
            'memory system', 'organizational knowledge', 'collective forgetting']
    b_kw = ['employee turnover', 'turnover intention', 'attrition', 'brain drain',
            'talent retention', 'organizational commitment', 'staff retention',
            'job hopping', 'exit, voice', 'leave the field', 'leaving the profession',
            'career expectations', 'professional efficacy', 'exhaustion',
            'ترک خدمت', 'خروج نخبگان', 'گردش شغلی', 'ماندگاری', 'organizational commitment',
            'turnover', 'attrition', 'retention']
    c_kw = ['media', 'journalism', 'newsroom', 'broadcast', 'newspaper', 'tv news',
            'radio', 'irib', 'صداوسیما', 'رسانه', 'روزنامه‌نگاری', 'خبرگزاری',
            'اتاق خبر', 'media organization', 'local news', 'news ecosystem',
            'journalist', 'newsroom', 'newspaper']
    if any(k in t for k in a_kw): dims.append('A')
    if any(k in k for k in b_kw): dims.append('B')
    if any(k in t for k in c_kw): dims.append('C')
    return '+'.join(dims) if dims else '؟'

def extract_method(text):
    t = text[:5000].lower()
    methods = {
        'مرور نظام‌مند ادبیات': ['systematic review', 'literature review', 'review of the literature', 'systematic literature', 'state of the art'],
        'نظرسنجی / پیمایش': ['survey', 'questionnaire', 'likert', 'structural equation', 'pls', 'covariance', 'cross-sectional'],
        'کیفی / مصاحبه': ['interview', 'qualitative', 'phenomenology', 'grounded theory', 'case study', 'case-based', 'ethnographic'],
        'مطالعه موردی': ['case study', 'case-based'],
        'تحلیل آماری': ['regression', 'factor analysis', 'amh', 'ahp', 'fsa', 'seman', 'data analysis'],
        'توصیفی-تحلیلی': ['descriptive', 'analytical', 'descriptive-analytical'],
        'چارچوب / مدل نظری': ['theoretical framework', 'conceptual framework', 'model', 'framework'],
        'دلفی / نظرات خبرگان': ['delphi', 'expert opinion', 'panel of experts'],
        'مطالعه میدانی': ['field study', 'longitudinal', 'empirical'],
    }
    for method, keywords in methods.items():
        if any(k in t for k in keywords):
            return method
    return '؟'

def extract_finding(text):
    t = text[:6000]
    abstract = None
    m = re.search(r'(?:abstract|چکیده|خلاصه)\s*:?\s*(.{80,600})', t, re.I)
    if m:
        abstract = m.group(1).strip()
    if not abstract:
        lines = [l.strip() for l in t.split('\n') if l.strip() and 60 < len(l.strip()) < 500]
        if lines:
            abstract = lines[0]
        else:
            abstract = t[:300]
    sentences = re.split(r'(?<=[.!?])\s+', abstract)
    return ' '.join(sentences[:2])[:400]

def main():
    import sys
    if len(sys.argv) < 3:
        print("Usage: python build_lit_table_v2.py <papers.jsonl> <out.json>")
        sys.exit(1)
    jsonl_path = sys.argv[1]
    out_path = sys.argv[2]
    
    papers = read_jsonl(jsonl_path)
    rows = []
    for p in papers:
        text = p.get('text', '')
        fn = p.get('file', '')
        rows.append({
            "file": fn,
            "dimension": classify_dimension(text),
            "method": extract_method(text),
            "finding": extract_finding(text),
        })
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)
    
    print(f"Built {len(rows)} rows -> {out_path}")
    for i, r in enumerate(rows):
        print(f"  {i+1:2d} | {r['file'][:55]:55s} | dim={r['dimension']:8s} | {r['method']}")

if __name__ == "__main__":
    main()
