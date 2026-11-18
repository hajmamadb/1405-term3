---
name: academic-paper-harvest
description: Harvest and organize academic papers from Academia.edu (and similar paper sites) through the user's already-logged-in Chrome over the Chrome DevTools Protocol, download their PDFs, extract text, classify them against a thesis/topic, sort them into folders, and build a Persian literature-review table (Excel). Use this skill whenever the user wants to find/download/collect papers on a research topic from Academia.edu or a paper site using their browser login, batch-download PDFs via CDP, classify an archive of papers into relevant/weakly-relevant/irrelevant, sort papers into folders without deleting anything, or build a literature-review table from a set of PDFs. Trigger on phrases like "گردآوری مقاله", "دانلود مقالات از آکادمیا", "بررسی و ساماندهی مقالات", "جدول مرور ادبیات", "find and download papers on X", even if the user does not say "CDP" or "skill".
---

# Academic Paper Harvest

Collect, download, classify, and tabulate academic papers for a literature review,
driving the **user's own already-logged-in Chrome** over the **Chrome DevTools Protocol (CDP)**.
Academia.edu (and friends) sit behind Cloudflare and often require login to see full text, so the
reliable path is: talk to the user's real browser (which is logged in) instead of a fresh headless
session. This skill bundles the exact toolchain that has been battle-tested on this workflow.

The two things that make or break this workflow are (a) respecting Cloudflare rate limits, and
(b) never deleting the user's files — only moving them. Everything else is mechanical.

## When to use

- The user wants to find papers on a thesis/research topic and download the full PDFs from
  Academia.edu (or a similar paper site) using their browser login.
- The user has a folder/archive of PDFs and wants them classified into "relevant / weakly
  relevant / irrelevant" against the thesis topic + keywords, then sorted into new folders.
  **Nothing may be deleted** — moves only.
- The user wants a **literature-review table** (Excel) from a set of already-downloaded PDFs,
  typically in Persian, with Persian title translations and Persian findings.

If the user is only doing a light web search and doesn't need PDFs or their login, prefer the
`exa-search` skill or plain web tools instead. This skill is for the heavier browser-CDP harvest.

## Prerequisites (Phase 0)

Check these before anything else; the rest fails fast if they're missing.

1. **Chrome with CDP on port 9222, user logged in.** The user must be logged into the paper site
   (e.g. Academia.edu) in the very Chrome instance you'll drive. If CDP is not up, run
   `scripts/start-chrome-cdp.bat` (it restarts Chrome with `--remote-debugging-port=9222` using the
   user's existing profile, so the login persists). Then confirm with `node scripts/cdp.mjs
   list-targets`.
   - **Tab IDs change on every Chrome restart.** Always re-run `list-targets` and grab a fresh
     page-tab id before driving it; never reuse a hardcoded id across a restart.
   - If a tab shows a `chrome-error://` / "اتصال شما قطع شد" page, the machine slept — just create
     a new tab with `new-tab` and verify login with `scripts/js/check-login.js`.
2. **Python with `pypdf` and `openpyxl`.** Use the DSH runtime python. If a package is missing,
   `pip install` may fail to resolve `files.pythonhosted.org` (DNS) — in that case use the Aliyun
   mirror: `pip install pypdf openpyxl -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com`.

Node is required for the `.mjs` CDP helpers (it ships with the runtime).

## Phase 1 — Search (build the candidate list)

Run `scripts/run-search.ps1` per query:

```
.\run-search.ps1 -TabId <TAB> -Query "short phrase" -WaitSec 15
```

It types the query into the site's search box, presses Enter, waits, and prints a JSON of result
cards (`id`, `href`, `text`).

**Why short phrases only:** Academia.edu's full-text search does **not** handle complex boolean
queries (`("a" OR "b") AND ("c")`) — they return 0 or junk. Simple multi-word phrases work. Build
several targeted phrases from the topic's keyword sets (English and Persian separately) instead of
one giant boolean expression.

**Rate limiting:** Cloudflare throws a "Just a moment…" challenge after ~4 fast requests.
**Pause 35–50 seconds between searches** (a random pause is fine). Never fire searches back to back.
If you hit the challenge, wait ~40s and retry — don't try to bypass it.

Collect the good `href` values into a candidate list. For Persian queries the title tab may be thin;
click the "PAPERS (FULL TEXT)" tab (`scripts/js/click-fulltext-and-extract.js`) and read the results
with `scripts/js/extract-persian.js`.

## Phase 2 — Download PDFs

Download by **clicking the real download button in the page**, not by `fetch()`ing the attachment
URL — in-page `fetch()` of the PDF is blocked by Cloudflare (`TypeError: Failed to fetch`) and
should not be used.

`scripts/download-pdf3.mjs <tab> <paperUrl> <downloadDir>`:
- sets `Browser.setDownloadBehavior` (allow + events) at the browser level,
- navigates to the paper page,
- clicks the `arrow_downward … Download PDF` button (do **not** click "PDF Pack"/"Package"),
- waits up to ~60s for the `downloadProgress` event to reach `completed`.

For many papers, put them in `scripts/batch-download.ps1` (or a copy of it) which iterates the list
with a 35–50s random pause between each and reports OK/ISSUE per file.

**Quality check after download:** verify the file's first bytes are `%PDF` (or `PK` if it actually
came down as a .docx/OOXML). A .docx means the site only had a Word original — convert it to PDF
via Word COM if a PDF is required, or keep the .docx. Rename to a stable, sortable name like
`NN_Author_Year_Title.pdf` (number new papers so they slot after existing ones).

