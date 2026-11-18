# Academia.edu + Chrome CDP — deep troubleshooting notes

Read this before a first run on a new machine, or when something unexpected happens. These are
the concrete failure modes observed in the field and their fixes.

## Chrome + CDP setup

- Drive the **user's own Chrome**, already logged in. Fresh/headless sessions hit Cloudflare and
  have no login. `scripts/start-chrome-cdp.bat` restarts Chrome with `--remote-debugging-port=9222`
  using the existing user profile (`C:\Users\<user>\AppData\Local\Google\Chrome\User Data`) so the
  login persists.
- Confirm CDP is up: `Invoke-WebRequest http://127.0.0.1:9222/json/version`.
- `node cdp.mjs list-targets` returns **page** tabs. Extension service workers and background
  pages are noise — pick the `type: page` entry that is the paper site.
- **Tab IDs change on every Chrome restart.** Always re-`list-targets` and use the fresh id. A
  stale id gives "tab not found".
- If a tab shows `chrome-error://chromewebdata/` / "اتصال شما قطع شد" / `ERR_NETWORK_IO_SUSPENDED`,
  the PC slept during a wait. Create a new tab (`new-tab`) and re-verify login; don't treat it as a
  permanent failure.
- `/json/new` may return **405** on some Chrome builds — `cdp.mjs` already falls back to a `PUT`.

## Searching

- **Navigate to `/search?search=...` silently redirects to home.** The site is a React SPA; the
  working path is to type into the real search box. `run-search.ps1` does this: set
  `window.__searchQuery`, dispatch input + Enter on the `textarea` inside `#nav--search-input`.
  The real search URL becomes `/search?q=...`.
- **PowerShell quoting breaks JS with escaped double quotes.** `run-search.ps1` works around this by
  writing a `js\__query.js` file with a **single-quoted** JS string (escaping only `\` and `'`) and
  evaluating it via `cdp-file.mjs` (which reads the script from a file). Prefer `cdp-file.mjs` over
  inline JS strings whenever the snippet has quotes.
- **Complex boolean queries return 0 / irrelevant results.** Use simple multi-word phrases.
- **Cloudflare "Just a moment…"** after ~4 fast requests → pause **35–50s** between requests. If the
  challenge appears, wait ~40s and retry. Do not attempt to solve/bypass the challenge.

## Downloading

- **Do NOT `fetch()` the attachment URL in-page** → `TypeError: Failed to fetch` (Cloudflare).
- The reliable method: `Browser.setDownloadBehavior` (behavior: `allow`, set `downloadPath`,
  `eventsEnabled: true`) at the **browser** WebSocket level, then **click** the
  `arrow_downward … Download PDF` button (not "PDF Pack"/"Package"). Wait for
  `Page.downloadProgress` to reach `completed`. This is what `download-pdf3.mjs` does.
- **Some papers only have a .docx original** (no PDF on the site). The download comes down as an
  OOXML file (first bytes `PK`). Convert to PDF via Word COM:
  `WINWORD.EXE` → open → `$doc.SaveAs([string]$pdf, 17)` (17 = `wdFormatPDF`). WINWORD is at
  `C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE`.
- Persian papers often download under **numeric ids** (e.g. `41801874.pdf`). Rename to a readable,
  sortable name (`NN_Author_Year_Title.pdf`).
- **Verify after download:** first 4 bytes `%PDF` = good; `PK` = docx/OOXML.

## Text extraction

- Use the **DSH runtime python**. `pip install` can fail with "Failed to resolve IP address for
  'files.pythonhosted.org'" (DNS) — use the Aliyun mirror:
  `pip install <pkg> -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com`.
- `pypdf` prints `fontTools is required …` warnings for some CFF/Type1 fonts. These are **harmless**
  — the text still extracts (some glyphs may be imperfect). Don't treat the stderr noise as failure.
- Extraction caps: `extract_all.py` = 4 pages (classification); `extract_full.py` = 8 pages
  (literature table); `extract_first2.py` = 2 pages (metadata only). Adjust `max_chars` if needed.

## Classification & sorting

- **Never delete. Only move.** The user's hard constraint.
- Classify by **content** (read the abstract/first pages), not by filename.
- **Duplicates:** keep both copies; annotate one as "duplicate of X". Never drop either.
- `sort-papers.ps1` reads `classification.json`
  (`{"related":[{"rel","reason"}], "unrelated":[{"rel","reason"}]}`) and moves files into the
  folder(s); it appends a numeric suffix on filename collisions and prints a full log. Verify the
  final per-folder counts sum to the original total.

## Literature table

- The auto-classifier (`build_lit_table_v2.py`) is a **first pass** only — it derives dimension and
  method from keyword signals and is good at catching the big buckets but can mislabel methods.
- The curation layer (`build_final_table.py`) is where real quality comes from: hand-fill
  `authors / year / title / title_fa / journal` (from the text or filename), a **Persian one-sentence
  finding**, and the `relevance` mapping. Target **zero "؟"** in the final table.
- Excel: `B Nazanin` font, frozen header row, auto-filter. `openpyxl` required.

## Misc

- Long `pwsh` commands auto-move to a **background job**; collect with `job_output` (a single long
  `wait`) rather than repeatedly polling. `job_kill` stragglers that no longer matter.
- The user communicates in **Persian**; final summaries and table content should be in Persian.
