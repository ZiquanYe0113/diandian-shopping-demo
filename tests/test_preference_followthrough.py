"""Regression cases from the full preference answer, not just its question."""
from diandian.agent import merge_requirements,missing_fields
from diandian.model_client import Requirements
from diandian.workflow import Engine
import pytest


def test_vague_battery_priority_never_becomes_an_invented_numeric_filter():
    r=merge_requirements('入耳式 看重续航',Requirements(category='耳机').model_dump(),{
        'attribute_filters':[
            {'key':'wearing_style','value':'in-ear','quote':'入耳式'},
            {'key':'battery_single','op':'gte','value':5,'unit':'小时','qualifier':'anc_off','quote':'看重续航'}]},semantic_only=True)
    assert not any(f['key']=='battery_single' for f in r['attribute_filters'])
    assert r['attribute_filters'][0]['value']=='入耳式'
    assert any('续航' in c['quote'] for c in r['preference_constraints'])
    assert 'preferences' not in missing_fields(r)


def test_legacy_session_filters_are_revalidated_before_next_recommendation():
    old=Requirements(category='耳机',use_case='运动',attribute_filters=[
        {'key':'wearing_style','value':'in-ear','quote':'入耳式'},
        {'key':'battery_single','op':'gte','value':5,'unit':'小时','qualifier':'anc_off','quote':'看重续航'}]).model_dump()
    r=merge_requirements('还有别的推荐吗',old,semantic_only=True)
    assert [f['value'] for f in r['attribute_filters']]==['入耳式']
    assert any('续航' in c['quote'] for c in r['preference_constraints'])


def test_unrelated_budget_number_does_not_erase_vague_battery_priority():
    r=merge_requirements('预算2000元，看重续航',Requirements(category='耳机').model_dump(),{
        'attribute_filters':[{'key':'battery_single','op':'gte','value':5,'unit':'小时','quote':'预算2000元，看重续航'}]},semantic_only=True)
    assert r['attribute_filters']==[]
    assert r['preference_constraints'][0]['strength']=='soft'


@pytest.mark.parametrize('raw,want',[
    ({'key':'battery_single','op':'gte','value':30,'unit':'小时','qualifier':'anc_on','quote':'开降噪单次至少5小时，含盒总计30小时'},None),
    ({'key':'battery_single','op':'gte','value':5,'unit':'小时','qualifier':'anc_on','quote':'不开降噪单次至少5小时'},'anc_off'),
    ({'key':'battery_single','op':'gte','value':8,'unit':'小时','qualifier':'anc_off','quote':'单次至少8小时'},''),
    ({'key':'battery_single','op':'gte','value':5,'unit':'小时','qualifier':'anc_on','quote':'单次至少5小时（开启降噪）'},'anc_on'),
    ({'key':'battery_single','op':'gte','value':5,'unit':'小时','qualifier':'anc_on','quote':'单次至少5小时，开启降噪时'},'anc_on'),
    ({'key':'battery_single','op':'gte','value':9,'unit':'小时','qualifier':'ambient_off','quote':'不开启环境声单次至少9小时'},'ambient_off'),
    ({'key':'battery_single','op':'gte','value':8,'unit':'小时','qualifier':'anc_on_spatial','quote':'启用空间音频并开启降噪单次至少8小时'},'anc_on_spatial'),
    ({'key':'battery_single','op':'gte','value':8,'unit':'小时','qualifier':'anc_on','quote':'运动耳机，开启降噪单次至少8小时'},'anc_on'),
    ({'key':'battery_single','op':'gte','value':8,'unit':'小时','qualifier':'anc_on','quote':'开启降噪，关闭空间音频，单次至少8小时'},'anc_on'),
])
def test_numeric_grounding_distinguishes_scope_and_negated_test_mode(raw,want):
    from diandian.product_facts import grounded_filter
    result=grounded_filter(raw)
    if want is None:assert result is None
    else:assert result['qualifier']==want


def test_missing_budget_is_asked_before_a_query_instead_of_false_no_result(tmp_path):
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    e.model.decide_agent=lambda c:{'action':'query_catalog','requirements':{'category':'耳机','use_case':'运动','attribute_filters':[{'key':'wearing_style','value':'in-ear','quote':'入耳式'}]}}
    try:
        r=e.run({'entry':'CHAT','message':'运动耳机，入耳式，看重续航'})
        assert r['status']=='CLARIFY' and '预算' in r['answer']
        assert r['agent']['observations']==[]
        assert r['requirements']['attribute_filters'][0]['value']=='入耳式'
    finally:e.close()


