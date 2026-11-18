# mcp-plugin-academic-paper-harvest

**Version:** 1.0.0 · **License:** MIT

A professional, relocatable plugin that harvests, downloads, classifies, and tabulates
academic papers — driving **your own already-logged-in Chrome** over the
**Chrome DevTools Protocol (CDP)**. Built for literature-review workflows on paper sites
like Academia.edu (which sit behind Cloudflare and often require login).

> **Why a plugin?** Paper sites block fresh/headless sessions and hide full text behind
> login. The reliable path is to talk to *your* real browser. This plugin bundles the exact,
> battle-tested toolchain: search → download PDFs → extract text → classify by topic →
> sort into folders → build a (Persian) literature-review Excel table.

---

## What it does

| Phase | Action | Script |
|-------|--------|--------|
| 0 | Start Chrome with CDP (login preserved) | `scripts/start-chrome-cdp.bat` |
| 1 | Search the paper site (short phrases, rate-limited) | `scripts/run-search.ps1` |
| 2 | Download PDFs (click real button, not `fetch`) | `scripts/download-pdf3.mjs`, `scripts/batch-download.ps1` |
| 3 | Extract text → classify against topic/keywords | `scripts/extract_all.py`, `scripts/sort-papers.ps1` |
| 4 | Build literature-review Excel table | `scripts/build_*.py` |

**Core guarantee: nothing is ever deleted — files are only moved.**

## Requirements

- **Windows** (Chrome + PowerShell). Node.js (ships with the DSH runtime).
- **Python** with `pypdf` and `openpyxl`.
- A logged-in Chrome profile for the paper site.

If `pip install` fails to resolve `files.pythonhosted.org` (DNS), use a mirror:
```
pip install pypdf openpyxl -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```

## Install

**PowerShell (Windows):**
```powershell
.\install.ps1
```

**Bash (macOS/Linux / WSL):**
```bash
./install.sh
```

Both copy the plugin into your DSH user skills folder
(`%USERPROFILE%\.agents\skills\academic-paper-harvest` on Windows,
`~/.agents/skills/academic-paper-harvest` elsewhere) and verify the layout.

To **uninstall**, simply delete that skills folder.

## Quick start

1. **Start CDP Chrome** (keep your login): `scripts\start-chrome-cdp.bat`
2. **Get a fresh tab id:** `node scripts\cdp.mjs list-targets` → pick the paper-site page tab.
3. **Search** (short phrases only; pause 35–50s between requests):
   ```powershell
   .\scripts\run-search.ps1 -TabId <TAB> -Query "your short phrase" -WaitSec 15
   ```
4. **Download** candidates (edit the list or pass `-PapersJson`):
   ```powershell
   .\scripts\batch-download.ps1 -TabId <TAB> -TargetDir "C:\papers\downloads" -PapersJson papers.json
   ```
5. **Classify & sort** (no deletions):
   ```powershell
   .\scripts\sort-papers.ps1 -Root "C:\papers" -ClassFile classification.json `
     -FolderRelated "مرتبط" -FolderWeak "کم_ارتباط" -FolderUnrelated "نامرتبط"
   ```
6. **Build the Excel table:**
   ```powershell
   python scripts\extract_full.py "C:\papers\مرتبط" full.jsonl
   python scripts\build_lit_table_v2.py full.jsonl classified.json
   python scripts\build_final_table.py classified.json "C:\papers\مرتبط" curated.json lit_final.json
   python scripts\build_excel_final.py lit_final.json "literature_review.xlsx"
   ```

> **Tip:** In DSH you usually don't run these by hand — just ask in plain language
> (e.g. *"گردآوری مقالات روی موضوع … از آکادمیا"* or *"جدول مرور ادبیات بساز"*).
> The skill triggers automatically and drives the steps for you.

## Configuration

- **Classification topic/keywords** are *yours* — you supply them when you ask (they are the
  ground truth for relevance). The skill classifies by **content**, not filename.
- **Folder names** and the **weak/borderline list** are parameters to `sort-papers.ps1`.
- **`curated.json`** (for the Excel table) is keyed by filename and carries
  `authors, year, title, title_translated, journal, finding`. Fill it per paper; omitting a
  field leaves a "؟" to fill in later.
- **`relevance_map.json`** (optional, next to the related folder) maps each dimension
  (A/B/C/…) to a thesis-section label.

## Files

```
mcp-plugin-academic-paper-harvest/
├── SKILL.md                  # skill instructions (frontmatter + phased workflow)
├── version.json              # name / version / metadata
├── README.md                 # this file
├── install.ps1 / install.sh  # one-command installers
├── LICENSE                   # MIT
├── CHANGELOG.md              # version history
├── references/
│   └── academia-cdp.md       # deep troubleshooting (CDP, Cloudflare, fetch, Word COM, pip)
└── scripts/
    ├── cdp.mjs / cdp-file.mjs          # CDP CLI (list-targets, new-tab, eval, …)
    ├── run-search.ps1                  # search + extract results
    ├── download-pdf3.mjs               # click-download via setDownloadBehavior
    ├── batch-download.ps1              # batch download with 35–50s pauses
    ├── start-chrome-cdp.bat / kill-chrome-cdp.bat
    ├── extract_all.py / extract_full.py / extract_first2.py
    ├── build_lit_table_v2.py           # dimension + method from text
    ├── build_final_table.py            # curated metadata + translated titles + findings
    ├── build_excel_final.py            # 10-column Excel (openpyxl, B Nazanin, filter)
    ├── sort-papers.ps1                 # move into 3 folders (no deletions)
    └── js/                             # page helpers (type-search, extract-results, …)
```

## Troubleshooting

See `references/academia-cdp.md` for the full field notes: tab-id churn, the
`/search?search=` redirect, Cloudflare "Just a moment…", the in-page `fetch` gotcha,
.docx→PDF via Word COM, and the pip mirror.

## License

MIT — see [LICENSE](LICENSE). Free to use, modify, and share.
