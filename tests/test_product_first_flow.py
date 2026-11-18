"""Product-first shopping across search/chat; alternatives keep requirements intact."""
import pytest
from diandian.workflow import Engine

@pytest.fixture
def engine(tmp_path):
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    # Reproduce a model trying to ask budget before every query.
    e.model.decide_agent=lambda c: {'action':'ask_user','ask_field':'budget'} if not c['observations'] else {'action':'finish','finish_route':'READY'}
    yield e
    e.close()

@pytest.mark.parametrize('entry',['CHAT','SEARCH'])
@pytest.mark.parametrize('message',['苹果耳机','苹果的耳机','AirPods','airpods'])
def test_known_family_or_brand_shows_cards_before_optional_questions(engine,entry,message):
    r=engine.run({'entry':entry,'message':message})
    assert r['status']=='READY' and len(r['products'])>=2
    assert all('Apple' in p['brand'] for p in r['products'])
    assert r['requirements']['budget_max'] is None
    assert not r['requirements']['budget_unlimited']
    assert '哪款' in r['followup_question']


def test_brand_scope_keeps_budget_and_survives_followup(engine):
    first=engine.run({'entry':'CHAT','message':'苹果耳机'})
    r=engine.run({'entry':'CHAT','message':'1000','session_id':first['session_id']})
    assert r['status']=='READY' and len(r['products'])==1
    assert r['products'][0]['product_id']=='H001'
    assert r['requirements']['budget_max']==1000


def test_exact_named_model_honors_budget_instead_of_bypassing_filter(engine):
    r=engine.run({'entry':'SEARCH','message':'预算1000元，AirPods Pro 3'})
    assert r['status']=='NO_RESULT' and not r['products']
    assert r['alternatives'] and all(p['product_id']=='H003' for p in r['alternatives'])
    assert r['requirements']['budget_max']==1000


def test_no_result_names_products_and_returns_separate_conditional_cards(engine):
    r=engine.run({'entry':'CHAT','message':'600元通勤香水'})
    assert r['status']=='NO_RESULT' and not r['products']
    assert r['alternatives'] and 'P001' not in r['answer']
    assert all(p['reference_price_cny']>600 for p in r['alternatives'])
    assert r['requirements']['budget_max']==600
    restored=engine.session(r['session_id'])['last_result']
    assert restored['alternatives']==r['alternatives']
    next_result=engine.run({'entry':'CHAT','message':'预算2000元','session_id':r['session_id']})
    assert next_result['status']=='READY'
    assert next_result['alternatives']==[]


def test_non_agent_flow_also_browses_named_brand_before_budget(tmp_path):
    e=Engine(tmp_path/'fixed.db',mode='mock')
    try:
        r=e.run({'entry':'SEARCH','message':'苹果耳机'})
        assert r['status']=='READY' and len(r['products'])>=2
        assert all('Apple' in p['brand'] for p in r['products'])
        assert r['requirements']['budget_max'] is None
    finally:e.close()


def test_named_product_price_question_is_answered_even_when_over_budget(engine):
    engine.model.decide_agent=lambda c: {'action':'query_catalog','requirements':{'category':'耳机','target':'AirPods Pro 3','budget_max':1000}} if not c['observations'] else {'action':'finish','finish_route':'QA'}
    r=engine.run({'entry':'CHAT','message':'AirPods Pro 3多少钱，预算1000元'})
    assert r['status']=='QA' and r['products'][0]['product_id']=='H003'
    assert '1899' in r['answer'] and not r['alternatives']


def test_invalid_decision_records_field_path_without_dumping_inputs(engine):
    engine.model.decide_agent=lambda c:{'action':'invented_action','requirements':{'category':'耳机'}}
    r=engine.run({'entry':'CHAT','message':'苹果耳机'})
    assert r['status']=='ERROR'
    assert r['agent']['validation_errors']==[{'field':'action','type':'literal_error'}]


@pytest.mark.parametrize('agent_enabled',[True,False])
def test_excluded_named_model_stays_out_of_family_and_next_budget_turn(tmp_path,agent_enabled):
    e=Engine(tmp_path/'exclusion.db',mode='mock',agent_enabled=agent_enabled)
    try:
        r=e.run({'entry':'CHAT','message':'预算2000元，不要AirPods Pro 3，看看AirPods'})
        assert r['status']=='READY' and all(p['product_id']!='H003' for p in r['products'])
        assert 'H003' in r['requirements']['excluded_product_ids']
        next_result=e.run({'entry':'CHAT','message':'预算3000元','session_id':r['session_id']})
        assert all(p['product_id']!='H003' for p in next_result['products'])
    finally:e.close()

@pytest.mark.parametrize('agent_enabled',[True,False])
def test_unverified_named_product_has_named_reason_not_generic_empty_scope(tmp_path,agent_enabled):
    e=Engine(tmp_path/'unverified.db',mode='mock',agent_enabled=agent_enabled)
    try:
        r=e.run({'entry':'CHAT','message':'蓝风铃'})
        assert r['status']=='NO_RESULT' and not r['products']
        assert '蓝风铃' in r['answer'] and '核验' in r['answer']
        assert 'P013' not in r['answer']
    finally:e.close()

@pytest.mark.parametrize('message,category,target,budget',[
    ('AirPods Pro 3降噪怎么样，预算1000元','耳机','AirPods Pro 3',1000),
    ('AirPods Pro 3续航怎么样，预算1000元','耳机','AirPods Pro 3',1000),
    ('尼罗河花园有哪些香调，预算800元','香水','尼罗河花园',800),
])
def test_exact_product_factual_lookup_is_independent_of_recommendation_budget(engine,message,category,target,budget):
    engine.model.decide_agent=lambda c:{'action':'query_catalog','requirements':{'category':category,'target':target,'budget_max':budget}} if not c['observations'] else {'action':'finish','finish_route':'QA'}
    r=engine.run({'entry':'CHAT','message':message})
    assert r['status']=='QA' and len(r['products'])==1
    assert r['products'][0]['reference_price_cny']>budget
    assert r['requirements']['budget_max']==budget and not r['alternatives']

@pytest.mark.parametrize('agent_enabled',[True,False])
def test_explicit_reconsideration_restores_only_named_product(tmp_path,agent_enabled):
    e=Engine(tmp_path/'reconsider.db',mode='mock',agent_enabled=agent_enabled)
    try:
        r=e.run({'entry':'CHAT','message':'预算2000元，不要AirPods Pro 3，看看AirPods'})
        r=e.run({'entry':'CHAT','message':'还是看看AirPods Pro 3','session_id':r['session_id']})
        assert r['status']=='READY' and [p['product_id'] for p in r['products']]==['H003']
        assert r['requirements']['budget_max']==2000
    finally:e.close()
