#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_translate.py — خط لولهٔ صفحه‌به‌صفحه: اسکرین‌شات + استخراج متن + ترجمهٔ فارسی

برای هر صفحه از PDF:
  ۱) استخراج متن انگلیسی همان صفحه
  ۲) رندر اسکرین‌شات همان صفحه و ذخیره روی هارد (PNG)
  ۳) ساخت سند Word (و در صورت تمایل PDF) که برای هر صفحهٔ مبدأ سه صفحه دارد:
       صفحه A: اسکرین‌شات صفحه
       صفحه B: متن انگلیسی استخراج‌شده
       صفحه C: ترجمهٔ فارسی دقیق
  هر صفحه که تمام شد، همان لحظه ذخیره می‌شود و در فایل وضعیت (state.json) ثبت
  می‌گردد؛ پس با اجرای مجدد، صفحات انجام‌شده دوباره پردازش نمی‌شوند.

مترجم: qwen38-nothinking روی https://ai.ismc.ir/api  (سازگار با OpenAI Chat Completions)
"""
import argparse, base64, hashlib, json, os, re, sys, time
from datetime import datetime

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF لازم است:  pip install PyMuPDF")

try:
    import requests
except ImportError:
    sys.exit("requests لازم است:  pip install requests")


# ---------------------------------------------------------------- تنظیمات پیش‌فرض
DEFAULT_BASE_URL   = os.environ.get("ISMC_BASE_URL", "https://ai.ismc.ir/api/v1")
DEFAULT_MODEL      = os.environ.get("ISMC_MODEL", "qwen38-nothinking")
DEFAULT_KEY        = os.environ.get("ISMC_API_KEY", "")     # کلید باید با sk- شروع شود
DEFAULT_WORKDIR    = os.environ.get("PDFT_WORKDIR", "./pdf_translate_out")
RENDER_DPI         = int(os.environ.get("PDFT_DPI", "150"))
A4_W_IN, A4_H_IN   = 8.27, 11.69
MARGIN_IN          = 0.45

SYSTEM_PROMPT = (
    "You are a precise professional translator. Translate the user's English text into "
    "fluent, natural, academic Persian (فارسی). Rules:\n"
    "1) Output ONLY the Persian translation — no notes, no explanations, no English.\n"
    "2) Preserve the paragraph structure and line breaks of the source.\n"
    "3) Keep numbers, formulas, URLs, code, and citation markers exactly as they are.\n"
    "4) For technical terms, use the standard Persian equivalent and put the original "
    "English term in parentheses the first time it appears, e.g. «شبکهٔ اجتماعی (social network)».\n"
    "5) Never summarize, never omit, never add content."
)


# ---------------------------------------------------------------- وضعیت / State
class State:
    def __init__(self, path):
        self.path = path
        self.data = {"pdf": None, "sha1": None, "pages": {}, "docx_order": [],
                     "created": datetime.now().isoformat(timespec="seconds")}
        if os.path.exists(path):
            try:
                self.data.update(json.load(open(path, encoding="utf-8")))
            except Exception:
                pass

    def save(self):
        tmp = self.path + ".tmp"
        json.dump(self.data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def is_done(self, p):
        return str(p) in self.data["pages"]

    def mark(self, p, rec):
        self.data["pages"][str(p)] = rec
        if p not in self.data["docx_order"]:
            self.data["docx_order"].append(p)
            self.data["docx_order"].sort()
        self.save()

    @property
    def done_pages(self):
        return sorted(int(k) for k in self.data["pages"])


# ---------------------------------------------------------------- مترجم
class Translator:
    def __init__(self, base_url, model, key, mock=False, timeout=180, retries=4):
        self.base_url, self.model, self.key = base_url.rstrip("/"), model, key
        self.mock, self.timeout, self.retries = mock, timeout, retries
        self.calls = 0

    def _one(self, text, target="Persian"):
        self.calls += 1
        if self.mock:
            time.sleep(0.05)
            return "«ترجمهٔ آزمایشی (mock) — مدل: %s»\n%s" % (self.model, text[:400])
        url = self.base_url + "/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        }
        headers = {"Content-Type": "application/json", "x-litellm-api-key": self.key}
        last = None
        for attempt in range(self.retries):
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                if r.status_code == 200:
                    j = r.json()
                    return j["choices"][0]["message"]["content"].strip()
                last = "HTTP %s: %s" % (r.status_code, r.text[:300])
                if r.status_code in (400, 401, 403, 404):
                    break
            except Exception as e:
                last = repr(e)[:300]
            time.sleep(2 * (attempt + 1))
        raise RuntimeError("ترجمه ناموفق: %s" % last)

    def translate(self, text, chunk_chars=5000):
        text = (text or "").strip()
        if not text:
            return ""
        if len(text) <= chunk_chars:
            return self._one(text)
        # تقسیم روی مرز پاراگراف/جمله برای حفظ انسجام
        parts, cur = [], ""
        for para in re.split(r"(\n\s*\n)", text):
            if len(cur) + len(para) > chunk_chars and cur.strip():
                parts.append(cur); cur = ""
            if len(para) > chunk_chars:
                for sent in re.split(r"(?<=[.!?])\s+", para):
                    if len(cur) + len(sent) > chunk_chars and cur.strip():
                        parts.append(cur); cur = ""
                    cur += sent + " "
            else:
                cur += para
        if cur.strip():
            parts.append(cur)
        out = []
        for i, p in enumerate(parts, 1):
            out.append(self._one(p))
        return "\n\n".join(out)


# ---------------------------------------------------------------- رندر / متن
def pdf_sha1(path, buf=1 << 20):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def render_page(page, png_path, dpi=RENDER_DPI):
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    pix.save(png_path)
    return pix.width, pix.height


def extract_text(page):
    t = page.get_text("text") or ""
    t = t.replace("\u00ad", "")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# ---------------------------------------------------------------- Word builder
def _set_rtl(par):
    """راست‌به‌چپ کردن پاراگراف در Word."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    pPr = par._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi"); pPr.append(bidi)
    par.alignment = 2  # right


