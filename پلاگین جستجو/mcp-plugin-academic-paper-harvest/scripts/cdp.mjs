#!/usr/bin/env node
// Minimal CDP client for driving the user's Chrome on port 9222.
// Usage:
//   node cdp.mjs list-targets
//   node cdp.mjs new-tab <url>
//   node cdp.mjs get-url <tabId>
//   node cdp.mjs set-url <tabId> <url>
//   node cdp.mjs eval <tabId> <jsExpression>
//   node cdp.mjs close-tab <tabId>
//   node cdp.mjs wait-load <tabId> [timeoutMs]

import { readFileSync } from 'node:fs';

const CDP_HTTP = 'http://127.0.0.1:9222';

async function httpJson(path) {
  const r = await fetch(CDP_HTTP + path);
  if (!r.ok) throw new Error(`CDP HTTP ${r.status} for ${path}`);
  return r.json();
}

function wsUrlForTarget(target) {
  return target.webSocketDebuggerUrl || (target.devtoolsFrontendUrl && target.devtoolsFrontendUrl.includes('devtools/') ? target.devtoolsFrontendUrl : null);
}

class CdpSession {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.id = 1;
    this.pending = new Map();
    this.listeners = new Map();
    this.ws = null;
  }
  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.addEventListener('open', () => resolve(), { once: true });
      this.ws.addEventListener('error', (e) => reject(new Error('ws error')), { once: true });
      this.ws.addEventListener('message', (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }
        if (msg.id !== undefined && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) reject(new Error(msg.error.message));
          else resolve(msg.result);
        } else if (msg.method) {
          const fns = this.listeners.get(msg.method) || [];
          for (const fn of fns) fn(msg.params);
        }
      });
    });
  }
  send(method, params = {}) {
    const id = this.id++;
    const payload = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(payload);
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP timeout on ${method}`));
        }
      }, 60000);
    });
  }
  on(method, fn) {
    if (!this.listeners.has(method)) this.listeners.set(method, []);
    this.listeners.get(method).push(fn);
  }
  close() {
    try { this.ws && this.ws.close(); } catch {}
  }
}

const cmd = process.argv[2];
const args = process.argv.slice(3);

async function main() {
  if (!cmd) { console.error('no command'); process.exit(2); }

  if (cmd === 'list-targets') {
    const targets = await httpJson('/json/list');
    const pages = targets.filter(t => t.type === 'page');
    for (const t of pages) {
      console.log(JSON.stringify({ id: t.id, title: t.title, url: t.url }));
    }
    return;
  }

  if (cmd === 'new-tab') {
    const url = args[0];
    let r = await fetch(CDP_HTTP + `/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
    if (!r.ok) r = await fetch(CDP_HTTP + `/json/new?${encodeURIComponent(url)}`);
    if (!r.ok) throw new Error('new-tab failed: ' + r.status);
    const t = await r.json();
    console.log(t.id);
    return;
  }

  if (cmd === 'close-tab') {
    const id = args[0];
    const r = await fetch(CDP_HTTP + `/json/close/${id}`);
    console.log(r.ok ? 'closed' : 'failed');
    return;
  }

  if (cmd === 'get-url') {
    const id = args[0];
    const targets = await httpJson('/json/list');
    const t = targets.find(x => x.id === id);
    if (!t) { console.log('NOT_FOUND'); process.exit(1); }
    console.log(t.url);
    return;
  }

  // Commands that need a live session
  const targets = await httpJson('/json/list');
  const tab = targets.find(t => t.id === args[0] && t.type === 'page');
  if (!tab) { console.error('tab not found: ' + args[0]); process.exit(1); }

  const sess = new CdpSession(tab.webSocketDebuggerUrl);
  await sess.connect();
  await sess.send('Runtime.enable');

  if (cmd === 'set-url') {
    const url = args[1];
    await sess.send('Page.enable');
    await sess.send('Page.navigate', { url });
    await waitForLoad(sess, Number(args[2] || 45000));
    console.log('navigated');
  } else if (cmd === 'eval') {
    const js = args[1];
    const r = await sess.send('Runtime.evaluate', { expression: js, returnByValue: true, awaitPromise: true, timeout: 45000 });
    if (r.exceptionDetails) {
      console.error('EXC: ' + JSON.stringify(r.exceptionDetails.exception?.description || r.exceptionDetails.text));
      process.exit(1);
    }
    const v = r.result && r.result.value !== undefined ? r.result.value : (r.result ? JSON.stringify(r.result) : '');
    console.log(typeof v === 'string' ? v : JSON.stringify(v));
  } else if (cmd === 'wait-load') {
    await waitForLoad(sess, Number(args[1] || 30000));
    console.log('loaded');
  } else {
    console.error('unknown session command: ' + cmd);
    process.exit(2);
  }
  sess.close();
}

function waitForLoad(sess, timeoutMs) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (ok) => { if (!done) { done = true; resolve(ok); } };
    const onEvent = () => finish(true);
    sess.on('Page.loadEventFired', onEvent);
    // Also resolve if already loaded (document readyState complete) — checked after a short delay
    setTimeout(async () => {
      try {
        const r = await sess.send('Runtime.evaluate', { expression: 'document.readyState', returnByValue: true });
        if (r.result && r.result.value === 'complete') finish(true);
      } catch {}
    }, 500);
    setTimeout(() => finish(false), timeoutMs);
  });
}

main().catch(e => { console.error('FATAL: ' + e.message); process.exit(1); });
