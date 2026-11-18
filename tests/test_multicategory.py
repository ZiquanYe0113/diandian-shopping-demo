"""Current production catalog integration; never uses historical price fixtures."""
from diandian.catalog import Catalog
from diandian.model_client import Requirements
from diandian.agent import merge_requirements
from diandian.shopping_logic import qa_answer


def test_headphones_are_a_real_separate_category():
    c=Catalog(); found=c.search({'category':'耳机'})
    assert len(found)==8
    assert all(p['category']=='耳机' for p in found)
    assert all(p['category']=='香水' for p in c.search({'category':'香水'}))


def test_unverified_perfume_prices_are_removed():
    products={p['product_id']:p for p in Catalog().products}
    assert products['P015']['reference_price_cny'] is None
    assert products['P009']['reference_price_cny']==1220
    for p in products.values():
        if p['reference_price_cny'] is not None:
            assert p['price_verified'] and p['price_source_url'].startswith('https://')


def test_unknown_price_does_not_satisfy_budget():
    c=Catalog(); found=c.search({'category':'耳机'})
    unknown={**found[0],'product_id':'unknown-price','reference_price_cny':None,'price_verified':False}
    good,rejected=c.filter(found+[unknown],{'category':'耳机','budget_max':1000})
    assert good and all(p['reference_price_cny'] is not None and p['reference_price_cny']<=1000 for p in good)
    assert 'unknown-price' not in {p['product_id'] for p in good}
    assert any(r['reason']=='实际价格未知' for r in rejected)


def test_anc_false_and_unknown_never_pass_required_anc():
    c=Catalog(); products=c.search({'category':'耳机'})
    unknown={**products[0],'product_id':'unknown','attributes':[]}
    good,_=c.filter(products+[unknown],{'category':'耳机','attribute_filters':[{'key':'anc','op':'eq','value':True,'quote':'必须主动降噪'}]})
    ids={p['product_id'] for p in good}
    assert 'H004' not in ids and 'H006' not in ids and 'unknown' not in ids
    assert {'H001','H003','H005'}<=ids


def test_single_battery_does_not_use_case_total_or_anc_off():
    c=Catalog(); products=c.search({'category':'耳机'})
    req={'category':'耳机','attribute_filters':[{'key':'battery_single','op':'gte','value':5,'unit':'小时','qualifier':'anc_on','quote':'开降噪单次至少5小时'}]}
    good,_=c.filter(products,req); ids={p['product_id'] for p in good}
    assert 'H001' not in ids and 'H002' in ids
    req['attribute_filters'][0]['unit']='分钟'
    assert c.filter(products,req)[0]==[]


def test_switch_category_clears_old_task_conditions():
    old=Requirements(category='香水',budget_max=800,use_case='约会',preferences=['木质'],spec_ml=50,concentration='EDP',target_ids=['P001']).model_dump()
    new=merge_requirements('改买耳机，预算1500元，用来通勤',old,{'category':'耳机'})
    assert new['category']=='耳机' and new['budget_max']==1500
    assert new['use_case']=='通勤' and new['preferences']==[]
    assert new['spec_ml'] is None and not new['concentration'] and not new['target_ids']


def test_headphone_qa_is_typed_not_perfume_shaped():
    c=Catalog(); p=next(p for p in c.products if p['product_id']=='H001')
    answer=qa_answer('主动降噪和续航是多少？',[p],[],c.products)
    assert '4小时' in answer and '主动降噪' in answer
    assert '20小时' in answer and '充电盒' in answer
    assert '毫升' not in answer and '浓度' not in answer


def test_price_verification_needs_official_provenance():
    from diandian.product_facts import normalize
    p=normalize({'product_id':'fake','price_verified':True,'reference_price_cny':99,'price_source_url':'https://example.com/price','price_source_quote':'99'})
    assert p['reference_price_cny'] is None and not p['price_verified']


def test_model_cannot_add_hard_attribute_from_unquoted_text():
    old=Requirements(category='耳机',budget_max=1500).model_dump()
    updates={'attribute_filters':[{'key':'anc','value':True,'op':'eq','quote':'笔记说必须降噪'}]}
    assert merge_requirements('只是想通勤听歌',old,updates,semantic_only=True)['attribute_filters']==[]


