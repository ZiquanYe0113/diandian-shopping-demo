import test from 'node:test';
import assert from 'node:assert/strict';
async function state(){return import('../web/xhs/state.mjs')}
async function appHarness(saved,respond,search='',storageFails=false){
 const {readFileSync}=await import('node:fs'),{runInNewContext}=await import('node:vm');
 const views=await import('../web/xhs/views.js'),helpers=await state(),realHelpers=await import('../web/xhs/real-note.mjs');
 const listeners={},demoListeners={},documentListeners={},storage={value:JSON.stringify(saved)},locations=[],requests=[];
 const message={value:'原始问题'},resultScroll={scrollTop:350},phone={dataset:{},innerHTML:'',addEventListener:(name,fn)=>listeners[name]=fn,querySelectorAll:()=>[],querySelector:selector=>selector==='[data-scroll=results]'?resultScroll:null};
 const demo={innerHTML:'',addEventListener:(name,fn)=>demoListeners[name]=fn};
 const document={body:{dataset:{}},querySelector:selector=>selector==='#phone'?phone:selector==='#real-note-demo'?demo:selector==='#message'?message:{textContent:'',hidden:true},addEventListener:(name,fn)=>documentListeners[name]=fn};
 const fetch=async(url,options)=>{requests.push({url,options});if(url==='/api/xhs/notes'&&!options?.method)return {ok:true,json:async()=>({notes:saved.realNotes||[]})};if(url==='/api/health')return {ok:true,json:async()=>({mode:'mock'})};if(url==='/api/catalog')return {ok:true,json:async()=>({products:[],notes:[1,2,3].map(i=>({note_id:'n'+i,title:'笔记'+i,text:'内容',product_ids:[]}))})};return respond(url,options)};
 const code=readFileSync(new URL('../web/xhs/app.js',import.meta.url),'utf8').replace(/^import .*;\n/gm,'');
 runInNewContext(code,{...helpers,...realHelpers,xhsRequest:(url,options)=>realHelpers.xhsRequest(url,options,fetch),views,originalNotes:['life','life2','life3'].map(id=>({id,title:'日常',body:'散步',tags:[]})),document,window:{history:{replaceState:(_a,_b,url)=>locations.push(url)},addEventListener:()=>{}},location:{search,pathname:'/xhs'},localStorage:{getItem:()=>storage.value,setItem:(_k,v)=>{if(storageFails)throw Error('quota');storage.value=v}},URLSearchParams,crypto:{randomUUID:()=> 'new-job'},fetch,setInterval:()=>{},clearTimeout:()=>{},setTimeout:fn=>{setImmediate(fn)}});
 await new Promise(resolve=>setImmediate(resolve));
 return {phone,demo,storage,locations,requests,message,input:value=>{message.value=value;listeners.input({target:{id:'message',value}})},realInput:value=>demoListeners.input({target:{id:'real-note-link',value}}),realSend:()=>demoListeners.submit({preventDefault(){},target:{dataset:{form:'real-note'}}}),send:()=>listeners.submit({preventDefault(){},target:{dataset:{form:'message'}}}),click:dataset=>documentListeners.click({target:{closest:()=>({dataset})}})};
}

test('search collapse and resume preserve only the current query conversation',async()=>{
 const c={messages:[{role:'assistant',text:'保留答案'}],sessionId:'old'};
 const app=await appHarness({conversations:{'SEARCH:雨天':c,'SEARCH:晴天':c}},async()=>assert.fail('no requests'),'?screen=results&q=雨天');
 app.click({action:'hide-ai'});
 let saved=JSON.parse(app.storage.value);assert.equal(saved.conversations['SEARCH:雨天'].hidden,true);assert.equal(saved.conversations['SEARCH:雨天'].sessionId,'old');assert.equal(saved.conversations['SEARCH:晴天'].hidden,undefined);
 app.click({action:'show-ai'});saved=JSON.parse(app.storage.value);assert.equal(saved.conversations['SEARCH:雨天'].hidden,false);assert.deepEqual(saved.conversations['SEARCH:雨天'].messages,c.messages);
});
test('new resets current NOTE session, recovery, input and conversation scroll while preserving other entries',async()=>{
 const old={messages:[{role:'assistant',text:'旧答案'}],sessionId:'old',recovery:{text:'恢复'},hidden:true,action:'other'};
 const app=await appHarness({conversations:{'NOTE:n1':old,'NOTE:n2':old,'CHAT:main':old},drafts:{'NOTE:n1':'草稿','NOTE:n2':'别处'},attachments:{'NOTE:n1':['图'],'NOTE:n2':['别图']},scrolls:{'note:n1:sheet':250,'note:n1:note':900,'note:n2:conversation':600,'chat:NOTE:n1:conversation':300}},async()=>assert.fail('no requests'),'?screen=note&note=n1&sheet=1');
 app.click({action:'new'});const saved=JSON.parse(app.storage.value),c=saved.conversations['NOTE:n1'];
 assert.deepEqual(c.messages,[]);assert.equal(c.sessionId,undefined);assert.equal(c.recovery,undefined);assert.equal(c.hidden,undefined);assert.equal(c.action,'summary');assert.equal(saved.drafts['NOTE:n1'],'');assert.deepEqual(saved.attachments['NOTE:n1'],[]);
 assert.equal(saved.scrolls['note:n1:sheet'],undefined);assert.equal(saved.scrolls['chat:NOTE:n1:conversation'],undefined);assert.equal(saved.scrolls['note:n1:note'],900);assert.equal(saved.scrolls['note:n2:conversation'],600);assert.deepEqual(saved.conversations['NOTE:n2'],old);assert.deepEqual(saved.conversations['CHAT:main'],old);assert.match(app.locations.at(-1),/sheet=1/);
});
test('pending request may be hidden but cannot be reset and completes once in its original session',async()=>{
 let finish;
 const app=await appHarness({conversations:{'SEARCH:雨天':{messages:[{role:'user',text:'问'}],pending:{id:'pending',text:'问',images:[],startedAt:1}}}},async()=>new Promise(resolve=>finish=()=>resolve({ok:true,json:async()=>({request_id:'pending',status:'completed',result:{session_id:'s',answer:'结果'}})})),'?screen=results&q=雨天');
 app.click({action:'hide-ai'});app.click({action:'new'});assert.equal(JSON.parse(app.storage.value).conversations['SEARCH:雨天'].pending.id,'pending');finish();await new Promise(resolve=>setImmediate(resolve));
 const c=JSON.parse(app.storage.value).conversations['SEARCH:雨天'];assert.equal(c.hidden,true);assert.equal(c.messages.at(-1).text,'结果');assert.equal(app.requests.filter(r=>r.options?.method==='POST').length,0);
 app.click({action:'new'});assert.deepEqual(JSON.parse(app.storage.value).conversations['SEARCH:雨天'].messages,[]);
});
test('late session restoration cannot bring an explicitly reset conversation back',async()=>{
 let finish;
 const app=await appHarness({conversations:{'NOTE:n1':{sessionId:'old',messages:[]}}},async()=>new Promise(resolve=>finish=()=>resolve({ok:true,json:async()=>({history:[{role:'assistant',text:'旧内容'}]})})),'?screen=note&note=n1&sheet=1');
 app.click({action:'new'});finish();await new Promise(resolve=>setImmediate(resolve));
 const c=JSON.parse(app.storage.value).conversations['NOTE:n1'];assert.deepEqual(c.messages,[]);assert.equal(c.sessionId,undefined);
});
