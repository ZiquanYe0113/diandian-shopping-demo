export function sessionKey(entry,noteId='',query=''){
 return entry==='NOTE'?`NOTE:${noteId}`:entry==='SEARCH'?`SEARCH:${query.trim().toLocaleLowerCase()}`:'CHAT:main';
}
export function searchLocalNotes(query,notes,products){
 const q=query.trim().toLocaleLowerCase();if(!q)return [];
 const ids=products.filter(p=>[p.product_name,...p.aliases.split(';')].some(a=>a.length>2&&(a.toLocaleLowerCase().includes(q)||q.includes(a.toLocaleLowerCase())))).map(p=>p.product_id);
 const category=/耳机|降噪|头戴/.test(q)?'耳机':/香水|香调|试香/.test(q)?'香水':'';
 const categoryIds=new Set(products.filter(p=>p.category===category).map(p=>p.product_id));
 return notes.filter(n=>`${n.title} ${n.text}`.toLocaleLowerCase().includes(q)||(n.product_ids||[]).some(id=>ids.includes(id))||(category&&(n.product_ids||[]).some(id=>categoryIds.has(id))));
}
export function recordResult(conversations,key,result){
 const old=conversations[key]||{messages:[]};
 return {...conversations,[key]:{...old,sessionId:result.session_id,messages:[...old.messages,{role:result.status==='ERROR'?'error':'assistant',text:result.answer,result}].slice(-20)}};
}
export function parseRoute(search){
 const p=new URLSearchParams(search);const screen=['home','chat','search','results','note','market','market-ai'].includes(p.get('screen'))?p.get('screen'):'home';
 return {screen,noteId:p.get('note')||'',query:p.get('q')||'',sheet:screen==='note'&&p.get('sheet')==='1'};
}
export function beginPending(conversations,key,pending){
 const old=conversations[key]||{messages:[]};
 return {...conversations,[key]:{...old,recovery:undefined,pending:{...pending,status:'queued',stage:'queued'},messages:[...old.messages,{role:'user',text:pending.text}].slice(-20)}};
}
export function applyJobSnapshot(conversations,key,id,job){
 const old=conversations[key];if(old?.pending?.id!==id||(job.request_id&&job.request_id!==id))return conversations;
 if(job.status==='completed'&&job.result){
  const next=recordResult(conversations,key,job.result);
  return {...next,[key]:{...next[key],pending:undefined,recovery:job.result.status==='ERROR'?old.pending:undefined}};
 }
 if(job.status==='interrupted')return {...conversations,[key]:{...old,pending:undefined,recovery:old.pending,messages:[...old.messages,{role:'error',text:'处理已中断，原输入已恢复。请确认后手动重试；不会自动再次调用模型。'}].slice(-20)}};
 return {...conversations,[key]:{...old,pending:{...old.pending,status:job.status,stage:job.stage||old.pending.stage,connectionLost:false}}};
}
export function searchReturnLocation(route,tab,scroll){return route.screen==='results'?{query:route.query,tab,scroll}:null}
export async function pollJob(id,{read,onSnapshot,onUnavailable=()=>{},pause=()=>new Promise(resolve=>setTimeout(resolve,1500)),active=()=>true}){
 while(active()){
  try{
   const response=await read('/api/jobs/'+encodeURIComponent(id));
   if(response.status===404){onSnapshot({status:'interrupted'});return}
   if(!response.ok)throw Error('无法查询处理状态');
   const job=await response.json();
   if((job.request_id&&job.request_id!==id)||!['queued','running','completed','interrupted'].includes(job.status)||(job.status==='completed'&&!job.result))throw Error('处理状态暂不可用');
   onSnapshot(job);
   if(job.status==='completed'||job.status==='interrupted')return;
  }catch(error){onUnavailable(error)}
  await pause();
 }
}
