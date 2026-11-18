# Changelog

All notable changes to **academic-paper-harvest** are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/) and the
project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-27

### Added
- Initial professional, shareable package.
- **Skill** (`SKILL.md`): five-phase workflow — prerequisites, search, download,
  classify & sort, literature-review table — with a "no deletion" guarantee.
- **CDP toolchain** (`scripts/`): `cdp.mjs`, `cdp-file.mjs`, `run-search.ps1`,
  `download-pdf3.mjs`, `batch-download.ps1`, `start/kill-chrome-cdp.bat`,
  page helpers in `scripts/js/`.
- **Text extraction** (`scripts/`): `extract_all.py` (4 pages), `extract_full.py`
  (8 pages), `extract_first2.py` (2 pages) → JSONL.
- **Table builders** (`scripts/`): `build_lit_table_v2.py` (dimension + method),
  `build_final_table.py` (curated metadata, translated titles, one-sentence
  findings), `build_excel_final.py` (10-column Excel, B Nazanin, freeze + filter).
- **Sorting** (`scripts/sort-papers.ps1`): moves files into related / weak /
  unrelated folders; handles name collisions; never deletes.
- **Reference** (`references/academia-cdp.md`): field troubleshooting notes
  (tab-id churn, search redirect, Cloudflare rate limits, the `fetch` gotcha,
  .docx→PDF via Word COM, pip mirror).
- **Packaging**: `README.md`, `install.ps1` + `install.sh`, `LICENSE` (MIT),
  `version.json` (v1.0.0).

### Notes
- All scripts are **relocatable** (they resolve paths from their own location) and
  **parameterized** — no project-specific paths or topics are hardcoded.
- Designed for DeepSeek Harness (DSH) user-level skills; also compatible with the
  standard `SKILL.md` frontmatter convention.

[1.0.0]: https://example.invalid/mcp-plugin-academic-paper-harvest/compare/v1.0.0
