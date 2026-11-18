from diandian.business_evaluation import check_business_result, summarize
from diandian.catalog import Catalog


def test_empty_ready_and_repeated_followup_fail():
    r={'status':'READY','requirements':{},'products':[],'followup_question':'预算多少？','answer':'先看这些'}
    failures=check_business_result({'statuses':['READY'],'products_min':1,'followup_excludes':['预算']},{'entry':'CHAT'},r)
    assert '没有提供候选商品' in failures and '重复追问：预算' in failures


def test_image_quotes_use_their_own_source_and_unknown_cards_do_not_pass_as_matched():
    r={'status':'NOTE_SUMMARY','note_analysis':{'mentions':[{'quote':'WH-CH720N','source':'image_text','image_index':1}],
       'image_observations':[{'image_index':1,'ocr_text':'索尼 WH-CH720N'}],'resolved_products':[]}}
    assert check_business_result({'statuses':['NOTE_SUMMARY']},{'entry':'NOTE','note_context':{'text':''}},r)==[]
    assert '商品资料卡未关联' in check_business_result({'resolved_ids':['H005']},{'entry':'NOTE'},r)


def test_all_supported_categories_are_checked_and_preference_polarity_is_preserved():
    p=next(p for p in Catalog().products if p['category']=='香水')
    r={'status':'READY','requirements':{'category':'耳机','preference_constraints':[{'value':'甜','polarity':'prefer'}]},'products':[p]}
    f=check_business_result({'preference_values':[{'value':'甜','polarity':'avoid'}]},{'entry':'CHAT'},r)
    assert '违反商品品类' in f and '偏好未保留：甜/avoid' in f


def test_incomplete_run_is_not_reported_as_complete_and_usage_is_counted():
    rows=[{'id':'one','complete':False,'turns':[{'failures':[],'result':{'status':'READY','elapsed_ms':100,'usage':[{'input_tokens':10,'output_tokens':2}]}}]}]
    r=summarize(rows,3)
    assert r['completed_cases']==0 and r['passed_cases']==0 and r['total_tokens']==12 and r['planned_cases']==3


def test_verified_typed_fact_is_valid_but_fabricated_fact_fails():
    from diandian.product_facts import fact_sources
    p=next(p for p in Catalog().products if p['product_id']=='H005')
    source=fact_sources(p)[0]
    r={'status':'READY','products':[p],'requirements':{},'recommendation_details':[{'product_id':'H005','sources':[source]}]}
    assert check_business_result({'statuses':['READY']},{'entry':'CHAT'},r)==[]
    source['quote']='凭空编造的参数'
    assert '推荐字段引用无依据' in check_business_result({'statuses':['READY']},{'entry':'CHAT'},r)


def test_hard_attribute_filter_and_missing_live_stock_are_not_ignored():
    p=next(p for p in Catalog().products if p['product_id']=='H004')
    r={'status':'READY','products':[p],'requirements':{'category':'耳机','attribute_filters':[{'key':'anc','op':'eq','value':True,'unit':'','qualifier':''}]}}
    assert '违反客观属性要求' in check_business_result({'statuses':['READY']},{'entry':'CHAT'},r)


def test_dataset_has_fixed_coverage_and_rejects_malformed_business_gates():
    import json,pytest
    from diandian.config import ROOT
    from diandian.business_evaluation import validate_business_cases
    cases=json.loads((ROOT/'evaluations/business-v2.json').read_text())['cases']
    assert len(validate_business_cases(cases))==36
    assert sum(len(c['turns']) for c in cases)==48
    assert sum(c['split']=='holdout' for c in cases)==4
    for expected in ({'statuses':['READY'],'products_min':-1},{'statuses':['READY'],'followup_excludes':'预算'}):
        with pytest.raises(ValueError):validate_business_cases([{'id':'x','turns':[{'entry':'CHAT','message':'耳机','expected':expected}]}])


def test_resolved_cards_cannot_fabricate_prices_or_duplicate_product_identity():
    p=next(p for p in Catalog().products if p['product_id']=='H005')
    r={'status':'NOTE_SUMMARY','note_analysis':{'resolved_products':[{**p,'reference_price_cny':1},{**p}]}}
    f=check_business_result({'statuses':['NOTE_SUMMARY']},{'entry':'NOTE'},r)
    assert '笔记商品卡资料与目录不符' in f and '笔记同一商品重复展示' in f


def test_scene_wrapper_words_are_equivalent_but_negation_is_not():
    r={'status':'READY','requirements':{'use_case':'运动用'},'products':[]}
    assert check_business_result({'requirements':{'use_case':'运动'}},{'entry':'CHAT'},r)==[]
    r['requirements']['use_case']='不是运动用'
    assert '需求未保留：use_case' in check_business_result({'requirements':{'use_case':'运动'}},{'entry':'CHAT'},r)


def test_cancellation_gate_requires_actual_empty_conditions_not_just_ready_status():
    r={'status':'READY','products':[],'requirements':{'attribute_filters':[{'key':'anc','value':False}],'preference_constraints':[{'value':'主动降噪','polarity':'avoid'}]}}
    f=check_business_result({'statuses':['READY'],'requirements_empty':['attribute_filters','preference_constraints']},{'entry':'CHAT'},r)
    assert '条件未撤销：attribute_filters' in f and '条件未撤销：preference_constraints' in f