## Phase 3 — Classify & sort (NO deletions)

The user's hard rule: **nothing is ever deleted; only moved.** The thesis topic + keywords are the
ground truth for relevance — classify by **content**, not by filename.

1. Extract text from every file in the tree with `scripts/extract_all.py <root> <out.jsonl>`
   (first 4 PDF pages / ~120 docx paragraphs / txt, capped chars each).
2. Judge each paper against the topic's core dimensions. A useful triad (adapt to the topic):
   - **A** — the domain concept (e.g. organizational memory & knowledge)
   - **B** — the human-capital concept (e.g. turnover / talent loss)
   - **C** — the context (e.g. media / newsroom)
   A paper is "related" if it meaningfully touches ≥1 dimension in the right context, or is a strong
   general study clearly transferable. Weak/no connection → "weakly related" or "irrelevant".
   Duplicates: keep **both** copies (mark one as a duplicate in the notes); do not delete either.
3. Create the target folders (e.g. `مرتبط`, `کم_ارتباط`, `نامرتبط`) and **move** files in.
   `scripts/sort-papers.ps1` is a working template that reads a `classification.json`
   (`{"related":[{"rel","reason"}], "unrelated":[...]}`) and moves files into the three folders,
   handling filename collisions with a numeric suffix and never deleting.
4. Verify: total files in the three folders == original count; nothing left unaccounted for.

If the classification is large, delegate the per-paper judgment to a subagent that reads the
extracted JSONL and returns `classification.json` — then run the sort script.

## Phase 4 — Literature-review table (Excel)

For an archive of already-classified/related PDFs:

1. `scripts/extract_full.py <relatedDir> <out.jsonl>` — first 8 pages each (enough for metadata +
   finding). (Use `extract_first2.py` if you only need author/year/journal.)
2. `scripts/build_lit_table_v2.py` — derives **dimension** (A/B/C) and **methodology** from keyword
   signals in the text. This is a first pass; the *human/LLM curation* layer fills the rest.
3. `scripts/build_final_table.py` — the curation layer: a `CURATED` dict supplies reliable
   `authors / year / title / title_fa (Persian translation) / journal`, a `FINDINGS` dict supplies
   a one-sentence **Persian** key finding per paper, and `relevance` maps each dimension to the
   thesis section it supports. **Goal: no "؟" in any field** — fill every gap from the filename or
   text.
4. `scripts/build_excel_final.py` — writes the final `.xlsx` (openpyxl) with 10 columns, a
   **B Nazanin** font, frozen header, and auto-filter. Columns:
   `شماره | نویسنده(ها) | سال | عنوان (Original) | عنوان (فارسی) | مجله/منبع | بُعد پایان‌نامه |
   روش‌شناسی | یافته/مفهوم کلیدی | ارتباط با پایان‌نامه`.

The Persian columns (`title_fa`, `finding`, `relevance`) must be fully Persian. `authors`/`journal`
keep their original language.

## Final deliverable

Give the user a short Persian summary: counts per folder, the new table path, and any borderline
decisions or duplicates. Use `present` for the final files (the `.xlsx`, and the sort report if you
wrote one). Keep the machine asleep-safe: if a CDP call returns a sleep/network error, just make a
new tab and continue — don't treat it as a hard failure.

## Reference

For the deep troubleshooting notes (redirect behavior, Cloudflare, the fetch gotcha, tab-id churn,
Word COM conversion, the pip mirror), read `references/academia-cdp.md`. Read it when something
unexpected happens or before a first run on a new machine.
