export const NOTE_SUMMARY_REQUEST='帮我总结一下这篇笔记。';
export const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const br=x=>esc(x).replaceAll('\n','<br>');
export const safeUrl=x=>{try{let u=new URL(x);return u.protocol==='https:'?u.href:'#'}catch{return '#'}};
const button=(action,label,extra='')=>`<button type="button" data-action="${action}" ${extra}>${label}</button>`;
const back=(action='back')=>button(action,'‹','class="icon-button" aria-label="返回"');
const mark='<span class="dd-mark">点</span>';
export function statusBar(){return `<div class="status-bar"><b>9:41</b><span class="status-cluster" aria-hidden="true"><span class="signal-bars"><i></i><i></i><i></i><i></i></span><span class="wifi-mark"></span><span class="ios-battery"><i>73</i></span></span></div>`}
function cover(n,large=false){if(n.curated){
 if(/^\/api\/xhs\/images\/[a-f0-9]{24}\/[0-9]{1,2}$/.test(n.images?.[0]?.src||''))return `<div class="feed-real-photo"><img src="${esc(n.images[0].src)}?v=${esc(n.image_revision||'')}" alt="${esc(n.title)} · 原帖图片" loading="lazy"></div>`;
 const tone=['mint','rose','blue'].includes(n.cover_tone)?n.cover_tone:'mint';
 return `<div class="reader-cover ${tone} ${large?'large':''}" role="img" aria-label="耳机主题示意封面"><span>${esc(n.topic||'耳机日常')}</span><div class="reader-headphones"><i></i><b></b></div><strong>${esc(n.title)}</strong><small>封面示意 · 查看原帖</small></div>`;
}if(n.local_example&&/^\/web\/examples\/[a-z0-9-]+\.png$/.test(n.images?.[0]?.src||''))return `<div class="feed-real-photo fact-card-cover ${large?'large':''}"><img src="${esc(n.images[0].src)}" alt="${esc(n.title)} · 自建资料卡" loading="lazy"></div>`;if(n.real&&!large&&/^\/api\/xhs\/images\/[a-f0-9]{24}\/[0-9]{1,2}$/.test(n.images?.[0]?.src||''))return `<div class="feed-real-photo"><img src="${esc(n.images[0].src)}?v=${esc(n.image_revision||'')}" alt="${esc(n.title)} · 笔记原图" loading="lazy"></div>`;return n.real?`<div class="real-note-cover ${large?'large':''}"><span>真实笔记</span><b>${esc(n.title)}</b><small>真实笔记 · 原文已读取</small></div>`:n.demo?`<div class="${large?'note-photo-v2':'feed-photo'} ${esc(n.photoClass)}" role="img" aria-label="${esc(n.photoLabel)}"></div>`:`<div class="perfume-art palette-${n.palette||0} ${large?'large':''}" role="img" aria-label="香水示意封面"><span class="art-kicker">SCENT DIARY</span><div class="bottle"><i></i><span>${esc(n.coverLabel||'EAU DE PARFUM')}<b>香 气 日 记</b></span></div><small>封面示意 · 本地收录笔记</small></div>`}
export function feedCard(n){return `<button type="button" class="feed-card pressable" data-action="note" data-id="${esc(n.note_id)}">${cover(n)}<span class="feed-title">${esc(n.title)}</span><span class="feed-meta"><i class="feed-avatar avatar-${(n.palette||0)%6+1}"></i><em>${n.real?esc(n.author||'真实笔记作者'):n.demo?'生活演示':n.curated?esc(n.author||n.source_author||'真实笔记作者'):n.local_example?'自建资料卡':'香水笔记 · 收录'}</em><b>${n.demo?'示意':'↗'}</b></span></button>`}
const nav=`<nav class="xhs-tabbar">${button('home','<i class="tab-home"></i><b>首页</b>','class="is-active"')}<button type="button" data-action="market"><i class="tab-market"></i><b>市集</b></button><button type="button" disabled class="publish-button" aria-label="发布"><i></i></button><button type="button" disabled><i class="tab-message"></i><b>消息</b></button><button type="button" disabled><i class="tab-profile"></i><b>我</b></button></nav>`;
export function home(notes){const curated=notes.filter(n=>n.curated);const sources=new Set(curated.map(n=>n.source_note_id));notes=[...curated,...notes.filter(n=>!n.local_example&&!n.curated&&!sources.has(n.note_id))];return `<section class="screen xhs-screen home-screen xhs-home-v2">${statusBar()}<header class="feed-header"><button class="assistant-entry pressable" data-action="chat" aria-label="进入点点"><span></span><i></i></button><nav>${button('demo','关注')}${button('home','发现','class="is-active"')}${button('demo','附近')}</nav><button class="home-search pressable" data-action="search" aria-label="搜索"><span></span></button></header><main class="xhs-feed"><div class="feed-column">${notes.filter((_,i)=>i%2===0).map(feedCard).join('')}</div><div class="feed-column">${notes.filter((_,i)=>i%2===1).map(feedCard).join('')}</div></main>${nav}<span class="in-phone-label">本地实验</span></section>`}
function diagnostics(r){
 const a=r.agent,actions={ask_user:'追问用户',query_catalog:'查询商品库',search_notes:'搜索笔记',read_note:'读取笔记',finish:'完成回答'};
 const agent=a?`<section class="agent-diagnostics"><b>Agent 行动</b><p>决策 ${esc(a.counts?.decisions)}/${esc(a.limits?.decisions)} · 搜索 ${esc(a.counts?.searches)}/${esc(a.limits?.searches)} · 读取 ${esc(a.counts?.reads)}/${esc(a.limits?.reads)}</p><ol>${(a.events||[]).map(e=>`<li>${esc(actions[e.action]||e.action)}${e.reason?`：${esc(e.reason)}`:''}</li>`).join('')}</ol><p>停止原因：${esc(a.stop_label)}</p>${a.notes?.length?`<details><summary>本次查阅 ${a.notes.length} 篇笔记</summary>${a.notes.map(n=>`<article><a href="${esc(safeUrl(n.source_url))}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a><small>${n.source==='xhs'?'真实笔记':'本地收录'}${n.truncated?' · 展示部分正文':''}${n.unanalysed_images?` · ${esc(n.unanalysed_images)} 张图片尚未分析`:''}</small><p>${br(n.text)}</p></article>`).join('')}</details>`:''}</section>`:'';
 return `<details class="diagnostics"><summary>实验信息 · ${r.mode==='mock'?'模拟':'真实模型'} · ${esc(r.elapsed_ms)} ms${r.cache_hit?' · 已复用缓存':''}</summary>${agent}<p>Token 用量：${esc(JSON.stringify(r.usage||[]))}</p><pre>${esc(JSON.stringify(r.trace||[],null,2))}</pre></details>`;
}
function conditions(req={}){
 const tags=[];
 if(req.budget_deferred)tags.push(['预算待定','修改预算：']);
 if(req.budget_unlimited)tags.push(['预算不限','修改预算：不限']);
 else if(req.budget_max!=null){const budget=req.budget_min!=null?`${req.budget_min}–${req.budget_max}元`:`${req.budget_max}元以内`;tags.push([budget,'修改预算：'+budget]);}
 if(req.use_case)tags.push([req.use_case,'修改场景：'+req.use_case]);
 for(const f of req.attribute_filters||[]){if(f.op!=='remove')tags.push([f.quote||String(f.value),'修改条件：'+(f.quote||String(f.value))]);}
 if(req.preferences?.length)tags.push([req.preferences.join('、'),'修改偏好：'+req.preferences.join('、')]);
 return tags.length?`<div class="condition-tags" aria-label="当前选购条件">${tags.map(([label,text])=>button('edit-condition',esc(label),`data-text="${esc(text)}" title="点击修改条件"`)).join('')}</div>`:'';
}
function noteAnswer(r){
 const note=r.note_analysis;
 if(!note?.summary)return br(r.answer);
 const theme=note.summary.trim();
 const points=(note.key_points||[]).slice(0,3);
 const opinion=note.author_opinion?.trim();
 // The structured note summary replaces the backend's duplicated prose.
 return `<p>${esc(theme)}</p>${points.length?`<ul>${points.map(p=>`<li>${esc(p)}</li>`).join('')}</ul>`:''}${opinion&&!([theme,...points].some(p=>p.includes(opinion)))?`<p class="author-opinion">作者观点：${esc(opinion)}</p>`:''}`;
}
function sourceMarkup(source){
 if(typeof source==='string')return esc(source);
 const fields={scent_family:'香调',suitable_scenarios:'适用场景',key_notes:'香调原料',selling_points:'资料描述',reference_price_cny:'参考价格',actual_spec_value:'实际规格',actual_spec_unit:'规格单位',cautions:'注意事项',concentration:'浓度版本',price_updated_at:'价格更新时间',price_type:'价格类型',brand:'品牌',product_name:'商品名称',category:'商品类别'};
 const label=source?.type==='catalog'?(fields[source.field]||source.label||'商品资料'):source?.type==='note'?'笔记原文':'收录资料';
 const url=safeUrl(source?.source_url);
 return `${esc(label)}：${esc(source?.quote||'未提供原文')}${url!=='#'?` <a href="${esc(url)}" target="_blank" rel="noopener noreferrer">查看来源 ↗</a>`:''}`;
}
function recommendation(p,r){
 const d=(r.recommendation_details||[]).find(d=>d.product_id===p.product_id);
 if(!d)return '';
 return `<section class="product-advice" aria-label="推荐分析">${d.reasons?.length?`<div class="recommendation-reasons"><b>推荐理由</b><ul>${d.reasons.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:''}${d.cautions?.length?`<p class="recommendation-cautions">注意：${d.cautions.map(esc).join('；')}</p>`:''}${d.sources?.length?`<details class="recommendation-sources"><summary>推荐依据</summary><ul>${d.sources.map(x=>`<li>${sourceMarkup(x)}</li>`).join('')}</ul></details>`:''}</section>`;
}
function selectionMarkup(r){
 if(!['READY','NO_RESULT','SELECTION_EXPLANATION'].includes(r.status)||!r.selection_record?.length)return '';
 const statuses={supported:'有支持资料',conflict:'存在冲突',unknown:'资料不足'};
 return `<details class="selection-record"><summary>本轮选择依据</summary><p>只展示本轮实际比较记录；没有依据的偏好保留待确认。</p>${r.selection_record.map(item=>`<article><b>${esc(item.product_name)}${item.selected?` · 第${esc(item.rank)}位`:''}</b><p>${esc(item.decision_reason)}</p>${(item.matches||[]).map(m=>`<p>${esc(m.preference)}：${esc(statuses[m.status]||'待确认')}</p>${[...(m.conflict||[]),...(m.support||[])].map(s=>`<blockquote>${sourceMarkup(s)}</blockquote>`).join('')}`).join('')}</article>`).join('')}</details>`;
}
function attributeMarkup(a){
 const value=typeof a.value==='boolean'?(a.value?'支持':'不支持'):String(a.value??'未知');
 return `<li><b>${esc(a.label||a.key)}</b> ${esc(value)}${esc(a.unit||'')}${a.qualifier?`<small>${esc(a.qualifier)}</small>`:''}</li>`;
}
function productCard(p,r){
 const headphones=p.category==='耳机';
 const facts=(p.attributes||[]).filter(a=>a.verified===true);
 const amount=p.reference_price_cny==null?'价格待核实':`¥${esc(p.reference_price_cny)}`;
 const version=headphones?esc(p.model_identifier||'具体版本见商品名称'):`${esc(p.actual_spec_value??'规格待核实')}${esc(p.actual_spec_unit)}${p.concentration?' · '+esc(p.concentration):''}`;
 return `<article class="product-recommendation"><div class="live-product"><div class="product-heading"><span class="${headphones?'mini-headphones':'mini-bottle'}" aria-hidden="true">${headphones?'♬':''}</span><h3>${esc(p.product_name)}</h3></div>${p.brand?`<p class="product-brand">${esc(p.brand)}</p>`:''}${p.resolution_notice?`<p class="product-resolution">${esc(p.resolution_notice)}</p>`:''}<p><b class="price">${amount}</b><small>${p.reference_price_cny==null?'': '官网价格快照 · '}${version}</small></p>${p.price_variant?`<p class="price-variant">价格对应：${esc(p.price_variant)}款${p.price_checked_at?` · ${esc(p.price_checked_at)}快照`:""}</p>`:""}${headphones?`<ul class="product-attributes">${facts.slice(0,3).map(attributeMarkup).join('')}</ul>`:`<p>${esc(p.scent_family)}</p>`}<details><summary>商品资料与注意事项</summary><p>${esc(p.selling_points)}</p>${headphones?`<ul class="product-attributes">${facts.map(a=>`<li>${attributeMarkup(a).slice(4,-5)} <a href="${esc(safeUrl(a.source_url))}" target="_blank" rel="noopener noreferrer">官方来源 ↗</a></li>`).join('')}</ul>`:''}<p>注意：${esc(p.cautions||'使用体验需要自行确认')}</p><small>${esc(p.price_type||'价格未核实')}${p.price_specification?'<br>'+esc(p.price_specification):''}${p.price_updated_at?' · 核验于 '+esc(p.price_updated_at):''}<br>价格为资料快照，库存未知</small>${p.price_source_url?`<p><a href="${esc(safeUrl(p.price_source_url))}" target="_blank" rel="noopener noreferrer">查看价格来源 ↗</a></p>`:''}</details></div>${recommendation(p,r)}</article>`;
}
function alternativesMarkup(r){
 if(!r.alternatives?.length)return '';
 return `<section class="conditional-alternatives"><h3>有条件的替代选择</h3><p>以下商品不符合当前预算，仅在你愿意调整预算时考虑。</p>${r.alternatives.slice(0,2).map(p=>`<div class="conditional-alternative"><p><b>${esc(p.condition)}</b></p><p class="recommendation-cautions">${esc(p.reason)}</p>${productCard(p,{recommendation_details:[]})}</div>`).join('')}</section>`;
}
function noteProductMarkup(note,products=[],catalog=[]){
 const known=new Map([...catalog,...products,...(note.resolved_products||[])].map(p=>[p.product_id,p]));
 const groups=new Map();
 for(const m of note.mentions||[]){
  let id=m.product_id||m.identity_product_id;
  let product=id?known.get(id):null;
  if(!id&&m.source!=='image_visual'&&m.confidence!=='uncertain'){
   const name=m.name.trim().toLowerCase();
   const identities=catalog.filter(p=>p.verified_for_recommendation===false&&!p.concentration&&[p.product_name,...(p.aliases||'').split(';')].some(a=>a.trim().toLowerCase()===name&&a.trim().length>2&&m.quote?.toLowerCase().includes(a.trim().toLowerCase())));
   if(identities.length===1){product=identities[0];id=product.product_id;}
  }
  if(product?.verified_for_recommendation===false&&!product.concentration){
   product={product_id:product.product_id,product_name:product.product_name,brand:product.brand,category:product.category,reference_price_cny:null,resolution_status:'identity_only',resolution_notice:'仅识别历史名称索引；具体版本、规格和价格尚未核验。'};
  }
  const key=id||m.name.trim().toLowerCase();
  if(!groups.has(key))groups.set(key,{product,mentions:[]});
  groups.get(key).mentions.push(m);
 }
 const render=group=>{
  const mentions=group.product?.mention_evidence||group.mentions;
  const product=group.product||{product_name:group.mentions[0].name,reference_price_cny:null,resolution_notice:group.mentions[0].product_id?'已匹配收录资料；商品详情尚未加载。':'尚未确认具体商品与版本。'};
  const evidence=mentions.map(m=>`<div><small>${m.source?.startsWith('image')?`第 ${esc(m.image_index)} 张图 · ${m.source==='image_visual'?'外观推测':'图片文字'}`:'正文'}</small><blockquote>${esc(m.quote)}</blockquote></div>`).join('');
  return `${productCard(product,{recommendation_details:[]})}<details class="note-product-evidence"><summary>原文依据${mentions.length>1?` · ${mentions.length}处`:''}</summary>${evidence}</details>`;
 };
 const all=[...groups.values()];
 return all.length?`<section class="mention-list"><h3>笔记中的商品</h3>${all.slice(0,3).map(render).join('')}${all.length>3?`<details class="more-mentions"><summary>更多商品（${all.length-3}）</summary>${all.slice(3).map(render).join('')}</details>`:''}</section>`:'';
}
export function resultMarkup(r,catalog=[]){
 const note=r.note_analysis;
 const followup=r.followup_question||'';
 let mainAnswer=followup&&r.answer?.endsWith(followup)?r.answer.slice(0,-followup.length).trimEnd():r.answer;
 if(r.status==='READY'&&r.requirements?.browse_product_ids!=null&&r.products?.length&&mainAnswer?.startsWith('根据当前条件，候选如下：')){
  mainAnswer=mainAnswer.split('\n').filter(line=>!/^\d+\. /.test(line)).join('\n').replace('根据当前条件，候选如下：','找到几款相关商品，先看看价格和差别：');
 }
 const mentions=note?noteProductMarkup(note,r.products||[],catalog):'';
 const observations=note?.image_observations||[];
 const visual=observations.length?`<details class="image-analysis"><summary>图片识别 · ${observations.length} 张</summary>${observations.map(im=>`<article><b>第 ${esc(im.image_index)} 张图</b>${im.ocr_text?`<p class="image-ocr">图片文字：${br(im.ocr_text)}</p>`:''}${im.description?`<p>图片内容：${esc(im.description)}</p>`:''}${im.uncertainty?`<small>待确认：${esc(im.uncertainty)}</small>`:''}</article>`).join('')}</details>`:'';
 const incomplete=note?.image_coverage?.missing||[];
 return `${incomplete.length?`<p class="note-image-warning">第 ${incomplete.map(esc).join('、')} 张图未完成识别；本次结果不包含这些图片。</p>`:''}${conditions(r.requirements)}<div class="result-answer">${noteAnswer({...r,answer:mainAnswer})}</div>${visual}${mentions}${(note?.mentions?.length?[]:r.products||[]).map(p=>productCard(p,r)).join('')}${alternativesMarkup(r)}${followup?`<p class="followup-question">${esc(followup)}</p>`:''}${r.evidence?.length?`<details class="live-evidence"><summary>查看 ${r.evidence.length} 篇关联笔记</summary>${r.evidence.map(n=>`<article>${n.source==='xhs'||n.real?`<a href="${esc(safeUrl(n.source_url))}" target="_blank" rel="noopener noreferrer">${esc(n.title)} ↗</a>`:`<button data-action="note" data-id="${esc(n.note_id)}">${esc(n.title)} ›</button>`}<p>${br(n.text)}</p><a href="${esc(safeUrl(n.source_url))}" target="_blank" rel="noopener noreferrer">查看原始来源 ↗</a></article>`).join('')}</details>`:''}${selectionMarkup(r)}${diagnostics(r)}`;
}
export function pendingLabel(pending,now=Date.now()){
 const stages={queued:'等待处理',running:'正在处理',understand:'理解需求',retrieve:'查找资料',rank_validate:'整理推荐',analyze_note:'分析笔记',answer:'整理回答'};
 const chinese=['读取笔记图片','分析正文与图片','等待处理','正在处理','理解需求','分析笔记','检索并筛选商品','排序并校验候选','整理结果','复用已完成结果','处理完成','Agent 选择下一步','Agent 查询商品库','Agent 搜索笔记','Agent 读取笔记'];
 const imageProgress=/^(?:复用图片识别 \d+\/\d+，待识别 \d+ 张|图片已识别 \d+\/\d+，失败 \d+ 张)$/.test(pending?.stage||'');
 return `${stages[pending?.stage]||((chinese.includes(pending?.stage)||imageProgress)?pending.stage:null)||stages[pending?.status]||'正在处理'} · 已经过 ${Math.max(0,Math.floor((now-(pending?.startedAt||now))/1000))} 秒`;
}
function searchConversation(c,busy,catalog=[]){
 const messages=c?.messages||[];let split=messages.length-1;
 while(split>0&&messages[split]?.role!=='user')split--;
 const older=messages.slice(0,split),recent=messages.slice(split);
 return `${older.length?`<details class="earlier-conversation"><summary>较早的对话（${older.length}条）</summary>${conversation({...c,messages:older},false,catalog)}</details>`:''}${conversation({...c,messages:recent},busy,catalog)}`;
}
export function conversation(c,busy,catalog=[]){return `<div class="messages">${(c?.messages||[]).map(m=>`<article class="chat-message ${esc(m.role)}">${m.role==='user'?`<p>${br(m.text==='总结这篇笔记的重点和作者态度，有商品时自动提取。'?NOTE_SUMMARY_REQUEST:m.text)}</p>`:`<div class="ai-role">${mark}<b>点点</b></div>${m.result?resultMarkup(m.result,catalog):`<p>${br(m.text)}</p>`}`}</article>`).join('')}${c?.recovery&&!busy?`<div class="recovery-input">${button('restore-input','恢复上次请求输入（不自动发送）')}</div>`:''}${busy?`<div class="thinking" role="status"><span></span>${esc(pendingLabel(c?.pending))}</div>`:''}</div>`}
function composer(busy,draft='',images=[],sheet=false,scope='note'){return `<form class="live-composer" data-form="message"><div class="attachment-status">${images.length?`已添加 ${images.length} 张图片 ${button('clear-images','移除')}`:''}</div><div class="composer-row">${sheet?'':`<label class="image-button" title="上传图片" aria-label="上传图片">＋<input type="file" id="images" accept="image/jpeg,image/png,image/webp" multiple ${busy?'disabled':''}></label>`}<textarea id="message" aria-label="${sheet?(scope==='note'?'笔记追问':'继续补充搜索需求'):'向点点提问'}" placeholder="${sheet?(scope==='note'?'针对这篇笔记继续问…':'继续补充预算、场景或偏好…'):'说说你的需求…'}" rows="1" maxlength="6000" >${esc(draft)}</textarea><button type="submit" class="send-button" aria-label="发送" ${busy?'disabled':''}>↑</button></div><small>${sheet?(scope==='note'?'回答基于本篇笔记':'针对本次搜索继续提问'):'内容由 AI 生成 · 价格为收录快照'}</small></form>`}
export function chat({c,busy,draft,images,source,mode,entry,products=[],action='summary'}){return `<section class="screen diandian-native-screen live-chat ${entry==='NOTE'?'note-context-chat':''}">${statusBar()}<header class="native-dd-header">${back()}<div class="native-dd-title"><span class="native-dd-mark"></span><b>点点</b></div>${button('new','新对话','class="new-chat"')}</header><div class="context-strip">${esc(source||'选香水、挑耳机 · 说说你的预算和偏好')}<small>${mode==='mock'?'模拟模式':'真实 AI'}</small></div>${entry==='NOTE'?`<div class="sheet-tools chat-note-tools">${button('note-action','总结这篇',`data-value="summary" class="${action==='summary'?'active':''}" ${busy?'disabled':''}`)}</div>`:''}<main class="chat-scroll" data-scroll="conversation">${c?.messages?.length?conversation(c,busy,products):`${entry==='NOTE'?`<section class="chat-welcome"><div class="welcome-orb">✦</div><h2>带着这篇笔记，继续聊。</h2><p>让点点帮你梳理重点，<br>也可以继续问你关心的内容。</p></section>`:`<section class="chat-welcome"><div class="welcome-orb">✦</div><h2>喜欢的，也要适合你。</h2><p>选香水、挑耳机、看懂笔记，<br>都可以和点点聊聊。</p><div class="welcome-prompts">${button('prompt','1500元内，清新通勤香水 ↗','data-text="预算1500元，想买清新的通勤香水"')}${button('prompt','1000元内，通勤降噪耳机 ↗','data-text="预算1000元，通勤耳机，必须主动降噪"')}${button('prompt','尼罗河花园是什么香调？ ↗','data-text="尼罗河花园是什么香调？"')}${button('prompt','想选香水，还没想好预算 ↗','data-text="想买一瓶通勤香水，喜欢清新的"')}</div><small>香水与耳机 · 支持本地图文示例</small></section>`}${busy?conversation(c,busy,products):''}`}</main>${composer(busy,draft,images,entry==='NOTE')}</section>`}
function searchHeader(q){return `<form class="search-header" data-form="search">${back()}<div class="search-field"><span>⌕</span><input id="query" aria-label="搜索关键词" placeholder="搜笔记、商品或选购需求" maxlength="200" value="${esc(q)}"></div><button class="text-button" type="submit">搜索</button></form>`}
export function search({query='',history=[],realNote={}}){return `<section class="screen xhs-screen search-screen live-search">${statusBar()}${searchHeader(query)}<main class="search-content"><section class="search-section"><div class="section-heading"><h2>历史记录</h2>${button('clear-history','清空')}</div><div class="chip-row">${history.map(q=>button('search-chip',esc(q),`class="history-chip" data-text="${esc(q)}"`)).join('')||'<p class="muted">搜索记录只保存在本地</p>'}</div></section><section class="search-section"><div class="section-heading"><h2>猜你想搜</h2></div><div class="suggestion-grid">${['通勤耳机','WH-CH720N','尼罗河花园','清新香水','耳机','周末野餐'].map(q=>button('search-chip',esc(q),`data-text="${esc(q)}"`)).join('')}</div></section><p class="scope-note">搜索范围：本地收录笔记与演示内容</p></main><section class="search-dd-entry">${button('chat',`${mark}<span><b>问点点｜说说你想买什么</b><small>按预算和偏好，帮你缩小选择</small></span><i>↗</i>`)}</section></section>`}
export function results({query,found,c,busy,draft,shopping,products=[],tab='all'}){return `<section class="screen xhs-screen search-screen results-screen live-results">${statusBar()}${searchHeader(query)}<nav class="results-tabs">${button('tab','综合',`data-value="all" class="${tab==='all'?'is-active':''}"`)}${button('tab','笔记',`data-value="notes" class="${tab==='notes'?'is-active':''}"`)}</nav><main class="results-body" data-scroll="results"><p class="scope-note">本地收录 · 找到 ${found.length} 篇笔记</p>${tab==='all'&&(shopping||c?.messages?.length)?`<section class="search-ai"><div class="results-ai-heading">${mark}<span><b>让点点帮你选</b><small>结合预算、场景和收录资料</small></span>${c?.messages?.length||busy?`<div class="search-session-controls">${button('new','重新开始',busy?'disabled':'')}${button('hide-ai','×','aria-label="收起导购内容"')}</div>`:''}</div>${c?.hidden?`<p>导购内容已收起</p>${button('show-ai',busy?'查看处理进度':'展开上次结果','class="resume-ai"')}`:c?.messages?.length||busy?searchConversation(c,busy,products)+`<div class="full-chat">${button('full-chat','进入点点完整对话 ↗')}</div>`:`<p>想把这些笔记变成适合你的选购建议？</p>${button('search-ai','生成导购建议','class="primary"')}`}</section>`:''}${found.length?`<div class="local-masonry"><div>${found.filter((_,i)=>i%2===0).map(feedCard).join('')}</div><div>${found.filter((_,i)=>i%2===1).map(feedCard).join('')}</div></div>`:`<section class="empty"><span>⌕</span><h3>暂时没有相关笔记</h3><p>当前只搜索本地收录内容，<br>可以换个关键词试试。</p></section>`}</main>${tab==='all'&&!c?.hidden&&(c?.messages?.length||busy)?composer(busy,draft,[],true,'search'):''}</section>`}
export function noteView({n,c,busy,draft,sheet,action='summary',mode,products=[]}){return `<section class="screen xhs-screen note-screen note-screen-v2 live-note">${statusBar()}<header class="note-header">${back()}<span class="note-avatar">${n.curated?esc((n.author||n.source_author||'文').slice(0,1)):n.real?'文':n.demo?'生':n.local_example?'资':'香'}</span><b>${n.curated?esc(n.author||n.source_author||'真实笔记作者'):n.real?esc(n.author||'真实笔记作者'):n.demo?esc(n.author)+' · 演示':n.local_example?'点点 · 自建资料卡':'香水笔记 · 本地收录'}</b>${n.real?'':button('demo','关注','class="follow-button"')}${button('source','↗','class="share-button" aria-label="查看来源"')}</header><main class="note-scroll" data-scroll="note">${(n.real||n.local_example||n.curated)&&n.images?.length?notePictures(n):cover(n,true)}${n.real||n.local_example||n.curated?'':'<div class="photo-pagination"><b></b><i></i></div>'}<article class="note-copy"><h1>${esc(n.title)}</h1><p class="note-body">${br(n.real||n.curated?n.text:(n.displayText||n.text))}</p>${button('open-sheet',`<span class="note-product-label">${mark}<span><b>问点点 · 看懂这篇笔记</b><small>梳理重点，继续聊聊</small></span></span><span>›</span>`,'class="note-product-card"')}${n.real&&n.image_warnings?.length?`<p class="note-image-warning">${n.image_warnings.map(esc).join('<br>')}</p>`:''}<p class="note-meta">${n.curated?`原作者：${esc(n.source_author)}<br>原帖：${esc(n.original_title)}<br><a href="${esc(safeUrl(n.source_url))}" target="_blank" rel="noopener noreferrer">查看原帖 ↗</a>`:n.real?`作者：${esc(n.author||'未提供')}<br>读取时间：${esc(n.fetched_at)}<br><a href="${esc(safeUrl(n.source_url))}" target="_blank" rel="noopener noreferrer">查看真实来源 ↗</a>`:n.demo?'虚构生活演示内容':n.local_example?'自建资料卡 · 官方资料整理，非用户体验笔记':'原笔记整理副本 · 非实时内容'}</p></article><div class="local-comments">${n.demo?'互动数据为原型演示':'未收录评论与互动数据'}</div></main><footer class="note-actions">${button('open-sheet','✦ 问点点')}<span>♡</span><span>☆</span><span>◌</span></footer>${sheet?`<button class="ai-dim" data-action="close-sheet" aria-label="关闭笔记AI面板"></button><section class="note-ai-sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title"><span class="sheet-handle"></span><header><div><h2 id="sheet-title">${mark} 笔记里的点点</h2><p>${esc(n.title)}</p></div><div class="sheet-session-controls">${button('new','重新开始',`class="new-chat" ${busy?'disabled':''}`)}${button('close-sheet','×','class="sheet-close" aria-label="关闭"')}</div></header><div class="sheet-tools">${button('note-action','总结这篇',`data-value="summary" class="${action==='summary'?'active':''}" ${busy?'disabled':''}`)}</div><main class="sheet-content" data-scroll="sheet">${c?.messages?.length||busy?conversation(c,busy,products):`<section class="sheet-empty"><span>✦</span><h3>从这篇笔记，聊起。</h3><p>点击总结这篇，或直接提问。<br>点点会带着本篇内容回答你。</p><small>${mode==='mock'?'模拟模式':'点击操作后调用真实模型'}</small></section>`}</main><div class="full-chat">${button('full-chat','进入点点完整对话 ↗')}</div>${composer(busy,draft,[],true)}</section>`:''}</section>`}

export function realNotePanel(s){
 const disabled=s.busy?'disabled':'';
 return `<section class="real-note-panel"><button type="button" class="real-note-entry" data-action="real-note-toggle" aria-expanded="${!!s.open}"><span><b>真实笔记演示</b><small>粘贴分享链接，导入正文与图片</small></span><i>${s.open?'⌃':'›'}</i></button>${s.open?`<div class="real-note-body"><p class="real-note-status" role="status">${esc(s.status?`${s.status.available?'服务已连接':'服务不可用'} · ${s.status.logged_in===true?'已登录':s.status.logged_in===null?'登录待确认':'未登录'}${s.status.message?' · '+s.status.message:''}`:'尚未检查登录状态')}</p><div class="real-note-tools">${button('real-note-status',s.busy==='status'?'检查中…':'检查登录状态',disabled)}${button('real-note-login',s.busy==='login'?'生成中…':'扫码登录',disabled)}</div>${s.qr?`<div class="real-note-qr"><img src="${esc(s.qr)}" alt="小红书登录二维码"><p>请使用小红书扫码。<br>二维码有效至 ${esc(new Date(s.qrExpires).toLocaleTimeString())}；扫码后点击“检查登录状态”。</p></div>`:''}<form data-form="real-note"><label for="real-note-link">完整分享文案或笔记链接</label><textarea id="real-note-link" rows="4" placeholder="粘贴小红书的完整分享文案…" ${disabled}>${esc(s.draft)}</textarea><button class="primary" type="submit" ${disabled}>${s.busy==='read'?'正在读取正文与图片…':'读取真实笔记'}</button></form>${s.error?`<p class="real-note-error" role="alert">${esc(s.error)}</p>`:''}<p class="real-note-hint">读取正文与图片不调用模型。导入后在手机中点击“总结这篇”，AI 会结合正文、图片文字与商品外观回答。</p></div>`:''}</section>`;
}

function notePictures(n){
 const images=n.images.filter(im=>(n.local_example&&/^\/web\/examples\/[a-z0-9-]+\.png$/.test(im.src||''))||/^\/api\/xhs\/images\/[a-f0-9]{24}\/[0-9]{1,2}$/.test(im.src||''));
 return `<section class="note-picture-gallery" aria-label="笔记原图"><div class="note-picture-track">${images.map(im=>`<figure><img src="${esc(im.src)}?v=${esc(n.image_revision||'')}" alt="笔记第 ${esc(im.index)} 张图片" loading="lazy"><figcaption>第 ${esc(im.index)} 张图</figcaption></figure>`).join('')}</div><p>${n.local_example?'自建资料卡':n.curated?'原帖图片':'原图'} ${images.length}/${esc(n.image_total||images.length)} · 左右滑动查看 · 总结时一起分析</p></section>`;
}

const marketArt=p=>p.category==='香水'?'/web/examples/perfume-gardens.png':p.brand?.includes('Sony')?'/web/examples/sony-headband.png':'/web/examples/airpods-5.png';
function marketCard(p,compact=false){
 return `<article class="market-card ${compact?'compact':''}"><div class="market-art"><img src="${marketArt(p)}" alt=""><small>品类示意</small></div><div><b>${esc(p.product_name)}</b><small>${esc(p.brand)}</small><strong>${p.reference_price_cny==null?'价格待核实':'¥'+esc(p.reference_price_cny)}</strong><small>收录参考价</small></div></article>`;
}
export function market(products){
 const list=products.filter(p=>p.verified_for_recommendation!==false&&p.reference_price_cny!=null);
 return `<section class="screen market-screen">${statusBar()}<header class="market-top">${button('search','⌕　搜索商品','class="market-search"')}${button('market-ai','<span>✦</span> ai购物','class="market-entry"')}</header><div class="market-categories"><b>推荐</b>　穿搭　运动　餐饮　生鲜　潮玩　家居　文玩</div><main data-scroll="market" class="market-scroll"><div class="market-tools">${['🌷|直播广场','🌟|星光夜市','👏|超级合拍','📦|好货市场','💝|宠粉清单','📋|我的订单','🛒|购物车','🎁|小红卡','🎟️|优惠券','🕘|商品足迹'].map(v=>{const [icon,label]=v.split('|');return `<div><i>${icon}</i>${label}</div>`}).join('')}</div><div class="market-grid">${list.map(p=>marketCard(p)).join('')}</div></main>${nav.replace('class="is-active"','').replace('data-action="market"','data-action="market" class="is-active" aria-current="page"')}</section>`;
}
export function marketResult(r){
 if(r.status!=='READY'||!r.products?.length)return resultMarkup(r);
 const groups=new Map();
 for(const p of r.products){
  const wear=p.attributes?.find(a=>a.key==='wearing_style'&&a.verified===true)?.value;
  const key=wear||'可选商品';
  if(!groups.has(key))groups.set(key,[]);
  groups.get(key).push(p);
 }
 const cards=[...groups].map(([label,items])=>`<section>${groups.size>1?`<h3>${esc(label)}</h3>`:''}${items.map(p=>{
  const d=r.recommendation_details?.find(d=>d.product_id===p.product_id);
  const reasons=d?.reasons?.slice(0,2)||[];
  return `<p class="market-reason"><b>${esc(p.product_name)}：</b>${esc(reasons.join('；')||'可先对照这款的参考价和商品资料。')}</p>${marketCard(p,true)}${d?.sources?.filter(s=>s.type==='note'&&s.product_id===p.product_id).slice(0,1).map(s=>`<blockquote>${esc(s.quote)}${safeUrl(s.source_url)!=='#'?` <a href="${esc(safeUrl(s.source_url))}" target="_blank" rel="noopener noreferrer">原帖 ↗</a>`:''}</blockquote>`).join('')||''}`;
 }).join('')}</section>`).join('');
 const hints=r.requirements?.category==='耳机'?['只看入耳式','优先主动降噪']:['偏好清新香调','有没有更便宜的选择'];
 return `<p>先看符合当前条件的款式，再比较各款的差别。</p>${cards}<p><b>注意事项</b><br>价格为收录快照，库存与实际体验需自行确认。</p>${r.followup_question?`<p>${esc(r.followup_question)}</p>`:''}<div class="market-chips">${hints.map(t=>button('prompt',esc(t),`data-text="${esc(t)}"`)).join('')}</div>${diagnostics(r)}`;
}
export function marketChat({c,busy,draft}){
 return `<section class="screen market-screen market-ai">${statusBar()}<header class="market-ai-header">${back()}<b>ai购物</b>${button('new','☰',`aria-label="新对话" ${busy?'disabled':''}`)}</header><main class="market-scroll" data-scroll="conversation">${c?.messages?.length?c.messages.map(m=>m.role==='user'?`<p class="market-user">${br(m.text)}</p>`:`<article class="market-answer">${m.result?marketResult(m.result):br(m.text)}</article>`).join(''):'<p>我是你的私人购物助手。今天有什么想买的东西吗？可以跟我聊聊预算和偏好。</p><small>本地演示 · 香水与耳机</small>'}${busy?`<p role="status">${esc(pendingLabel(c?.pending))}</p>`:c?.recovery?button('restore-input','恢复上次输入'):''}</main><form class="market-composer" data-form="message"><textarea id="message" aria-label="向购物助手提问" placeholder="接着问点什么…" maxlength="6000">${esc(draft)}</textarea><button type="submit" aria-label="发送" ${busy?'disabled':''}>↑</button></form></section>`;
}
