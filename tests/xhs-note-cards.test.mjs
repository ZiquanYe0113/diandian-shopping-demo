import test from 'node:test';
import assert from 'node:assert/strict';
import {resultMarkup,results,noteView} from '../web/xhs/views.js';

test('note text and image evidence share one factual gray product card',()=>{
 const p={product_id:'H005',category:'耳机',product_name:'Sony WH-CH720N',brand:'Sony 索尼',reference_price_cny:654,model_identifier:'WH-CH720N',attributes:[{verified:true,key:'anc',label:'主动降噪',value:true}],mention_evidence:[{source:'text',quote:'戴着CH720N'},{source:'image_text',image_index:2,quote:'CH720N'}]};
 const html=resultMarkup({answer:'总结',note_analysis:{mentions:[{name:p.product_name,product_id:'H005',quote:'戴着CH720N'},{name:p.product_name,product_id:'H005',source:'image_text',image_index:2,quote:'CH720N'}],resolved_products:[p]}});
 assert.equal((html.match(/class="live-product"/g)||[]).length,1);
 assert.match(html,/¥654/);assert.match(html,/主动降噪/);assert.match(html,/第 2 张图/);
});
test('historical identity card does not invent verified price or version',()=>{
 const html=resultMarkup({note_analysis:{mentions:[{name:'绿邂逅',identity_product_id:'P016',quote:'绿邂逅'}],resolved_products:[{product_id:'P016',product_name:'邂逅清新香水',brand:'CHANEL 香奈儿',category:'香水',resolution_status:'identity_only',resolution_notice:'具体版本、规格和价格尚未核验。',reference_price_cny:null}]}});
 assert.match(html,/class="live-product"/);assert.match(html,/香奈儿/);assert.match(html,/价格待核实/);assert.match(html,/尚未核验/);assert.doesNotMatch(html,/¥1240/);
});
test('search and note offer scoped reset and search can hide without rendering old answer',()=>{
 const c={messages:[{role:'assistant',text:'之前的结果'}]};
 const visible=results({query:'耳机',found:[],c,shopping:true});
 assert.match(visible,/data-action="new"/);assert.match(visible,/data-action="hide-ai"/);
 const hidden=results({query:'耳机',found:[],c:{...c,hidden:true},shopping:true});
 assert.doesNotMatch(hidden,/之前的结果/);assert.match(hidden,/data-action="show-ai"/);assert.doesNotMatch(hidden,/data-form="message"/);
 const note=noteView({n:{note_id:'n',title:'标题',text:'正文'},c,sheet:true});
 assert.match(note,/data-action="new"/);assert.match(note,/data-action="close-sheet"/);
});

test('old saved note results hydrate matched facts and paused identity without a model call',()=>{
 const catalog=[{product_id:'H005',product_name:'Sony WH-CH720N',category:'耳机',reference_price_cny:654},{product_id:'P016',product_name:'邂逅清新香水',brand:'CHANEL 香奈儿',category:'香水',aliases:'绿邂逅;邂逅清新',verified_for_recommendation:false,concentration:'',reference_price_cny:1240,selling_points:'旧资料'}];
 const html=resultMarkup({note_analysis:{mentions:[{name:'Sony WH-CH720N',product_id:'H005',quote:'Sony WH-CH720N'},{name:'绿邂逅',product_id:null,source:'text',confidence:'confirmed',quote:'我试了绿邂逅'}]}},catalog);
 assert.match(html,/¥654/);assert.match(html,/香奈儿/);assert.match(html,/尚未核验/);
 assert.doesNotMatch(html,/¥1240/);assert.doesNotMatch(html,/旧资料/);
});
