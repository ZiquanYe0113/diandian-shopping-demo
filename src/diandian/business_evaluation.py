"""Business gates over complete workflow outputs, separate from semantic review."""
import statistics,re,copy
from .evaluation import check_result,validate_cases

EXTRA_RULES={'products_min','followup_excludes','preference_values','resolved_ids','resolved_max','alternatives_min','requirements_empty'}

def validate_business_cases(cases):
    validate_cases([{**c,'turns':[{**t,'expected':{k:v for k,v in t['expected'].items() if k not in EXTRA_RULES}} for t in c['turns']]} for c in cases])
    for case in cases:
        for turn in case['turns']:
            for key,value in turn['expected'].items():
                if key in ('products_min','resolved_max','alternatives_min') and (not isinstance(value,int) or isinstance(value,bool) or value<0):raise ValueError('商品数量门槛非法')
                if key in ('followup_excludes','resolved_ids','requirements_empty') and (not isinstance(value,list) or not all(isinstance(v,str) and v for v in value)):raise ValueError('业务列表门槛非法')
                if key=='requirements_empty':
                    from .model_client import Requirements
                    if set(value)-set(Requirements.model_fields):raise ValueError('未知需求字段')
                if key=='preference_values' and (not isinstance(value,list) or not all(isinstance(v,dict) and isinstance(v.get('value'),str) and v['value'] and set(v)<={'attribute','value','polarity','strength'} for v in value)):raise ValueError('偏好门槛非法')
    return cases

def check_business_result(expected,request,result):
    base={k:v for k,v in expected.items() if k not in EXTRA_RULES}
    base=copy.deepcopy(base)
    scene=base.get('requirements',{}).pop('use_case',None)
    failures=check_result(base,request,{**result,'recommendation_details':[]})
    if scene is not None:
        normalize=lambda s:re.sub(r'(?:时使用|使用|用)$','',re.sub(r'^(?:用于|用来)','',s.strip()))
        if normalize(result.get('requirements',{}).get('use_case',''))!=normalize(scene):failures.append('需求未保留：use_case')
    from .catalog import Catalog
    from .preferences import product_sources
    catalog=Catalog().products;byid={p['product_id']:p for p in catalog}
    selected={p['product_id'] for p in result.get('products',[])}
    for detail in result.get('recommendation_details',[]):
        pid=detail.get('product_id');product=byid.get(pid)
        if not product or pid not in selected:failures.append('推荐依据商品不在候选');continue
        allowed=product_sources(product,result.get('evidence',[]),catalog)
        for source in detail.get('sources',[]):
            field=source.get('field');quote=source.get('quote')
            scalar=source.get('type')=='catalog' and field in product and str(product[field])==quote
            sourced=any(all(s.get(k)==source.get(k) for k in ('type','product_id','field','quote','note_id')) for s in allowed)
            if source.get('product_id')!=pid or not (scalar or sourced):failures.append('推荐字段引用无依据')
    # Image quotes are grounded against their own OCR/visual observation, not body text.
    if '商品引文不存在于原文' in failures:
        failures.remove('商品引文不存在于原文')
    analysis=result.get('note_analysis',{})
    observations={o['image_index']:o for o in analysis.get('image_observations',[])}
    for m in analysis.get('mentions',[]):
        source=m.get('source','text')
        ref=(request.get('note_context',{}).get('text','')+'\n'+request.get('note_context',{}).get('title','')) if source=='text' else observations.get(m.get('image_index'),{}).get('ocr_text' if source=='image_text' else 'description','')
        if not m.get('quote') or m['quote'] not in ref:failures.append('商品引文不存在于来源')
    if len(result.get('products',[]))<expected.get('products_min',0):failures.append('没有提供候选商品')
    if len(result.get('alternatives',[]))<expected.get('alternatives_min',0):failures.append('未提供条件式替代方案')
    category=result.get('requirements',{}).get('category')
    if category in ('耳机','香水') and any(p.get('category')!=category for p in result.get('products',[])):failures.append('违反商品品类')
    from .product_facts import attribute_rejection
    if result.get('status')=='READY' and any(attribute_rejection(p,result.get('requirements',{}).get('attribute_filters',[])) for p in result.get('products',[])):
        failures.append('违反客观属性要求')
    for word in expected.get('followup_excludes',[]):
        if word in result.get('followup_question','') or (result.get('status')=='CLARIFY' and word in result.get('answer','')):failures.append('重复追问：'+word)
    for field in expected.get('requirements_empty',[]):
        if result.get('requirements',{}).get(field) not in (None,[], ''):failures.append('条件未撤销：'+field)
    prefs=result.get('requirements',{}).get('preference_constraints',[])
    for pref in expected.get('preference_values',[]):
        if not any(all(p.get(k)==v for k,v in pref.items()) for p in prefs):failures.append('偏好未保留：'+pref['value']+'/'+pref.get('polarity','prefer'))
    cards=analysis.get('resolved_products',[])
    if len({p.get('product_id') for p in cards})!=len(cards):failures.append('笔记同一商品重复展示')
    for card in cards:
        canonical=byid.get(card.get('product_id'))
        if not canonical:failures.append('笔记商品卡不在目录');continue
        if card.get('resolution_status')=='identity_only':
            if card.get('reference_price_cny') is not None or card.get('concentration') or card.get('attributes'):failures.append('历史身份卡冒充核验资料')
        elif any(card.get(k)!=canonical.get(k) for k in ('reference_price_cny','actual_spec_value','actual_spec_unit','concentration','attributes')):
            failures.append('笔记商品卡资料与目录不符')
    if not set(expected.get('resolved_ids',[]))<={p['product_id'] for p in cards}:failures.append('商品资料卡未关联')
    if len(cards)>expected.get('resolved_max',999):failures.append('商品资料卡重复或误关联')
    return list(dict.fromkeys(failures))


def summarize(rows,planned):
    turns=[t for c in rows for t in c['turns']]
    lat=sorted(t['result'].get('elapsed_ms',0) for t in turns)
    usage=[u for t in turns for u in t['result'].get('usage',[])]
    return {'planned_cases':planned,'completed_cases':sum(c['complete'] for c in rows),
        'passed_cases':sum(c['complete'] and all(not t['failures'] for t in c['turns']) for c in rows),
        'turns':len(turns),'passed_turns':sum(not t['failures'] for t in turns),
        'error_turns':sum(t['result'].get('status')=='ERROR' for t in turns),
        'input_tokens':sum(u.get('input_tokens') or 0 for u in usage),'output_tokens':sum(u.get('output_tokens') or 0 for u in usage),
        'total_tokens':sum((u.get('input_tokens') or 0)+(u.get('output_tokens') or 0) for u in usage),
        'model_calls':len(usage),'mean_ms':round(statistics.mean(lat)) if lat else 0,
        'p95_ms':lat[min(len(lat)-1,int(len(lat)*.95))] if lat else 0}
