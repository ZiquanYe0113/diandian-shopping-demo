import test from 'node:test';
import assert from 'node:assert/strict';
import {resultMarkup,noteView} from '../web/xhs/views.js';
import {searchLocalNotes} from '../web/xhs/state.mjs';
const earphone={product_id:'H001',category:'耳机',product_name:'测试耳机',reference_price_cny:null,price_type:'未核实',attributes:[{key:'anc',label:'主动降噪',value:true,verified:true,source_quote:'ANC',source_url:'https://www.apple.com.cn/specs',qualifier:'仅聆听降噪'}]};
test('earphone card shows unknown price and typed facts without perfume units',()=>{
 const html=resultMarkup({answer:'候选',products:[earphone]});
 assert.match(html,/价格待核实/);assert.match(html,/主动降噪/);assert.match(html,/仅聆听降噪/);
 assert.ok(!html.includes('¥未知')&&!html.includes('ml')&&!html.includes('浓度')&&!html.includes('mini-bottle'));
});
test('earphone attribute labels and source links are escaped',()=>{
 const html=resultMarkup({products:[{...earphone,attributes:[{...earphone.attributes[0],label:'<script>x</script>',source_url:'javascript:bad()'}]}],recommendation_details:[{product_id:'H001',sources:[{type:'catalog',field:'attributes.0',label:'<img onerror=bad>',quote:'<x>',source_url:'javascript:bad()'}]}]});
 assert.ok(!html.includes('<script>')&&!html.includes('<img onerror')&&!html.includes('href="javascript:'));
});
test('generic category searches stay within category-linked notes',()=>{
 const products=[{product_id:'P001',category:'香水',product_name:'尼罗河',aliases:'尼罗河'},{product_id:'H001',category:'耳机',product_name:'WH-CH520',aliases:'WH-CH520'}];
 const notes=[{note_id:'p',title:'资料A',text:'',product_ids:['P001']},{note_id:'h',title:'资料B',text:'',product_ids:['H001']}];
 assert.deepEqual(searchLocalNotes('通勤香水',notes,products).map(n=>n.note_id),['p']);
 assert.deepEqual(searchLocalNotes('耳机',notes,products).map(n=>n.note_id),['h']);
});
test('local image note displays original fact card without claiming consumer review',()=>{
 const html=noteView({n:{local_example:true,note_id:'local:airpods-5',title:'资料卡',text:'官方参数',images:[{index:1,src:'/web/examples/airpods-5.png'}]},sheet:false});
 assert.ok(html.includes('/web/examples/airpods-5.png'));assert.match(html,/自建资料卡/);
 assert.ok(!html.includes('香水笔记 · 本地收录'));
});

test('home hides internal fact cards while keeping reader-style notes',async()=>{
 const {home}=await import('../web/xhs/views.js');
 const html=home([{note_id:'local:internal',title:'INTERNAL FACT CARD',text:'',local_example:true,product_ids:[]},{note_id:'curated:test',title:'跑步时到底要不要隔音',text:'',curated:true,product_ids:[]}]);
 assert.ok(!html.includes('INTERNAL FACT CARD')&&!html.includes('local:internal'));
 assert.ok(html.includes('跑步时到底要不要隔音'));
});

test('source note shows original author and source attribution',()=>{
 const html=noteView({n:{note_id:'curated:fit',curated:true,title:'头戴久了怎么样',text:'作者觉得夹耳',source_author:'耳机作者',original_title:'原文标题',source_url:'https://www.xiaohongshu.com/explore/aaaaaaaaaaaaaaaaaaaaaaaa',images:[]},sheet:false});
 assert.ok(html.includes('耳机作者')&&html.includes('原文标题'));
 assert.ok(!html.includes('香水示意封面')&&!html.includes('自建资料卡'));
});

test('source note body never falls back to a stale editorial displayText',()=>{
 const base={note_id:'curated:x',curated:true,title:'原帖标题',source_author:'原作者',source_url:'https://www.xiaohongshu.com/explore/aaaaaaaaaaaaaaaaaaaaaaaa',images:[],displayText:'STALE EDITORIAL SUMMARY'};
 let html=noteView({n:{...base,text:'作者原话\n第二行'},sheet:false});
 assert.ok(html.includes('作者原话<br>第二行')&&!html.includes('STALE EDITORIAL SUMMARY'));
 html=noteView({n:{...base,text:''},sheet:false});
 assert.ok(!html.includes('STALE EDITORIAL SUMMARY'));
});

test('objective preferences are visible in condition chips',()=>{
 const html=resultMarkup({answer:'补充预算',requirements:{attribute_filters:[{key:'wearing_style',value:'入耳式',op:'eq',quote:'入耳式'}]}});
 assert.ok(html.includes('入耳式'));
});

test('optional refinement appears once after product cards, safely escaped',()=>{
 const followup='主要用来通勤还是运动？<script>x</script>';
 const html=resultMarkup({answer:'先看候选。\n'+followup,products:[earphone],followup_question:followup});
 assert.equal(html.split('主要用来通勤还是运动？').length-1,1);
 assert.ok(html.indexOf('class="live-product"')<html.indexOf('主要用来通勤还是运动？'));
 assert.ok(!html.includes('<script>'));
});

test('undecided budget is displayed separately from unlimited and SKU pricing is visible',()=>{
 const html=resultMarkup({answer:'先看看',requirements:{budget_deferred:true},products:[{...earphone,reference_price_cny:298,price_variant:'粉红色'}]});
 assert.ok(html.includes('预算待定')&&!html.includes('预算不限'));
 assert.ok(html.includes('粉红色'));
});

test('curated feed replaces its source entry and escapes provenance text',async()=>{
 const {home}=await import('../web/xhs/views.js');
 const html=home([{note_id:'xhs:a',real:true,title:'ORIGINAL DUPLICATE',text:''},{note_id:'curated:a',curated:true,title:'EDITED ARTICLE',text:'',source_note_id:'xhs:a'}]);
 assert.ok(html.includes('EDITED ARTICLE')&&!html.includes('ORIGINAL DUPLICATE'));
 const escaped=noteView({n:{note_id:'curated:x',curated:true,title:'标题',text:'内容',source_author:'<script>bad</script>',original_title:'<img src=x>',source_url:'javascript:bad()',images:[]},sheet:false});
 assert.ok(escaped.includes('&lt;script&gt;')&&!escaped.includes('<script>')&&!escaped.includes('href="javascript:'));
});
