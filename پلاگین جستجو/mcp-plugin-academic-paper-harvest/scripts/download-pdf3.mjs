#!/usr/bin/env node
// Downloads a PDF by:
// 1. Setting Browser.setDownloadBehavior on the browser to save to a dir
// 2. Navigating to the paper page
// 3. Clicking the single "Download PDF" button
// 4. Waiting for Browser.downloadProgress to report completed
// Usage: node download-pdf3.mjs <tabId> <paperUrl> <downloadDir>
const CDP_HTTP = 'http://127.0.0.1:9222';
import { mkdirSync } from 'node:fs';
async function httpJson(p){const r=await fetch(CDP_HTTP+p);if(!r.ok)throw new Error('http '+r.status);return r.json();}
class S{constructor(u){this.u=u;this.id=1;this.p=new Map();this.l=new Map();}
 connect(){return new Promise((res,rej)=>{this.ws=new WebSocket(this.u);this.ws.addEventListener('open',()=>res(),{once:true});this.ws.addEventListener('error',()=>rej(new Error('ws error')),{once:true});this.ws.addEventListener('message',ev=>{let m;try{m=JSON.parse(ev.data);}catch{return;}if(m.id!==undefined&&this.p.has(m.id)){const{x,y}=this.p.get(m.id);this.p.delete(m.id);m.error?y(new Error(m.error.message)):x(m.result);}else if(m.method){(this.l.get(m.method)||[]).forEach(f=>f(m.params));}});});}
 send(method,params={}){const id=this.id++;return new Promise((res,rej)=>{this.p.set(id,{x:res,y:rej});this.ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(this.p.has(id)){this.p.delete(id);rej(new Error('timeout '+method));}},120000);});}
 on(m,f){if(!this.l.has(m))this.l.set(m,[]);this.l.get(m).push(f);}
 close(){try{this.ws&&this.ws.close();}catch{}}}
const [tabId, paperUrl, downloadDir] = process.argv.slice(2);
mkdirSync(downloadDir, {recursive:true});
// 1. Set download behavior on BROWSER level
const ver = await httpJson('/json/version');
const bs = new S(ver.webSocketDebuggerUrl);
await bs.connect();
await bs.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: downloadDir, eventsEnabled: true });
console.log('Browser download behavior set');
bs.close();
// 2. Use the tab
const targets = await httpJson('/json/list');
const tab = targets.find(t=>t.id===tabId&&t.type==='page');
if(!tab){console.error('tab not found');process.exit(1);}
const s = new S(tab.webSocketDebuggerUrl);
await s.connect();
await s.send('Page.enable');
await s.send('Runtime.enable');
// Also set at page level
try { await s.send('Page.setDownloadBehavior', { behavior: 'allow', downloadPath: downloadDir, eventsEnabled: true }); } catch(e) { console.log('Page.setDownloadBehavior not available: ' + e.message); }
// Track downloads
let dlStarted = false, dlCompleted = false, dlFilename = '';
s.on('Browser.downloadWillBegin', p => { dlStarted = true; dlFilename = p.suggestedFilename; console.log('Download will begin: ' + dlFilename); });
s.on('Browser.downloadProgress', p => {
  console.log('Download progress: ' + p.state + ' received=' + p.receivedBytes + ' total=' + p.totalBytes);
  if (p.state === 'completed') { dlCompleted = true; }
});
s.on('Page.downloadWillBegin', p => { dlStarted = true; dlFilename = p.suggestedFilename; console.log('Page download will begin: ' + dlFilename); });
s.on('Page.downloadProgress', p => {
  console.log('Page download progress: ' + p.state);
  if (p.state === 'complete') { dlCompleted = true; }
});
// 3. Navigate to paper
console.log('Navigating to: ' + paperUrl);
await s.send('Page.navigate', { url: paperUrl });
await new Promise(r=>setTimeout(r, 12000));
// 4. Click the single PDF download button
const clickJs = `(function(){
  var btns = document.querySelectorAll('button');
  // Try to find "arrow_downward Download PDF" (single PDF button)
  for (var i = 0; i < btns.length; i++) {
    var t = (btns[i].innerText || '').replace(/\\n/g,' ').trim();
    if (/arrow_downward/.test(t) && /Download PDF/.test(t) && !/Pack|Package/.test(t)) {
      btns[i].click();
      return JSON.stringify({clicked: t});
    }
  }
  // Fallback: "Download PDF" without Pack
  for (var j = 0; j < btns.length; j++) {
    var t2 = (btns[j].innerText || '').replace(/\\n/g,' ').trim();
    if (/Download PDF/.test(t2) && !/Pack|Package/.test(t2)) {
      btns[j].click();
      return JSON.stringify({clicked: t2, fallback: true});
    }
  }
  return JSON.stringify({clicked: null, hint: 'no single PDF download button found', body: document.body.innerText.slice(0,300)});
})()`;
const cr = await s.send('Runtime.evaluate', { expression: clickJs, returnByValue: true });
if(cr.exceptionDetails){console.error('EXC: '+(cr.exceptionDetails.exception&&cr.exceptionDetails.exception.description||cr.exceptionDetails.text));}
console.log('Click: '+(typeof cr.result.value==='string'?cr.result.value:JSON.stringify(cr.result.value)));
// 5. Wait for download
for (let i = 0; i < 30; i++) {
  await new Promise(r=>setTimeout(r, 2000));
  if (dlCompleted) break;
}
console.log(JSON.stringify({dlStarted, dlCompleted, dlFilename}));
s.close();