def build_docx(state, docx_path, build_pdf=False):
    """سند Word را از روی حافظهٔ نهان بازسازی می‌کند: ۳ صفحه به‌ازای هر صفحهٔ مبدأ."""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_BREAK, WD_ALIGN_PARAGRAPH

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(A4_W_IN), Inches(A4_H_IN)
    for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, m, Inches(MARGIN_IN))
    avail_w = A4_W_IN - 2 * MARGIN_IN
    avail_h = A4_H_IN - 2 * MARGIN_IN

    st = doc.styles["Normal"]
    st.font.name = "Vazir"
    st.font.size = Pt(10.5)
    try:
        from docx.oxml.ns import qn
        st.element.rPr.rFonts.set(qn("w:eastAsia"), "Vazir")
        st.element.rPr.rFonts.set(qn("w:cs"), "Vazir")
    except Exception:
        pass

    order = state.data.get("docx_order") or state.done_pages
    order = [int(p) for p in order]

    def new_page():
        """پاراگراف سرصفحه‌ای که خودش صفحه را می‌شکند (بدون پاراگراف خالی اضافه)."""
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.page_break_before = True
        p.paragraph_format.space_after = Pt(4)
        return p

    first = True
    for p in order:
        rec = state.data["pages"][str(p)]
        # ---------------- صفحه A : اسکرین‌شات
        if first:
            h = doc.add_paragraph(); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
            first = False
        else:
            h = new_page()
        r = h.add_run("صفحهٔ %d — اسکرین‌شات" % p); r.bold = True; r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        png = rec["png"]
        iw, ih = rec.get("w", 1), rec.get("h", 1)
        scale = min(avail_w / iw, (avail_h - 1.0) / ih)
        pic = doc.add_paragraph(); pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pic.paragraph_format.space_after = Pt(0)
        pic.paragraph_format.space_before = Pt(0)
        pic.add_run().add_picture(png, width=Inches(iw * scale))

        # ---------------- صفحه B : متن انگلیسی
        h = new_page()
        r = h.add_run("Page %d — Extracted English text" % p); r.bold = True; r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        t = rec.get("text") or ""
        if not t:
            doc.add_paragraph("[No extractable text on this page — likely a scanned image.]")
        for para in t.split("\n"):
            pp = doc.add_paragraph(para)
            pp.paragraph_format.space_after = Pt(2)
            for run in pp.runs:
                run.font.name = "DejaVu Sans"; run.font.size = Pt(9.5)

        # ---------------- صفحه C : ترجمهٔ فارسی
        h = new_page()
        r = h.add_run("صفحهٔ %d — ترجمهٔ فارسی" % p); r.bold = True; r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        fa = rec.get("fa") or ""
        if not fa:
            fa = "[متن قابل استخراجی در این صفحه نبود — احتمالاً صفحه تصویری/اسکن‌شده است.]"
        for para in fa.split("\n"):
            pp = doc.add_paragraph(para)
            pp.paragraph_format.space_after = Pt(3)
            _set_rtl(pp)

    doc.save(docx_path)

    if build_pdf:
        pdf_out = os.path.splitext(docx_path)[0] + ".pdf"
        try:
            import subprocess, tempfile
            prof = tempfile.mkdtemp(prefix="lo_prof_")
            subprocess.run(["soffice", "-env:UserInstallation=file://%s" % prof,
                            "--headless", "--norestore", "--convert-to", "pdf",
                            "--outdir", os.path.dirname(os.path.abspath(docx_path)),
                            os.path.abspath(docx_path)],
                           check=True, timeout=900,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(pdf_out):
                return pdf_out
        except Exception as e:
            print("  ! تبدیل به PDF ناموفق بود:", e)
    return None


# ---------------------------------------------------------------- هستهٔ پردازش
def run(pdf_path, workdir=DEFAULT_WORKDIR, base_url=DEFAULT_BASE_URL, model=DEFAULT_MODEL,
        key=DEFAULT_KEY, start=1, end=None, mock=False, dpi=RENDER_DPI,
        rebuild=False, make_pdf=False, log=print, should_stop=None):

    pdf_path = os.path.abspath(pdf_path)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)
    os.makedirs(workdir, exist_ok=True)
    shots = os.path.join(workdir, "screenshots"); os.makedirs(shots, exist_ok=True)
    texts = os.path.join(workdir, "texts");       os.makedirs(texts, exist_ok=True)
    state_path = os.path.join(workdir, "state.json")
    docx_path  = os.path.join(workdir, os.path.splitext(os.path.basename(pdf_path))[0] + "_fa.docx")

    sha = pdf_sha1(pdf_path)

    # --- اگر state متعلق به فایل دیگری است، در جای جدید بگذار
    if os.path.exists(state_path):
        try:
            old = json.load(open(state_path, encoding="utf-8"))
            if old.get("sha1") and old["sha1"] != sha:
                state_path = os.path.join(workdir, "state_%s.json" % sha[:8])
                docx_path = docx_path.replace("_fa.docx", "_fa_%s.docx" % sha[:8])
                log("⚠ فایل وضعیت قبلی مربوط به PDF دیگری بود؛ فایل وضعیت جدید: %s" % state_path)
        except Exception:
            pass

    st = State(state_path)
    st.data["pdf"], st.data["sha1"] = pdf_path, sha
    st.save()

    doc = fitz.open(pdf_path)
    n = doc.page_count
    end = end or n
    start = max(1, start); end = min(n, end)

    log("=" * 72)
    log("PDF      : %s" % pdf_path)
    log("صفحات    : %d   |   بازهٔ این اجرا: %d تا %d" % (n, start, end))
    log("PROGRESS total=%d done=%d" % (end - start + 1, 0))
    log("خروجی    : %s" % workdir)
    log("مدل      : %s  (%s)" % (model, "MOCK/آزمایشی" if mock else base_url))
    log("از قبل انجام‌شده: %d صفحه %s" % (len(st.done_pages), st.done_pages[:20]))
    log("=" * 72)

    tr = Translator(base_url, model, key, mock=mock)
    todo = [p for p in range(start, end + 1) if not st.is_done(p)]
    if not todo:
        log("✅ همهٔ صفحات این بازه قبلاً انجام شده‌اند. هیچ کار تکراری‌ای انجام نشد.")
    done_now = 0
    for p in todo:
        if should_stop is not None and should_stop():
            log("\n⏹ درخواست توقف. تا همین‌جا ذخیره شد؛ اجرای بعدی از صفحهٔ %d ادامه می‌دهد." % p)
            break
        page = doc.load_page(p - 1)
        png = os.path.join(shots, "page_%04d.png" % p)
        txt = os.path.join(texts, "page_%04d.txt" % p)
        t0 = time.time()
        try:
            w, h = render_page(page, png, dpi=dpi)
            text = extract_text(page)
            open(txt, "w", encoding="utf-8").write(text)
            fa = tr.translate(text)
            st.mark(p, {"png": png, "text": text, "fa": fa, "w": w, "h": h,
                        "chars": len(text), "at": datetime.now().isoformat(timespec="seconds")})
            done_now += 1
            log("  ✔ صفحه %4d ثبت شد | %5d کاراکتر | %3d کاراکتر فارسی | %.1f ثانیه"
                % (p, len(text), len(fa), time.time() - t0))
            log("PROGRESS total=%d done=%d page=%d" % (end - start + 1, done_now, p))
        except KeyboardInterrupt:
            log("\n⏹ توقف کاربر. تا همین‌جا ذخیره شد؛ اجرای بعدی از صفحهٔ %d ادامه می‌دهد." % p)
            break
        except Exception as e:
            log("  ✘ صفحه %4d خطا: %s  → این صفحه ثبت نشد و در اجرای بعدی تکرار می‌شود." % (p, e))

    doc.close()

    # --- ساخت/بازسازی سند Word از حافظهٔ نهان
    if st.done_pages:
        log("… ساخت سند Word از %d صفحهٔ ثبت‌شده" % len(st.done_pages))
        out_pdf = build_docx(st, docx_path, build_pdf=make_pdf)
        log("📄 Word : %s" % docx_path)
        if out_pdf:
            log("📕 PDF  : %s" % out_pdf)
    log("— این اجرا: %d صفحهٔ جدید | کل ثبت‌شده: %d صفحه" % (done_now, len(st.done_pages)))
    log("DONE docx=%s" % docx_path)
    return {"docx": docx_path, "state": state_path, "done": len(st.done_pages), "new": done_now}


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="اسکرین‌شات + استخراج متن + ترجمهٔ فارسی، صفحه‌به‌صفحه و قابل‌ادامه")
    ap.add_argument("pdf", help="مسیر فایل PDF")
    ap.add_argument("-o", "--workdir", default=DEFAULT_WORKDIR, help="پوشهٔ خروجی")
    ap.add_argument("--key", default=DEFAULT_KEY, help="کلید API (با sk- شروع می‌شود)")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--dpi", type=int, default=RENDER_DPI)
    ap.add_argument("--mock", action="store_true", help="بدون تماس با API (تست ساختار)")
    ap.add_argument("--make-pdf", action="store_true", help="خروجی PDF هم بساز (نیازمند libreoffice)")
    ap.add_argument("--rebuild", action="store_true", help="سند Word را از حافظهٔ نهان دوباره بساز")
    a = ap.parse_args()
    if a.rebuild:
        st = State(os.path.join(a.workdir, "state.json"))
        print(build_docx(st, os.path.join(a.workdir, "rebuild.docx"), build_pdf=a.make_pdf))
        return
    run(a.pdf, a.workdir, a.base_url, a.model, a.key, a.start, a.end,
        a.mock, a.dpi, a.rebuild, a.make_pdf)


if __name__ == "__main__":
    main()
