#!/usr/bin/env node
// Like cdp.mjs eval but reads the JS expression from a file (avoids shell quoting issues).
// Usage: node cdp-file.mjs eval <tabId> <jsFile>
import { readFileSync } from 'node:fs';
const CDP_HTTP = 'http://127.0.0.1:9222';
async function httpJson(p){const r=await fetch(CDP_HTTP+p);if(!r.ok)throw new Error('http '+r.status);return r.json();}
class S{constructor(u){this.u=u;this.id=1;this.p=new Map();}
 connect(){return new Promise((res,rej)=>{this.ws=new WebSocket(this.u);this.ws.addEventListener('open',()=>res(),{once:true});this.ws.addEventListener('error',()=>rej(new Error('ws error')),{once:true});this.ws.addEventListener('message',ev=>{let m;try{m=JSON.parse(ev.data);}catch{return;}if(m.id!==undefined&&this.p.has(m.id)){const{x,y}=this.p.get(m.id);this.p.delete(m.id);m.error?y(new Error(m.error.message)):x(m.result);}});});}
 send(method,params={}){const id=this.id++;return new Promise((res,rej)=>{this.p.set(id,{x:res,y:rej});this.ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(this.p.has(id)){this.p.delete(id);rej(new Error('timeout '+method));}},90000);});}
 close(){try{this.ws&&this.ws.close();}catch{}}}
const [cmd, tabId, file] = process.argv.slice(2);
const targets = await httpJson('/json/list');
const tab = targets.find(t=>t.id===tabId&&t.type==='page');
if(!tab){console.error('tab not found');process.exit(1);}
const s = new S(tab.webSocketDebuggerUrl); await s.connect();
await s.send('Runtime.enable');
if(cmd==='eval'){
  const expr = readFileSync(file,'utf8');
  const r = await s.send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true,timeout:60000});
  if(r.exceptionDetails){console.error('EXC: '+(r.exceptionDetails.exception&&r.exceptionDetails.exception.description||r.exceptionDetails.text));process.exit(1);}
  const v = r.result && r.result.value!==undefined ? r.result.value : (r.result?JSON.stringify(r.result):'');
  console.log(typeof v==='string'?v:JSON.stringify(v));
}
s.close();
