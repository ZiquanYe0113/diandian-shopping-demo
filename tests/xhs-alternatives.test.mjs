import test from 'node:test';
import assert from 'node:assert/strict';
import {resultMarkup} from '../web/xhs/views.js';

test('conditional alternatives render separately with escaped warnings and no normal budget reasons',()=>{
 const html=resultMarkup({answer:'没有匹配商品',products:[{product_id:'ok',product_name:'正常候选'}],
  alternatives:[{product_id:'alt',product_name:'替代<img>',reference_price_cny:1030,
   condition:'仅在你愿意提高预算时考虑',reason:'超出原预算<script>',mismatches:[{field:'budget_max'}]}],
  recommendation_details:[{product_id:'alt',reasons:['在预算上限800内']}]
 });
 assert.match(html,/有条件的替代选择/);
 assert.match(html,/超出原预算&lt;script&gt;/);
 assert.match(html,/替代&lt;img&gt;/);
 assert.match(html,/仅在你愿意提高预算时考虑/);
 assert.ok(html.indexOf('正常候选')<html.indexOf('有条件的替代选择'));
 assert.doesNotMatch(html,/在预算上限800内/);
});

test('named-product browsing leads with cards instead of duplicating the complete price list',()=>{
 const html=resultMarkup({status:'READY',requirements:{browse_product_ids:['H001','H002'],browse_label:'苹果'},
  answer:'根据当前条件，候选如下：\n1. A｜参考价 ¥999\n2. B｜参考价 ¥1149\n价格和在售状态为资料快照，不是实时库存；缺失属性不视为满足。',
  products:[{product_id:'H001',product_name:'A',reference_price_cny:999},{product_id:'H002',product_name:'B',reference_price_cny:1149}]});
 assert.doesNotMatch(html,/1\. A｜参考价/);
 assert.match(html,/找到几款相关商品/);
 assert.match(html,/<h3>A<\/h3>/);
 assert.match(html,/资料快照/);
});

test('product facts are grouped in a gray card and recommendation is a sibling section',()=>{
 for(const category of ['耳机','香水']){
  const html=resultMarkup({products:[{product_id:'p',product_name:'商品',category,reference_price_cny:999}],recommendation_details:[{product_id:'p',reasons:['符合需求'],cautions:['需要试听']}],followup_question:'主要用来通勤吗？'});
  assert.match(html,/<article class="product-recommendation"><div class="live-product">/);
  assert.match(html,/<\/div><section class="product-advice"/);
  assert.match(html,/符合需求/);
  assert.match(html,/需要试听/);
  assert.match(html,/followup-question/);
 }
});
