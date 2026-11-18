import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
const fixture=JSON.parse(fs.readFileSync('demo/fixtures.json','utf8'));
const box={fetch:async()=>({json:async()=>fixture}),Response:globalThis.Response,URL,location:{href:'http://localhost/demo/'},crypto:webcrypto,Map,console};
if(!box.Response)box.Response=class{constructor(body,options){this.body=body;this.status=options.status;}async json(){return JSON.parse(this.body)}};
vm.createContext(box);
let code=fs.readFileSync('demo/offline.mjs','utf8').replace("await import('./web/xhs/app.js');",'');
await vm.runInContext('(async()=>{'+code+'})()',box);
async function send(message,sid,entry='CHAT'){const r=await box.fetch('/api/jobs',{method:'POST',body:JSON.stringify({request_id:message,entry,message,session_id:sid})});return (await r.json()).result}
let r=await send('预算1000元通勤耳机');assert.equal(r.status,'READY');assert.equal(r.requirements.budget_max,1000);
r=await send('只看入耳式',r.session_id);assert.equal(r.status,'NO_RESULT');assert.equal(r.requirements.budget_max,1000);
r=await send('总结这篇',null,'NOTE');assert.equal(r.status,'NOTE_SUMMARY');assert.equal(r.note_analysis.resolved_products.length,1);
console.log('Static demo: budget, incompatible style, note extraction passed');
