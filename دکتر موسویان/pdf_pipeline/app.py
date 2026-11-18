#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — «رابط هوشمند» محلی برای خط لولهٔ ترجمهٔ PDF (بدون هیچ وابستگی اضافه)

اجرا:
    python3 app.py                 # روی http://127.0.0.1:8765
    python3 app.py --port 9000 --host 0.0.0.0

قابلیت‌ها:
  • انتخاب PDF از روی دیسک (فهرست خودکار) یا آپلود فایل از مرورگر
  • نمایش تعداد صفحات و حجم فایل قبل از شروع
  • شروع / توقف پردازش با نمایش زندهٔ لاگ (Server-Sent Events)
  • نمایش درصد پیشرفت و شمارش صفحات انجام‌شده
  • فهرست «کارهای قبلی» از روی state.json و امکان ادامهٔ کار نیمه‌تمام
  • دانلود Word و PDF خروجی و مشاهدهٔ اسکرین‌شات صفحات، همه از داخل رابط
"""
import argparse, json, mimetypes, os, re, shutil, threading, time, traceback, uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import pdf_translate as pt

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_OUT = os.environ.get("PDFT_WORKDIR", os.path.join(HERE, "pdf_translate_out"))
UPLOADS = os.path.join(HERE, "uploads")
os.makedirs(UPLOADS, exist_ok=True)

SEARCH_ROOTS = [HERE, "/mnt/data", os.path.expanduser("~/Downloads"),
                os.path.expanduser("~/Documents"), os.path.expanduser("~/Desktop"), "/tmp"]
MAX_DEPTH = 4
MAX_LIST = 400

# ------------------------------------------------------------------ Job manager
class Job:
    def __init__(self, jid, params):
        self.id = jid
        self.params = params
        self.lines = deque(maxlen=4000)
        self.lock = threading.Lock()
        self.stop_flag = False
        self.status = "queued"     # queued | running | done | error | stopped
        self.progress = {"total": 0, "done": 0, "page": 0}
        self.result = None
        self.error = None
        self.started = time.time()
        self.ended = None
        self.thread = threading.Thread(target=self._work, daemon=True)

    def emit(self, msg):
        m = re.match(r"PROGRESS total=(\d+) done=(\d+)(?: page=(\d+))?", str(msg))
        if m:
            self.progress = {"total": int(m.group(1)), "done": int(m.group(2)),
                             "page": int(m.group(3) or 0)}
        with self.lock:
            self.lines.append("%s" % msg)

    def snapshot(self, from_idx=0):
        with self.lock:
            lines = list(self.lines)
        return {
            "id": self.id, "status": self.status, "progress": self.progress,
            "result": self.result, "error": self.error,
            "started": self.started, "ended": self.ended,
            "lines": lines[from_idx:], "n": len(lines),
        }

    def _work(self):
        self.status = "running"
        p = self.params
        try:
            res = pt.run(
                p["pdf"], workdir=p["workdir"], base_url=p["base_url"], model=p["model"],
                key=p["key"], start=p["start"], end=p["end"], mock=p["mock"], dpi=p["dpi"],
                rebuild=False, make_pdf=p["make_pdf"], log=self.emit,
                should_stop=lambda: self.stop_flag,
            )
            self.result = res
            self.status = "stopped" if self.stop_flag else "done"
        except Exception as e:
            self.error = "%s" % e
            self.status = "error"
            self.emit("✘ خطای کلی: %s" % e)
            self.emit(traceback.format_exc()[-2000:])
        finally:
            self.ended = time.time()

    def start(self):
        self.thread.start()


JOBS = {}
JOBS_LOCK = threading.Lock()


# ------------------------------------------------------------------ Helpers
def safe_workdir_name(pdf_path):
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    stem = re.sub(r"[^\w\u0600-\u06FF.\-]+", "_", stem)[:60] or "doc"
    return stem


def list_pdfs():
    out = []
    seen = set()
    for root in SEARCH_ROOTS:
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip("/").count("/")
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(".") and d not in
                           ("node_modules", "__pycache__", "site-packages", "screenshots")]
            if dirpath.count("/") - base_depth >= MAX_DEPTH:
                dirnames[:] = []
            for fn in filenames:
                if fn.lower().endswith(".pdf"):
                    full = os.path.join(dirpath, fn)
                    if full in seen:
                        continue
                    seen.add(full)
                    try:
                        sz = os.path.getsize(full)
                    except OSError:
                        continue
                    out.append({"path": full, "name": fn, "size": sz,
                                "mtime": os.path.getmtime(full)})
                    if len(out) >= MAX_LIST:
                        return sorted(out, key=lambda x: -x["mtime"])
    return sorted(out, key=lambda x: -x["mtime"])


def pdf_info(path):
    import fitz
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    d = fitz.open(path)
    info = {"path": os.path.abspath(path), "pages": d.page_count,
            "size": os.path.getsize(path)}
    try:
        info["title"] = (d.metadata or {}).get("title") or ""
        info["author"] = (d.metadata or {}).get("author") or ""
    except Exception:
        pass
    d.close()
    return info


def scan_tasks():
    """کارهای قبلی را از پوشهٔ خروجی اصلی می‌خواند."""
    tasks = []
    roots = {BASE_OUT, HERE}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            if fn.startswith("state") and fn.endswith(".json"):
                sp = os.path.join(root, fn)
                try:
                    d = json.load(open(sp, encoding="utf-8"))
                except Exception:
                    continue
                pages = sorted(int(k) for k in d.get("pages", {}))
                # تعداد کل صفحات فایل مبدأ
                total = None
                try:
                    if d.get("pdf") and os.path.exists(d["pdf"]):
                        total = pdf_info(d["pdf"])["pages"]
                except Exception:
                    pass
                docx = None
                if d.get("pdf"):
                    base = os.path.splitext(os.path.basename(d["pdf"]))[0]
                    cand = os.path.join(root, base + "_fa.docx")
                    if os.path.exists(cand):
                        docx = cand
                tasks.append({
                    "state": sp, "workdir": root, "pdf": d.get("pdf"),
                    "pdf_exists": bool(d.get("pdf") and os.path.exists(d.get("pdf"))),
                    "done": len(pages), "pages": pages[:12],
                    "total": total, "docx": docx,
                    "created": d.get("created"), "sha1": (d.get("sha1") or "")[:8],
                })
    return tasks


def is_under(path, root):
    p, r = os.path.realpath(path), os.path.realpath(root)
    return p == r or p.startswith(r + os.sep)


# ------------------------------------------------------------------ HTML
PAGE = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ترجمهٔ صفحه‌به‌صفحهٔ PDF — رابط هوشمند</title>
<style>
  :root{--bg:#0f1115;--card:#181c23;--card2:#1f242d;--fg:#e8ecf1;--mut:#9aa4b2;
        --acc:#4f8cff;--ok:#2ecc71;--warn:#f5a623;--err:#ff5c5c;--line:#2a3038}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);
       font-family:Vazirmatn,Vazir,"Segoe UI",Tahoma,sans-serif;line-height:1.8}
  header{padding:18px 22px;border-bottom:1px solid var(--line);
         background:linear-gradient(90deg,#12161c,#1b2230)}
  header h1{margin:0;font-size:19px}
  header p{margin:4px 0 0;color:var(--mut);font-size:13px}
  .wrap{max-width:1100px;margin:0 auto;padding:18px 16px 60px;display:grid;
        grid-template-columns:1fr 1fr;gap:16px}
  @media(max-width:900px){.wrap{grid-template-columns:1fr}}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
  .card h2{margin:0 0 12px;font-size:15px;color:#cfd8e3;
           border-bottom:1px solid var(--line);padding-bottom:8px}
  label{display:block;font-size:12.5px;color:var(--mut);margin:10px 0 4px}
  input[type=text],input[type=password],input[type=number],select,textarea{
      width:100%;background:var(--card2);border:1px solid var(--line);color:var(--fg);
      border-radius:9px;padding:9px 11px;font-family:inherit;font-size:13.5px;direction:ltr}
  textarea{min-height:78px;resize:vertical}
  .row{display:flex;gap:10px}
  .row>*{flex:1}
  button{cursor:pointer;font-family:inherit;font-size:14px;border:0;border-radius:10px;
         padding:11px 16px;font-weight:600;transition:.15s}
  .primary{background:var(--acc);color:#fff}
  .primary:hover{background:#3b78e8}
  .danger{background:#3a2027;color:#ff9c9c;border:1px solid #5c2b33}
  .ghost{background:var(--card2);color:var(--fg);border:1px solid var(--line)}
  button:disabled{opacity:.45;cursor:not-allowed}
  .bar{height:9px;background:#0b0e12;border-radius:99px;overflow:hidden;border:1px solid var(--line)}
  .bar>i{display:block;height:100%;width:0;background:linear-gradient(90deg,#2ecc71,#4f8cff);
         transition:width .3s}
  #log{background:#0a0d11;border:1px solid var(--line);border-radius:10px;padding:10px;
       height:330px;overflow:auto;font-family:ui-monospace,Menlo,Consolas,monospace;
       font-size:12px;direction:ltr;text-align:left;white-space:pre-wrap}
  .pill{display:inline-block;font-size:11.5px;padding:2px 9px;border-radius:99px;
        border:1px solid var(--line);color:var(--mut)}
  .pill.ok{color:#b6f2cd;border-color:#245c39;background:#12291c}
  .pill.run{color:#cfe0ff;border-color:#2b4a86;background:#131f36}
  .pill.err{color:#ffc9c9;border-color:#5c2b33;background:#2a1418}
  .task{display:flex;justify-content:space-between;align-items:center;gap:8px;
        padding:9px 10px;border:1px solid var(--line);border-radius:10px;margin-bottom:8px;
        background:var(--card2);font-size:13px}
  .task small{color:var(--mut);direction:ltr;display:block;font-size:11px}
  a{color:var(--acc);text-decoration:none}
  a:hover{text-decoration:underline}
  .hint{font-size:11.5px;color:var(--mut);margin-top:6px}
  .file-list{max-height:170px;overflow:auto;border:1px solid var(--line);border-radius:10px}
  .file-list div{padding:7px 10px;border-bottom:1px solid #222831;cursor:pointer;font-size:12.5px}
  .file-list div:hover{background:#222831}
  .file-list small{color:var(--mut);direction:ltr}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
</style>
</head>
<body>
<header>
  <h1>📚 ترجمهٔ صفحه‌به‌صفحهٔ PDF — اسکرین‌شات + متن انگلیسی + ترجمهٔ فارسی</h1>
  <p>هر صفحهٔ مبدأ ⇒ سه صفحهٔ خروجی (A: تصویر، B: انگلیسی، C: فارسی) — ذخیرهٔ فوری هر صفحه و ادامهٔ کار پس از قطع</p>
</header>

<div class="wrap">
  <!-- ------------------------------ تنظیمات ------------------------------ -->
  <div class="card">
    <h2>۱) انتخاب فایل و تنظیمات</h2>

    <label>آپلود PDF از این دستگاه</label>
    <input type="file" id="file" accept="application/pdf">

    <label>یا مسیر فایل روی دیسک</label>
    <input type="text" id="pdfpath" placeholder="/mnt/data/book.pdf">
    <div class="hint">با کلیک روی «فهرست فایل‌ها» یا خودکار بارگذاری می‌شود.</div>
    <div class="row" style="margin-top:8px">
      <button class="ghost" onclick="loadFiles()">🔄 فهرست فایل‌های PDF</button>
      <button class="ghost" onclick="loadInfo()">ℹ️ تعداد صفحات</button>
    </div>
    <div class="file-list" id="files" style="margin-top:8px"></div>
    <div class="hint" id="info"></div>

    <label>کلید API (باید با sk- شروع شود)</label>
    <input type="password" id="key" placeholder="sk-...">
    <div class="hint">کلید معتبر را از <span style="direction:ltr;display:inline-block">https://ai.ismc.ir/ui</span> → Keys بسازید و در فایل <code>.env</code> هم می‌توانید بگذارید.</div>

    <label>مدل</label>
    <select id="model">
      <option value="qwen38-nothinking" selected>qwen38-nothinking (بدون استدلال — دقیق‌ترین برای ترجمه)</option>
      <option value="qwen38">qwen38</option>
      <option value="qwen38-sglang">qwen38-sglang (توان عبوری بیشتر)</option>
    </select>

    <label>آدرس سرویس</label>
    <input type="text" id="base_url" value="https://ai.ismc.ir/api/v1">

    <div class="grid2" style="margin-top:6px">
      <div><label>از صفحه</label><input type="number" id="start" value="1" min="1"></div>
      <div><label>تا صفحه (خالی = آخرین صفحه)</label><input type="number" id="end" placeholder=""></div>
    </div>
    <div class="grid2">
      <div><label>کیفیت اسکرین‌شات (DPI)</label><input type="number" id="dpi" value="150" min="72" max="400"></div>
      <div><label>خروجی PDF هم بساز؟</label>
        <select id="make_pdf"><option value="0">نه (فقط Word)</option><option value="1">بله (کندتر)</option></select>
      </div>
    </div>
    <label style="display:flex;gap:8px;align-items:center;margin-top:10px">
      <input type="checkbox" id="mock" style="width:auto"> حالت آزمایشی (بدون تماس با API — تست ساختار)
    </label>

    <div class="row" style="margin-top:14px">
      <button class="primary" id="btnStart" onclick="start()">▶️ شروع پردازش</button>
      <button class="danger" id="btnStop" onclick="stop()" disabled>⏹ توقف</button>
    </div>
  </div>

  <!-- ------------------------------ پیشرفت ------------------------------ -->
  <div class="card">
    <h2>۲) پیشرفت زنده</h2>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span class="pill" id="status">آماده</span>
      <span class="pill" id="pctxt">۰٪</span>
    </div>
    <div class="bar" style="margin:10px 0 12px"><i id="bar"></i></div>
    <div id="log">—</div>
    <div id="out" style="margin-top:12px"></div>
  </div>

  <!-- ------------------------------ کارهای قبلی ------------------------------ -->
  <div class="card" style="grid-column:1/-1">
    <h2>۳) کارهای قبلی — ادامه یا دانلود خروجی</h2>
    <div id="tasks"><span class="hint">در حال خواندن…</span></div>
  </div>
</div>

<script>
let JOB=null, SRC=null, LASTN=0;

function esc(s){return (s+"").replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function fa(n){return (n+"").replace(/\d/g,d=>"۰۱۲۳۴۵۶۷۸۹"[d])}

async function loadFiles(){
  const box=document.getElementById('files'); box.textContent='در حال جست‌وجو…';
  const r=await fetch('/api/files'); const j=await r.json();
  if(!j.files.length){box.textContent='فایل PDF پیدا نشد؛ مسیر را دستی وارد کنید یا آپلود کنید.';return}
  box.innerHTML=j.files.map(f=>`<div onclick="pick('${f.path.replace(/\\/g,'\\\\').replace(/'/g,"\\'")}')">
     ${esc(f.name)} <small>${(f.size/1048576).toFixed(1)} MB</small></div>`).join('');
}
function pick(p){document.getElementById('pdfpath').value=p; loadInfo();}

async function loadInfo(){
  const p=document.getElementById('pdfpath').value.trim(); if(!p)return;
  document.getElementById('info').textContent='…';
  try{
    const r=await fetch('/api/pdfinfo?path='+encodeURIComponent(p)); const j=await r.json();
    if(j.error){document.getElementById('info').textContent='⚠ '+j.error;return}
    document.getElementById('info').innerHTML=
      `✅ ${fa(j.pages)} صفحه — ${(j.size/1048576).toFixed(1)} مگابایت`+
      (j.title?` — «${esc(j.title)}»`:'');
    document.getElementById('end').placeholder=fa(j.pages);
  }catch(e){document.getElementById('info').textContent='⚠ خطا در خواندن فایل';}
}

document.getElementById('file').addEventListener('change',async ev=>{
  const f=ev.target.files[0]; if(!f)return;
  document.getElementById('info').textContent='در حال آپلود…';
  const r=await fetch('/api/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(f.name)},body:f});
  const j=await r.json();
  if(j.error){document.getElementById('info').textContent='⚠ '+j.error;return}
  document.getElementById('pdfpath').value=j.path; loadInfo();
});

async function start(){
  const p={
    pdf:document.getElementById('pdfpath').value.trim(),
    key:document.getElementById('key').value.trim(),
    model:document.getElementById('model').value,
    base_url:document.getElementById('base_url').value.trim(),
    start:+document.getElementById('start').value||1,
    end:document.getElementById('end').value?+document.getElementById('end').value:null,
    dpi:+document.getElementById('dpi').value||150,
    make_pdf:document.getElementById('make_pdf').value==='1',
    mock:document.getElementById('mock').checked
  };
  if(!p.pdf){alert('مسیر PDF را مشخص کنید');return}
  document.getElementById('log').textContent=''; LASTN=0;
  document.getElementById('out').innerHTML=''; setStatus('run','در حال اجرا…');
  const r=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
  const j=await r.json();
  if(j.error){alert(j.error);setStatus('err','خطا');return}
  JOB=j.id;
  document.getElementById('btnStart').disabled=true;
  document.getElementById('btnStop').disabled=false;
  const es=new EventSource('/api/stream?job='+JOB);
  SRC=es;
  es.onmessage=ev=>{
    const s=JSON.parse(ev.data);
    if(s.lines&&s.lines.length){
      const L=document.getElementById('log');
      L.textContent+= (L.textContent?'\n':'')+s.lines.join('\n');
      L.scrollTop=L.scrollHeight;
    }
    if(s.progress&&s.progress.total){
      const d=s.progress.done,t=s.progress.total;
      const pct=Math.round(d*100/t);
      document.getElementById('bar').style.width=pct+'%';
      document.getElementById('pctxt').textContent=fa(pct)+'٪  ('+fa(d)+'/'+fa(t)+')';
    }
    if(s.status!=='running'&&s.status!=='queued'){
      es.close(); SRC=null; done(s);
    }
  };
  es.onerror=()=>{/* EventSource خودش تلاش مجدد می‌کند */};
}

function done(s){
  document.getElementById('btnStart').disabled=false;
  document.getElementById('btnStop').disabled=true;
  if(s.status==='done'){setStatus('ok','تمام شد ✅');document.getElementById('bar').style.width='100%';}
  else if(s.status==='stopped'){setStatus('','متوقف شد — با «شروع» ادامه دهید');}
  else {setStatus('err','خطا');}
  if(s.result){
    const d=s.result;
    const pdfp=d.docx.replace(/\.docx$/,'.pdf');
    document.getElementById('out').innerHTML=
      `<div class="task"><div><b>خروجی آماده است</b>
        <small>${esc(d.docx)}</small>
        <small>صفحات ثبت‌شده: ${fa(d.done)} | جدید: ${fa(d.new)}</small></div>
        <div style="text-align:left">
          <a href="/api/download?path=${encodeURIComponent(d.docx)}">⬇️ Word</a> &nbsp;
          <a href="/api/download?path=${encodeURIComponent(pdfp)}">⬇️ PDF</a>
        </div></div>
        <div class="hint">پوشهٔ خروجی: <span style="direction:ltr;display:inline-block">${esc(s.result.state||'')}</span></div>`;
  }
  if(s.error)document.getElementById('log').textContent+='\n'+s.error;
  loadTasks();
}
function setStatus(cls,txt){
  const e=document.getElementById('status');
  e.className='pill '+(cls||''); e.textContent=txt;
}

async function stop(){ if(JOB){await fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job:JOB})});} }

async function loadTasks(){
  const r=await fetch('/api/tasks'); const j=await r.json();
  const box=document.getElementById('tasks');
  if(!j.tasks.length){box.innerHTML='<span class="hint">کار قبلی‌ای پیدا نشد.</span>';return}
  box.innerHTML=j.tasks.map((t,i)=>`
    <div class="task">
      <div>
        <b>${esc((t.pdf||'?').split('/').pop())}</b>
        <small>${esc(t.pdf||'')}</small>
        <small>انجام‌شده: ${fa(t.done)}${t.total?(' از '+fa(t.total)):''} صفحه — sha: ${esc(t.sha1)}</small>
      </div>
      <div style="text-align:left;min-width:210px">
        ${t.docx?`<a href="/api/download?path=${encodeURIComponent(t.docx)}">⬇️ Word</a> &nbsp;`:''}
        ${t.pdf_exists?`<button class="ghost" onclick="resume('${esc(t.pdf).replace(/\\/g,'\\\\').replace(/'/g,"\\'")}')">▶️ ادامه</button>`:''}
      </div>
    </div>`).join('');
}
function resume(p){document.getElementById('pdfpath').value=p;loadInfo();start();}

loadFiles(); loadTasks();
</script>
</body>
</html>
"""


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "PDFTranslateUI/1.0"

    def log_message(self, fmt, *a):
        pass  # ساکت

    # ---------- utils
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code=200):
        self._send(code, obj)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _q(self):
        return parse_qs(urlparse(self.path).query)

    # ---------- GET
    def do_GET(self):
        path = urlparse(self.path).path
        q = self._q()
        try:
            if path in ("/", "/index.html"):
                return self._send(200, PAGE, "text/html; charset=utf-8")

            if path == "/api/files":
                return self._json({"files": list_pdfs()})

            if path == "/api/pdfinfo":
                p = unquote((q.get("path") or [""])[0])
                try:
                    return self._json(pdf_info(p))
                except Exception as e:
                    return self._json({"error": "%s" % e})

            if path == "/api/tasks":
                return self._json({"tasks": scan_tasks()})

            if path == "/api/stream":
                jid = (q.get("job") or [""])[0]
                job = JOBS.get(jid)
                if not job:
                    return self._json({"error": "job not found"}, 404)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                idx = 0
                while True:
                    snap = job.snapshot(idx)
                    idx = snap.pop("n")
                    try:
                        self.wfile.write(("data: " + json.dumps(snap, ensure_ascii=False) + "\n\n").encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    if job.status not in ("running", "queued") and not snap["lines"]:
                        return
                    time.sleep(0.4)
                return

            if path == "/api/download":
                p = unquote((q.get("path") or [""])[0])
                if not p or not any(is_under(p, a) for a in (BASE_OUT, HERE)):
                    return self._json({"error": "مسیر مجاز نیست"}, 403)
                if not os.path.isfile(p):
                    return self._json({"error": "فایل نیست"}, 404)
                ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
                if p.lower().endswith((".docx",)):
                    ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                data = open(p, "rb").read()
                fn = os.path.basename(p)
                return self._send(200, data, ctype,
                                  {"Content-Disposition": 'attachment; filename="%s"' % fn})

            if path == "/api/raw":
                # مشاهدهٔ درون‌مرورگری (تصویر/PDF)
                p = unquote((q.get("path") or [""])[0])
                if not p or not any(is_under(p, a) for a in (BASE_OUT, HERE)):
                    return self._json({"error": "مسیر مجاز نیست"}, 403)
                if not os.path.isfile(p):
                    return self._json({"error": "فایل نیست"}, 404)
                ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
                return self._send(200, open(p, "rb").read(), ctype)

            return self._json({"error": "not found"}, 404)
        except Exception as e:
            traceback.print_exc()
            return self._json({"error": "%s" % e}, 500)

    # ---------- POST
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/upload":
                raw = self._body()
                name = unquote(self.headers.get("X-Filename") or "upload.pdf")
                name = os.path.basename(name) or "upload.pdf"
                if not name.lower().endswith(".pdf"):
                    return self._json({"error": "فقط فایل PDF"}, 400)
                dest = os.path.join(UPLOADS, name)
                if os.path.exists(dest):
                    stem, ext = os.path.splitext(name)
                    dest = os.path.join(UPLOADS, "%s_%s%s" % (stem, uuid.uuid4().hex[:6], ext))
                open(dest, "wb").write(raw)
                return self._json({"path": dest, "size": len(raw)})

            if path == "/api/start":
                p = json.loads(self._body() or b"{}")
                pdf = (p.get("pdf") or "").strip()
                if not os.path.isfile(pdf):
                    return self._json({"error": "فایل PDF پیدا نشد: %s" % pdf}, 400)
                mock = bool(p.get("mock"))
                key = (p.get("key") or pt.DEFAULT_KEY or "").strip()
                if not mock and not key:
                    return self._json({"error": "کلید API لازم است (یا حالت آزمایشی را بزنید)"}, 400)

                workdir = os.path.join(BASE_OUT, safe_workdir_name(pdf))
                os.makedirs(workdir, exist_ok=True)
                params = {
                    "pdf": os.path.abspath(pdf),
                    "workdir": workdir,
                    "key": key,
                    "model": p.get("model") or pt.DEFAULT_MODEL,
                    "base_url": p.get("base_url") or pt.DEFAULT_BASE_URL,
                    "start": int(p.get("start") or 1),
                    "end": int(p["end"]) if p.get("end") else None,
                    "dpi": int(p.get("dpi") or pt.RENDER_DPI),
                    "make_pdf": bool(p.get("make_pdf")),
                    "mock": mock,
                }
                jid = uuid.uuid4().hex[:12]
                job = Job(jid, params)
                with JOBS_LOCK:
                    JOBS[jid] = job
                job.start()
                return self._json({"id": jid, "workdir": workdir})

            if path == "/api/stop":
                p = json.loads(self._body() or b"{}")
                job = JOBS.get(p.get("job"))
                if job:
                    job.stop_flag = True
                    return self._json({"ok": True})
                return self._json({"error": "job not found"}, 404)

            return self._json({"error": "not found"}, 404)
        except Exception as e:
            traceback.print_exc()
            return self._json({"error": "%s" % e}, 500)


def main():
    ap = argparse.ArgumentParser(description="رابط هوشمند ترجمهٔ PDF")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    os.makedirs(BASE_OUT, exist_ok=True)
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print("=" * 68)
    print("  رابط هوشمند ترجمهٔ PDF آماده است:")
    print("     http://%s:%d" % ("127.0.0.1" if a.host in ("0.0.0.0", "") else a.host, a.port))
    print("  پوشهٔ خروجی: %s" % os.path.abspath(BASE_OUT))
    print("  برای توقف: Ctrl+C")
    print("=" * 68)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nخاموش شد.")


if __name__ == "__main__":
    main()