def test_answering_new_fields_does_not_exhaust_conversation_budget(tmp_path):
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    def decide(c):
        return {'action':'query_catalog' if not c['observations'] else 'finish',
                'requirements':{'attribute_filters':[{'key':'wearing_style','value':'in-ear','quote':'入耳式'}]} if '入耳式' in c['request']['message'] else {}}
    e.model.decide_agent=decide
    try:
        a=e.run({'entry':'CHAT','message':'耳机'})
        sid=a['session_id']
        b=e.run({'entry':'CHAT','message':'不限','session_id':sid})
        c=e.run({'entry':'CHAT','message':'运动','session_id':sid})
        assert a['status']=='CLARIFY' and b['status']==c['status']=='READY'
        r=e.run({'entry':'CHAT','message':'入耳式 看重续航','session_id':sid})
        assert r['status']=='READY' and r['products']
        assert all(p['product_id'] in ('H003','H006','H007') for p in r['products'])
        e.model.decide_agent=lambda c:{'action':'ask_user','ask_field':'budget'}
        again=e.run({'entry':'CHAT','message':'预算改成2500元，运动耳机有没有别的推荐','session_id':sid})
        assert again['agent']['stop_reason']!='clarification_limit'
    finally:e.close()


def test_unexecuted_query_is_not_reported_as_no_matching_products(tmp_path):
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    e.model.decide_agent=lambda c:{'action':'finish','finish_route':'NO_RESULT','requirements':{'category':'耳机','budget_max':2000,'use_case':'运动'}}
    try:
        r=e.run({'entry':'CHAT','message':'2000元运动耳机'})
        assert r['status']=='INCOMPLETE'
        assert '当前商品库没有符合' not in r['answer']
    finally:e.close()


def test_noop_preference_echo_keeps_original_user_evidence():
    from diandian.preferences import update_preferences
    old={'preferences_structured':True,'preference_constraints':[{'attribute':'续航','value':'长','polarity':'prefer','strength':'soft','quote':'我看重长续航'}]}
    req={**old,'preference_updates':[{'attribute':'续航','value':'长','polarity':'prefer','strength':'soft','operation':'upsert','quote':'还有别的推荐吗'}]}
    r=update_preferences('还有别的推荐吗',req,old,semantic_only=True)
    assert r['preference_constraints'][0]['quote']=='我看重长续航'


def test_fixed_workflow_keeps_recovered_soft_priority(tmp_path):
    e=Engine(tmp_path/'s.db',mode='mock')
    e.model.mode='real'
    e.model.understand=lambda *a,**kw:{'route':'READY','requirements':{'category':'耳机','budget_unlimited':True,'use_case':'运动','attribute_filters':[{'key':'battery_single','op':'gte','value':5,'unit':'小时','quote':'看重续航'}]}}
    try:
        r=e.understand({'request':{'entry':'CHAT','message':'运动耳机，预算不限，看重续航'},'requirements':{}})
        assert r['requirements']['attribute_filters']==[]
        assert r['requirements']['preference_constraints'][0]['strength']=='soft'
    finally:e.close()


@pytest.mark.parametrize('message',['那运动耳机有没有别的推荐','其他款可以推荐吗','再推荐几款，改成头戴包耳式'])
def test_alternatives_exclude_previous_choices_and_still_understand_new_preferences(tmp_path,message):
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    try:
        first=e.run({'entry':'CHAT','message':'2000元运动耳机'})
        previous={p['product_id'] for p in first['products']}
        def decide(ctx):
            return {'action':'query_catalog' if not ctx['observations'] else 'finish',
                    'requirements':{'attribute_filters':[{'key':'wearing_style','value':'over-ear','quote':'头戴包耳式'}]} if '头戴包耳式' in message else {}}
        e.model.decide_agent=decide
        r=e.run({'entry':'CHAT','message':message,'session_id':first['session_id']})
        assert previous<=set(r['requirements']['excluded_product_ids'])
        assert not previous & {p['product_id'] for p in r['products']}
        if '头戴包耳式' in message:
            assert r['requirements']['attribute_filters'][0]['value']=='头戴包耳式'
    finally:e.close()
