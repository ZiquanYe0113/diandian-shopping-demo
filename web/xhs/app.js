const originalNotes=[];
import {sessionKey,searchLocalNotes,beginPending,applyJobSnapshot,pollJob,searchReturnLocation,parseRoute} from './state.mjs';
import * as views from './views.js?v=market-ai-v1';
import {mergeRealNotes,xhsRequest,safeQrImage} from './real-note.mjs';
const phone=document.querySelector('#phone');
const realNoteDemo=document.querySelector('#real-note-demo');
const STORAGE='diandian-xhs-v2-real-catalog';
let saved={};try{saved=JSON.parse(localStorage.getItem(STORAGE)||'{}')}catch{}
let conversations=saved.conversations||{},history=saved.history||[],route=parseRoute(location.search),chatOrigin=saved.chatOrigin||null;
let notes=[],products=[],mode='real',searchTab=saved.searchTab||'all',noteReturn=saved.noteReturn||null;
const busy=new Set(Object.keys(conversations).filter(key=>conversations[key].pending)),drafts=saved.drafts||{},attachments=saved.attachments||{},scrolls=saved.scrolls||{},polling=new Set();
let storageWarning=false;
const realNote={open:false,draft:saved.realNoteDraft||'',busy:'',status:null,error:'',qr:'',qrExpires:0};
function toast(text){const el=document.querySelector('#toast');el.textContent=text;el.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.hidden=true,3500)}
function persist(){try{localStorage.setItem(STORAGE,JSON.stringify({conversations,history,chatOrigin,noteReturn,searchTab,drafts,attachments,scrolls,realNoteDraft:realNote.draft}));return true}catch{if(!storageWarning){toast('本地保存空间不足；当前对话仍可继续。');storageWarning=true}return false}}
function currentNote(){return notes.find(n=>n.note_id===route.noteId)}
function context(){
 if(route.screen==='market-ai')return {entry:'CHAT',key:'CHAT:market'};
 if(route.screen==='note')return {entry:'NOTE',noteId:route.noteId,key:sessionKey('NOTE',route.noteId)};
 if(route.screen==='results')return {entry:'SEARCH',query:route.query,key:sessionKey('SEARCH','',route.query)};
 if(route.screen==='chat'&&chatOrigin&&conversations[chatOrigin]?.context)return {...conversations[chatOrigin].context,key:chatOrigin};
 return {entry:'CHAT',key:sessionKey('CHAT')};
}
function syncUrl(){const p=new URLSearchParams();if(route.screen!=='home')p.set('screen',route.screen);if(route.noteId)p.set('note',route.noteId);if(route.query)p.set('q',route.query);if(route.sheet)p.set('sheet','1');window.history.replaceState({},'',location.pathname+(p.size?'?'+p:''))}
function saveScroll(){const key=phone.dataset.viewKey;phone.querySelectorAll('[data-scroll]').forEach(el=>scrolls[key+':'+el.dataset.scroll]=el.scrollTop)}
function render(bottom=false,skipSave=false){
 if(!skipSave)saveScroll();const ctx=context(),c=conversations[ctx.key],isBusy=busy.has(ctx.key),draft=drafts[ctx.key]||'',images=attachments[ctx.key]||[];
 const viewKey=route.screen+':'+(route.noteId||route.query||ctx.key);
 if(route.screen==='home')phone.innerHTML=views.home(notes);
 else if(route.screen==='market')phone.innerHTML=views.market(products);
 else if(route.screen==='market-ai')phone.innerHTML=views.marketChat({c,busy:isBusy,draft});
 else if(route.screen==='search')phone.innerHTML=views.search({query:route.query,history});
 else if(route.screen==='results')phone.innerHTML=views.results({products,query:route.query,found:searchLocalNotes(route.query,notes,products),c,busy:isBusy,draft,shopping:/耳机|降噪|头戴|香水|香调|试香|预算|推荐|买|选/.test(route.query)||products.some(p=>p.aliases.split(';').some(a=>a.length>2&&route.query.toLowerCase().includes(a.toLowerCase()))),tab:searchTab});
 else if(route.screen==='note')phone.innerHTML=views.noteView({products,n:currentNote(),c,busy:isBusy,draft,sheet:route.sheet,action:c?.action||'summary',mode});
 else phone.innerHTML=views.chat({products,c,busy:isBusy,draft,images,entry:ctx.entry,action:c?.action||'summary',source:ctx.entry==='NOTE'?'来自笔记：'+(notes.find(n=>n.note_id===ctx.noteId)?.title||'本篇笔记'):ctx.entry==='SEARCH'?'来自搜索：'+ctx.query:'',mode});
 if(realNoteDemo)realNoteDemo.innerHTML=views.realNotePanel(realNote);
 phone.dataset.viewKey=viewKey;document.body.dataset.screen=route.screen;
 phone.querySelectorAll('[data-scroll]').forEach(el=>{el.scrollTop=bottom&&el.dataset.scroll!=='note'?el.scrollHeight:scrolls[viewKey+':'+el.dataset.scroll]||0});
 if(bottom&&route.screen==='results'){const el=phone.querySelector('[data-scroll=results]'),last=phone.querySelector('.search-ai .chat-message:last-child');if(el&&last)el.scrollTop=last.getBoundingClientRect().top-el.getBoundingClientRect().top+el.scrollTop-10}
 if(route.sheet&&!busy.has(ctx.key))phone.querySelector('#message')?.focus({preventScroll:true});
 syncUrl();
}
function navigate(screen,props={}){route={screen,noteId:'',query:'',sheet:false,...props};if(screen==='chat'&&!props.keepOrigin){chatOrigin=null;persist()}render()}
function closeSheet(){route.sheet=false;render();phone.querySelector('[data-action="open-sheet"]')?.focus()}
function openSheet(){route.sheet=true;render();phone.querySelector('[data-action="close-sheet"]')?.focus()}
function submitSearch(query){const q=query.trim();if(!q)return;history=[q,...history.filter(x=>x!==q)].slice(0,8);searchTab='all';persist();navigate('results',{query:q})}
function updatePendingIndicator(key){
 if(context().key!==key)return;
 const indicator=phone.querySelector('.thinking');
 if(indicator){const pending=conversations[key]?.pending;indicator.innerHTML=`<span></span>${views.esc(pending?.connectionLost?'连接暂时中断，正在查询原请求 · '+views.pendingLabel(pending):views.pendingLabel(pending))}`;}
}
function applySnapshot(key,id,job){
 conversations=applyJobSnapshot(conversations,key,id,job);
 const c=conversations[key];
 if(!c?.pending){
  busy.delete(key);
  if(c?.recovery){if(!drafts[key])drafts[key]=c.recovery.text;if(!attachments[key]?.length)attachments[key]=c.recovery.images||[];}
 }
 persist();
 if(context().key===key){if(!c?.pending)render(true);else updatePendingIndicator(key)}
}
async function recoverJob(key){
 const id=conversations[key]?.pending?.id;if(!id||polling.has(key))return;
 polling.add(key);busy.add(key);
 try{await pollJob(id,{
  read:url=>fetch(url),
  active:()=>conversations[key]?.pending?.id===id,
  onSnapshot:job=>applySnapshot(key,id,job),
  onUnavailable:()=>{const c=conversations[key];if(c?.pending?.id===id){conversations={...conversations,[key]:{...c,pending:{...c.pending,connectionLost:true}}};persist();updatePendingIndicator(key)}}
 });}finally{polling.delete(key)}
}
setInterval(()=>{const key=context().key;if(busy.has(key))updatePendingIndicator(key)},1000);
async function send(text){
 text=text.trim();if(!text)return;
 const ctx={...context()},key=ctx.key;if(busy.has(key))return;
 const n=ctx.entry==='NOTE'?notes.find(n=>n.note_id===ctx.noteId):null;
 if(ctx.entry==='NOTE'&&!n){toast('笔记不存在，请返回首页重新选择。');return}
 const noteAction=ctx.entry==='NOTE'?'summary':undefined;
 const old=conversations[key]||{messages:[]},images=[...(attachments[key]||[])],id=crypto.randomUUID();
 conversations=beginPending({...conversations,[key]:{...old,context:ctx,action:noteAction}},key,{id,text,images,startedAt:Date.now()});
 drafts[key]='';attachments[key]=[];busy.add(key);
 if(!persist()){conversations={...conversations,[key]:old};drafts[key]=text;attachments[key]=images;busy.delete(key);render();toast('无法保存请求，尚未提交。请减少图片或清理本地空间后手动重试。');return}
 render(true);
 const payload={request_id:id,entry:ctx.entry,message:text,session_id:old.sessionId||null,images};
 if(ctx.entry==='NOTE'){payload.note_context={note_id:n.note_id,title:n.title,text:n.text,image_revision:n.image_revision||''};payload.note_action=noteAction}
 try{
  const response=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(!response.ok){
   // A definite validation rejection did not start work. Unknown server failures are queried by ID.
   if(response.status>=400&&response.status<500){applySnapshot(key,id,{status:'interrupted'});toast('提交未被接受，请检查输入后手动重试。');return}
   throw Error('提交状态暂时未知');
  }
  const job=await response.json();applySnapshot(key,id,job);
 }catch{const c=conversations[key];if(c?.pending){conversations={...conversations,[key]:{...c,pending:{...c.pending,connectionLost:true}}};persist();updatePendingIndicator(key)}}
 if(conversations[key]?.pending)recoverJob(key);
}
async function realNoteAction(action){
 if(realNote.busy)return;
 if(action==='read'&&!realNote.draft.trim()){realNote.error='请粘贴完整分享文案或笔记链接。';render();return}
 realNote.busy=action;realNote.error='';render();
 try{
  if(action==='status'){
   realNote.status=await xhsRequest('/api/xhs/status');
   if(realNote.status.logged_in){realNote.qr='';realNote.qrExpires=0}
  }else if(action==='login'){
   const data=await xhsRequest('/api/xhs/login',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
   if(data.image===''&&data.timeout===0&&data.message==='已登录，可读取公开笔记'){
    realNote.status={available:true,logged_in:true,message:data.message};realNote.qr='';realNote.qrExpires=0;
   }else{
    realNote.qr=safeQrImage(data.image);realNote.qrExpires=Date.now()+Number(data.timeout||0)*1000;
    if(!realNote.qr)throw Error('二维码暂未生成，请检查服务后重试。');
   }
  }else{
   const data=await xhsRequest('/api/xhs/notes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:realNote.draft})});
   if(!data.note?.real||!data.note?.note_id||(!data.note?.text&&!data.note?.images?.length))throw Error('没有读取到完整笔记正文，请重新分享。');
   notes=mergeRealNotes(notes,[data.note]);noteReturn=null;persist();
   navigate('note',{noteId:data.note.note_id});
  }
 }catch(e){realNote.error=e.message}
 finally{realNote.busy='';render()}
}
realNoteDemo?.addEventListener('submit',event=>{event.preventDefault();realNoteAction('read')});
realNoteDemo?.addEventListener('input',event=>{if(event.target.id==='real-note-link'){realNote.draft=event.target.value;persist()}});
phone.addEventListener('submit',event=>{event.preventDefault();if(event.target.dataset.form==='search')submitSearch(document.querySelector('#query').value);else if(event.target.dataset.form==='real-note')realNoteAction('read');else send(document.querySelector('#message').value)});
phone.addEventListener('input',event=>{if(event.target.id==='real-note-link'){realNote.draft=event.target.value;persist()}else if(event.target.id==='message'){drafts[context().key]=event.target.value;persist()}});
document.addEventListener('click',event=>{
 const b=event.target.closest('[data-action]');if(!b||b.disabled)return;
 const action=b.dataset.action,ctx=context();
 if(action==='home')navigate('home');
 else if(action==='market'||action==='market-ai')navigate(action);
 else if(action==='chat')navigate('chat');
 else if(action==='search')navigate('search');
 else if(action==='real-note-toggle'){realNote.open=!realNote.open;render();if(realNote.open&&!realNote.status)realNoteAction('status')}
 else if(action==='real-note-status')realNoteAction('status');
 else if(action==='real-note-login')realNoteAction('login');
 else if(action==='note'){if(!notes.some(n=>n.note_id===b.dataset.id)){toast('未收录该笔记');return}saveScroll();const origin=searchReturnLocation(route,searchTab,phone.querySelector('[data-scroll=results]')?.scrollTop||0);if(origin)noteReturn=origin;else if(route.screen!=='note'&&!(route.screen==='chat'&&ctx.entry==='NOTE'))noteReturn=null;persist();navigate('note',{noteId:b.dataset.id})}
 else if(action==='back'){
  if(route.screen==='market-ai')navigate('market');
  else if(route.screen==='chat'&&chatOrigin){const c=conversations[chatOrigin]?.context;chatOrigin=null;if(c?.entry==='NOTE')navigate('note',{noteId:c.noteId});else if(c?.entry==='SEARCH')navigate('results',{query:c.query});else navigate('home')}
  else if(route.screen==='note'&&noteReturn){const origin=noteReturn;noteReturn=null;searchTab=origin.tab;scrolls['results:'+origin.query+':results']=origin.scroll;persist();navigate('results',{query:origin.query})}
  else if(route.screen==='results')navigate('search',{query:route.query});else navigate('home');
 }
 else if(action==='search-chip')submitSearch(b.dataset.text);
 else if(action==='clear-history'){history=[];persist();render()}
 else if(action==='prompt')send(b.dataset.text);
 else if(action==='search-ai')send(route.query);
 else if(action==='tab'){searchTab=b.dataset.value;persist();render()}
 else if(action==='edit-condition'){drafts[ctx.key]=b.dataset.text;persist();render();phone.querySelector('#message')?.focus({preventScroll:true})}
 else if(action==='restore-input'){const recovery=conversations[ctx.key]?.recovery;if(recovery&&!busy.has(ctx.key)){drafts[ctx.key]=recovery.text;attachments[ctx.key]=recovery.images||[];persist();render();phone.querySelector('#message')?.focus({preventScroll:true})}}
 else if(action==='open-sheet')openSheet();
 else if(action==='close-sheet')closeSheet();
 else if(action==='hide-ai'||action==='show-ai'){
  if(ctx.entry!=='SEARCH')return;
  const c=conversations[ctx.key]||{messages:[],context:ctx};conversations={...conversations,[ctx.key]:{...c,hidden:action==='hide-ai'}};persist();render();
 }
 else if(action==='note-action')send(views.NOTE_SUMMARY_REQUEST);
 else if(action==='full-chat'){
  const c=conversations[ctx.key]||{messages:[],action:'summary'};conversations={...conversations,[ctx.key]:{...c,context:ctx}};chatOrigin=ctx.key;persist();navigate('chat',{keepOrigin:true});
 }
 else if(action==='new'){
  if(busy.has(ctx.key)){toast('请等本轮结束后再新建对话');return}
  saveScroll();
  conversations={...conversations,[ctx.key]:{messages:[],context:ctx,action:ctx.entry==='NOTE'?'summary':undefined}};drafts[ctx.key]='';attachments[ctx.key]=[];
  const conversationScrollKeys=[`chat:${ctx.key}:conversation`];
  if(ctx.entry==='NOTE')conversationScrollKeys.push(`note:${ctx.noteId}:sheet`);
  if(ctx.entry==='SEARCH')conversationScrollKeys.push(`results:${ctx.query}:results`);
  for(const key of conversationScrollKeys)delete scrolls[key];
  persist();render(false,true);
 }
 else if(action==='clear-images'){attachments[ctx.key]=[];render()}
 else if(action==='source'){const n=currentNote();if(n?.source_url)window.open(views.safeUrl(n.source_url),'_blank','noopener,noreferrer');else toast('这是本地虚构生活笔记，没有线上来源')}
 else if(action==='catalog')submitSearch('香水');
 else if(action==='demo')toast('这是本地实验，当前先体验点点、搜索和笔记入口。');
});
phone.addEventListener('keydown',event=>{
 if(event.key==='Enter'&&event.target.id==='message'&&!event.shiftKey&&!event.isComposing){event.preventDefault();send(event.target.value)}
 if(!route.sheet)return;
 if(event.key==='Escape'){event.preventDefault();closeSheet()}
 if(event.key==='Tab'){
  const items=[...phone.querySelectorAll('.note-ai-sheet button:not([disabled]),.note-ai-sheet textarea:not([disabled]),.note-ai-sheet summary,.note-ai-sheet a[href]')];
  const first=items[0],last=items.at(-1);if(!first)return;
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
 }
});
phone.addEventListener('change',async event=>{
 if(event.target.id!=='images')return;const key=context().key;
 try{const files=[...event.target.files];if(files.length>3||files.some(f=>f.size>5*1024*1024||!['image/jpeg','image/png','image/webp'].includes(f.type)))throw Error('最多3张JPEG/PNG/WebP图片，每张不超过5MB');attachments[key]=await Promise.all(files.map(f=>new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(f)})));persist();if(context().key===key)render()}
 catch(e){attachments[key]=[];toast(e.message)}
});
async function init(){
 try{
  const responses=await Promise.all([fetch('/api/health'),fetch('/api/catalog')]);if(responses.some(r=>!r.ok))throw Error('服务未连接');
  const [health,catalog]=await Promise.all(responses.map(r=>r.json()));mode=health.mode;products=catalog.products;
  const fragrance=catalog.notes.map((n,i)=>({...n,palette:i%6,coverLabel:products.find(p=>n.product_ids.includes(p.product_id))?.brand||'SCENT DIARY',displayText:n.text.replace(/^# [^\n]+\n+/, '').replace(/## /g,'')}));
  const life=originalNotes.filter(n=>!n.shopping).map(n=>({...n,note_id:n.id,text:n.body+'\n'+n.tags.join(' '),displayText:n.body,product_ids:[],demo:true}));
  notes=fragrance;
  try{const data=await xhsRequest('/api/xhs/notes');notes=mergeRealNotes(notes,data.notes)}catch(e){realNote.error='已保存笔记暂时无法恢复：'+e.message}
  document.querySelector('#mode').textContent=mode==='mock'?'模拟模式 · 不调用API':'Qwen3.5-Flash · 真实模式';
  if(route.screen==='note'&&!currentNote())route={screen:'home',noteId:'',query:'',sheet:false};
  // Restore backend text if a local conversation result has been cleared by storage limits.
  const ctx=context(),c=conversations[ctx.key];
  if(c?.sessionId&&!c.messages?.length){
   const r=await fetch('/api/session/'+encodeURIComponent(c.sessionId));
   if(r.ok){
    const data=await r.json(),messages=(data.history||[]).map(m=>({role:m.role,text:m.text})),last=messages.at(-1),result=data.last_result;
    if(result?.status==='ERROR')messages.push({role:'error',text:result.answer,result});
    else if(last?.role==='assistant'&&typeof result?.answer==='string'&&last.text===result.answer)last.result=result;
    if(conversations[ctx.key]?.sessionId===c.sessionId&&!conversations[ctx.key]?.pending&&!conversations[ctx.key]?.messages?.length){conversations={...conversations,[ctx.key]:{...conversations[ctx.key],messages}};persist();}
   }
  }
  for(const [key,c] of Object.entries(conversations)){if(c.recovery){if(!drafts[key])drafts[key]=c.recovery.text;if(!attachments[key]?.length)attachments[key]=c.recovery.images||[];}}
  render();for(const key of busy)recoverJob(key);if(route.sheet)phone.querySelector('[data-action="close-sheet"]')?.focus();
 }catch(e){phone.innerHTML=`<section class="boot"><h2>暂时连接不到服务</h2><p>${views.esc(e.message)}</p><button onclick="location.reload()">重新连接</button></section>`;document.querySelector('#mode').textContent='本地服务连接失败'}
}
window.addEventListener('pagehide',()=>{saveScroll();persist()});
init();