def test_attribute_source_does_not_cross_battery_modes():
    from diandian.product_facts import fact_sources
    from diandian.preferences import validate_interpretations
    c=Catalog();p=next(p for p in c.products if p['product_id']=='H001')
    req=Requirements(preference_constraints=[{'attribute':'续航','value':'长','polarity':'prefer','strength':'soft','quote':'希望续航长'}]).model_dump()
    facts=fact_sources(p); on=next(f for f in facts if '4小时' in f['quote']);off=next(f for f in facts if '6小时' in f['quote'])
    claim={'product_id':'H001','attribute':'续航','value':'长','presence':'present','source_type':'catalog','field':on['field'],'quote':off['quote']}
    assert validate_interpretations([claim],req,[p],[],c.products)==[]
    claim['quote']=on['quote']
    assert len(validate_interpretations([claim],req,[p],[],c.products))==1


def test_headphone_variants_match_only_when_identified():
    from diandian.note_analysis import matching_products
    c=Catalog()
    assert {p['product_id'] for p in matching_products('AirPods 5 USB-C充电盒款',c.products)}=={'H001'}
    assert {p['product_id'] for p in matching_products('AirPods 5',c.products)}=={'H001','H002'}
    # Perfume concentration elsewhere in the note must not hide the headphone.
    assert 'H005' in {p['product_id'] for p in matching_products('WH-CH720N与一瓶EDT',c.products)}


