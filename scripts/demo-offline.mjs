const fixture=await fetch('./fixtures.json').then(r=>r.json());
const product=fixture.products[0],note=fixture.notes[0],jobs=new Map(),sessions=new Map();
const nativeFetch=globalThis.fetch.bind(globalThis);
const response=(data,status=200)=>Promise.resolve(new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}}));
function answer(q){
 const sid=q.session_id||crypto.randomUUID(),old=sessions.get(sid)||{},text=q.message||'';
 let budget=old.budget??null;const m=text.match(/预算\s*(\d+)|(\d+)\s*元|^(\d+)$/);if(m)budget=Number(m[1]||m[2]||m[3]);
 const style=/取消.*入耳|不要求入耳/.test(text)?'':/入耳/.test(text)?'入耳式':old.style||'';
 const req={category:'耳机',budget_max:budget,use_case:old.scene||'',preferences:old.preferences||[]};
 if(/通勤/.test(text))req.use_case='通勤';
 if(/降噪/.test(text))req.preferences=['主动降噪'];
 let products=[product],status='READY',summary='这是一款头戴包耳式耳机，适合先比较佩戴方式、降噪功能与续航参数。实际佩戴感受建议试戴确认。';
 if(style==='入耳式'){products=[];status='NO_RESULT';summary='这款是头戴包耳式，不符合入耳式要求。小样只收录这一款，不会把它当成入耳式推荐。可以取消这个条件，继续了解这款的降噪或续航。';}
 if(budget!=null&&budget<product.reference_price_cny){products=[];status='NO_RESULT';summary='当前收录参考价高于你的预算。本小样没有其他商品，不会自动放宽预算。';}
 const result={session_id:sid,status,answer:summary,products,requirements:req,mode:'mock',usage:[],elapsed_ms:0,evidence:[],recommendation_details:products.map(p=>({product_id:p.product_id,reasons:['支持主动降噪；头戴包耳式；约192g。','开启降噪官方测试最长35小时，关闭降噪最长50小时，实际续航受使用条件影响。'],sources:[],cautions:[p.cautions]})),followup_question:'可以继续问这款的降噪、续航或佩戴方式。'};
 if(/香水|薯片|苹果耳机|AirPods/i.test(text)){result.status='NO_RESULT';result.products=[];result.answer='小样仅展示索尼 WH-CH720N。其他商品请使用完整项目；这里不会生成目录外商品。';}
 if(q.entry==='NOTE'){
  result.status='NOTE_SUMMARY';result.products=[];result.answer=/续航/.test(text)?'笔记记录：开启降噪最长35小时，关闭降噪最长50小时，都是官方测试参数。':'这篇演示笔记介绍 WH-CH720N 的佩戴方式、主动降噪和官方续航参数，不包含个人实测结论。';
  const body=q.note_context?.text||note.text;result.answer=/续航/.test(text)?(/35小时/.test(body)?'笔记记录：开启降噪最长35小时，关闭降噪最长50小时，均为官方测试参数。':'这篇笔记未记录具体续航时长。'):body;
  result.note_analysis={summary:result.answer,key_points:[],author_opinion:'',image_observations:[],mentions:[{name:product.product_name,product_id:product.product_id,quote:'索尼 WH-CH720N',source:'text',confidence:'confirmed'}],resolved_products:[{...product,resolution_status:'matched'}]};result.followup_question='';
 }
 sessions.set(sid,{budget,style,scene:req.use_case,preferences:req.preferences,last_result:result});return result;
}
globalThis.fetch=(url,options={})=>{
 const path=new URL(String(url),location.href).pathname;
 if(path==='/api/health')return response({mode:'mock'});
 if(path==='/api/catalog')return response(fixture);
 if(path==='/api/xhs/notes')return response({notes:[]});
 if(path==='/api/jobs'&&options.method==='POST'){const q=JSON.parse(options.body);const result=answer(q);const job={request_id:q.request_id,status:'completed',result};jobs.set(q.request_id,job);return response(job);}
 if(path.startsWith('/api/jobs/'))return jobs.has(path.split('/').at(-1))?response(jobs.get(path.split('/').at(-1))):response({},404);
 if(path.startsWith('/api/session/'))return response(sessions.get(path.split('/').at(-1))||{},404);
 if(path.startsWith('/api/'))return response({detail:'静态演示不提供该服务'},404);
 return nativeFetch(url,options);
};
await import('./web/xhs/app.js');
