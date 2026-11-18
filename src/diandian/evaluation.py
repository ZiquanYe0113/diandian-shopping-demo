"""Deterministic gates, distinct from semantic / human quality scoring."""
import re
from .model_client import Requirements
from .catalog import Catalog
RULES={'statuses','requirements','no_products','forbidden_ids','required_ids','mention_min','mention_max','points_max','answer_contains','answer_excludes','cache_hit','category'}

def validate_cases(cases):
    ids=set()
    for case in cases:
        if not case.get('id') or case['id'] in ids or not case.get('turns'): raise ValueError('用例ID重复或无轮次')
        ids.add(case['id'])
        for turn in case['turns']:
            expected=turn.get('expected',{})
            if not expected or set(expected)-RULES: raise ValueError('用例必须包含已知的非空检查标准')
            for key,value in expected.items():
                if key in ('statuses','forbidden_ids','required_ids','answer_contains','answer_excludes') and (not isinstance(value,list) or not all(isinstance(x,str) and x for x in value)): raise ValueError('列表检查标准非法')
                if key=='statuses' and (not value or set(value)-{'READY','CLARIFY','QA','IDENTIFY','CONTENT','OUT_OF_SCOPE','NO_RESULT','NOTE_SUMMARY','NOTE_EXTRACT','ERROR'}): raise ValueError('状态检查标准非法')
                if key=='requirements' and (not isinstance(value,dict) or not value or set(value)-set(Requirements.model_fields)): raise ValueError('需求检查标准不能为空')
                if key in ('no_products','cache_hit') and not isinstance(value,bool): raise ValueError('布尔检查标准非法')
                if key in ('mention_min','mention_max','points_max') and (not isinstance(value,int) or isinstance(value,bool) or value<0): raise ValueError('条数检查标准非法')
            if turn.get('entry') not in ('CHAT','SEARCH','NOTE') or not turn.get('message'): raise ValueError('用例入口或消息非法')
    return cases

def check_result(expected,request,result):
    failures=[]; req=result.get('requirements',{}); products=result.get('products',[])
    if result.get('status')=='ERROR': failures.append('请求失败')
    if expected.get('statuses') and result.get('status') not in expected['statuses']: failures.append('状态不符')
    for field,value in expected.get('requirements',{}).items():
        actual=req.get(field)
        if isinstance(value,list): matched=isinstance(actual,list) and all(v in actual for v in value)
        else: matched=actual==value
        if not matched: failures.append('需求未保留：'+field)
    catalog={p['product_id']:p for p in Catalog().products}
    ids={p['product_id'] for p in products}
    for p in products:
        canonical=catalog.get(p['product_id'])
        if not canonical: failures.append('商品不在目录'); continue
        for field in ('reference_price_cny','actual_spec_value','actual_spec_unit','category','concentration'):
            if p.get(field)!=canonical.get(field): failures.append('商品字段与目录不符：'+field)
    for detail in result.get('recommendation_details',[]):
        pid=detail.get('product_id'); canonical=catalog.get(pid)
        if not canonical or pid not in ids: failures.append('推荐依据商品不在候选'); continue
        for source in detail.get('sources',[]):
            if not isinstance(source,dict) or source.get('type')!='catalog' or source.get('product_id')!=pid or source.get('field') not in canonical or str(canonical.get(source.get('field')))!=source.get('quote'):
                failures.append('推荐字段引用无依据')
    if expected.get('no_products') and products: failures.append('不应生成商品')
    if ids & set(req.get('excluded_product_ids',[])): failures.append('违反换批商品排除')
    if ids & set(expected.get('forbidden_ids',[])): failures.append('出现禁止商品')
    if not set(expected.get('required_ids',[]))<=ids: failures.append('指定商品未出现')
    if expected.get('cache_hit') is not None and result.get('cache_hit',False)!=expected['cache_hit']: failures.append('缓存行为不符')
    for p in products:
        price=p.get('reference_price_cny')
        if result.get('status')=='READY' and not req.get('budget_unlimited'):
            if req.get('budget_max') is not None and (price is None or price>req['budget_max']): failures.append('违反预算上限')
            if req.get('budget_min') is not None and (price is None or price<req['budget_min']): failures.append('违反预算下限')
        category=expected.get('category') or (req.get('category') if req.get('category')=='香水' else None)
        if category and p.get('category')!=category: failures.append('违反商品品类')
        if result.get('status')=='READY' and req.get('must_in_stock') and p.get('availability') not in ('有货','in_stock'): failures.append('未确认实时有货')
        if req.get('spec_ml') and (p.get('actual_spec_unit')!='ml' or p.get('actual_spec_value')!=req['spec_ml']): failures.append('违反规格要求')
        if req.get('concentration') and p.get('concentration','').casefold()!=req['concentration'].casefold(): failures.append('违反浓度版本')
        name=p.get('brand','')+' '+p.get('product_name','')
        if any(x and x.casefold() in name.casefold() for x in req.get('exclude',[])): failures.append('违反品牌排除')
        value=p.get('actual_spec_value'); unit=p.get('actual_spec_unit','')
        if value is not None:
            other='g' if unit=='ml' else 'ml'
            if re.search(r'(?<!\d)'+re.escape(f'{value:g}')+r'\s*'+other+r'\b',result.get('answer','')): failures.append('规格单位错误')
    a=result.get('note_analysis',{}); mentions=a.get('mentions',[])
    if len(a.get('key_points',[]))>expected.get('points_max',999): failures.append('摘要重点过多')
    if len(mentions)<expected.get('mention_min',0) or len(mentions)>expected.get('mention_max',999): failures.append('商品提及数量不符')
    note=request.get('note_context',{}); text=note.get('text','')+'\n'+note.get('title','')
    for m in mentions:
        if not m.get('quote') or m['quote'] not in text: failures.append('商品引文不存在于原文')
    for word in expected.get('answer_contains',[]):
        if word not in result.get('answer',''): failures.append('回答缺少：'+word)
    for word in expected.get('answer_excludes',[]):
        if word in result.get('answer',''): failures.append('回答不应包含：'+word)
    return list(dict.fromkeys(failures))