def test_mock_bounded_agent_recommends_verified_headphones(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    try:
        r=e.run({'entry':'SEARCH','message':'1000元耳机，用来通勤，必须主动降噪'})
        assert r['status']=='READY'
        assert {p['product_id'] for p in r['products']}=={'H001','H005','H007'}
        assert '毫升' not in r['answer'] and '浓度' not in r['answer']
        switched=e.run({'entry':'CHAT','message':'改买香水，预算1500元，通勤清新','session_id':r['session_id']})
        assert switched['requirements']['attribute_filters']==[]
        assert switched['status']=='READY' and all(p['category']=='香水' for p in switched['products'])
    finally:e.close()


def test_local_image_example_runs_without_mcp(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'s.db',mode='mock')
    try:
        from diandian.local_examples import notes as internal_image_fixtures
        note=next(n for n in internal_image_fixtures() if n['product_ids']==['H001'])
        images=e.note_image_loader(note['note_id'])
        assert len(images)==1 and images[0]['data_url'].startswith('data:image/png;base64,')
        r=e.run({'entry':'NOTE','note_action':'summary','message':'帮我看看这篇在说什么','note_context':{k:note[k] for k in ('note_id','title','text')}})
        assert r['status']=='NOTE_SUMMARY' and r['note_analysis']['image_coverage']['provided']==[1]
        assert '模拟' in r['note_analysis']['image_observations'][0]['uncertainty']
    finally:e.close()


def test_switch_mentioning_rejected_old_category_does_not_reverse_switch():
    old=Requirements(category='香水',budget_max=800,preferences=['木质']).model_dump()
    r=merge_requirements('不买香水了，改买耳机，预算1500元，通勤用',old)
    assert r['category']=='耳机' and r['preferences']==[]


def test_alias_specificity_never_hides_a_different_product_subject():
    from diandian.note_analysis import matching_products
    from diandian.preferences import unique_version_product
    c=Catalog();quote='AirPods 5 USB-C充电盒款续航短，Sony WH-CH720N续航很长。'
    assert {p['product_id'] for p in matching_products(quote,c.products)}=={'H001','H005'}
    assert unique_version_product(quote,c.products) is None


def test_multiple_battery_modes_and_range_bounds_all_survive_merge():
    msg='必须开降噪单次至少5小时，关闭降噪单次至少6小时'
    filters=[{'key':'battery_single','op':'gte','value':5,'unit':'小时','qualifier':'anc_on','quote':'开降噪单次至少5小时'}, {'key':'battery_single','op':'gte','value':6,'unit':'小时','qualifier':'anc_off','quote':'关闭降噪单次至少6小时'}]
    req=merge_requirements(msg,Requirements(category='耳机',budget_unlimited=True).model_dump(),{'attribute_filters':filters},semantic_only=True)
    assert len(req['attribute_filters'])==2
    c=Catalog();good,_=c.filter(c.search(req),req)
    assert 'H001' not in {p['product_id'] for p in good} and 'H002' in {p['product_id'] for p in good}


def test_named_model_switch_does_not_restore_old_perfume_preferences(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'s.db',mode='mock')
    try:
        old=Requirements(category='香水',budget_max=1500,use_case='约会',preferences=['木质'],strict_preferences=['不甜'],spec_ml=50,concentration='EDP').model_dump()
        r=e.understand({'request':{'entry':'CHAT','message':'改买 AirPods5，预算1500元，通勤'},'requirements':old})
        assert r['requirements']['category']=='耳机'
        assert r['requirements']['preferences']==[] and r['requirements']['strict_preferences']==[]
    finally:e.close()


def test_same_family_two_qualified_skus_cannot_share_experience():
    from diandian.note_analysis import matching_products
    from diandian.preferences import unique_version_product
    c=Catalog();q='AirPods 5 USB-C充电盒款续航短，AirPods 5无线充电盒款续航很长。'
    assert {p['product_id'] for p in matching_products(q,c.products)}=={'H001','H002'}
    assert unique_version_product(q,c.products) is None


def test_numeric_equality_allows_json_float_but_bool_is_separate():
    c=Catalog();p=next(p for p in c.products if p['product_id']=='H001')
    req=Requirements(category='耳机',attribute_filters=[{'key':'battery_single','op':'eq','value':4,'unit':'小时','qualifier':'anc_on','quote':'开降噪单次4小时'}]).model_dump()
    assert c.filter([p],req)[0]==[p]
    req['attribute_filters'][0].update(key='anc',value=1.0,unit='',qualifier='')
    assert c.filter([p],req)[0]==[]


def test_battery_threshold_without_codec_cannot_choose_better_codec():
    c=Catalog();p=next(p for p in c.products if p['product_id']=='H007')
    req={'category':'耳机','attribute_filters':[{'key':'battery_single','op':'gte','value':8.5,'unit':'小时','qualifier':'anc_on','quote':'开降噪单次至少8.5小时'}]}
    assert c.filter([p],req)[0]==[]


def test_fixed_headphone_budget_correction_does_not_ask_scent(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'s.db',mode='mock')
    try:
        e.model.understand=lambda *a,**k:{'route':'CLARIFY','requirements':Requirements(category='耳机',budget_max=1500,use_case='通勤').model_dump(),'clarification_question':'预算多少？','summary':''}
        r=e.understand({'request':{'entry':'CHAT','message':'1500元耳机通勤'}})
        assert r['route']=='READY'
        full=e.run({'entry':'CHAT','message':'1500元耳机通勤'})
        assert '香调' not in full['followup_question'] and '佩戴' in full['followup_question']
    finally:e.close()


def test_observed_model_json_key_marker_is_syntax_only():
    from diandian.agent_contract import AgentDecision
    from pydantic import ValidationError
    import pytest
    # Frozen failure recovered from LangGraph error record: all attribute keys had ':'.
    raw={'action':'finish','product_ids':['H001'],'requirements':{'attribute_filters':[{':key':'anc',':op':'eq',':value':True,':unit':'',':qualifier':'',':quote':'必须主动降噪'}]}}
    d=AgentDecision.model_validate(raw)
    assert d.requirements.attribute_filters[0].key=='anc'
    req=merge_requirements('必须主动降噪',Requirements(category='耳机').model_dump(),d.requirements.model_dump(exclude_unset=True),semantic_only=True)
    assert req['attribute_filters'][0]['value'] is True
    raw['requirements']['attribute_filters'][0]['key']='wearing_style'
    with pytest.raises(ValidationError):AgentDecision.model_validate(raw)
    with pytest.raises(ValidationError):AgentDecision.model_validate({'action':'delete_catalog'})


def test_catalog_change_invalidates_confirmed_old_price_cache(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    try:
        first=e.run({'entry':'CHAT','message':'1000元耳机，通勤'})
        assert first['products']
        selected=first['products'][0]['product_id']
        next(p for p in e.catalog.products if p['product_id']==selected)['reference_price_cny']=1999
        r=e.run({'entry':'CHAT','message':'是的','session_id':first['session_id']})
        assert r['cache_hit'] is False and selected not in {p['product_id'] for p in r['products']}
        assert all(p['reference_price_cny']<=1000 for p in r['products'])
    finally:e.close()
