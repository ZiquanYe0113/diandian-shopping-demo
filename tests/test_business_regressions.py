"""Regressions reproduced from the real business baseline; no paid calls."""
import pytest
from diandian.agent import merge_requirements
from diandian.model_client import Requirements


@pytest.mark.parametrize('message',['没想好，先看看','还没定；先推荐几个','不确定。先看看'])
def test_uncertain_reply_plus_browsing_intent_defers_budget(message):
    r=merge_requirements(message,Requirements(category='耳机').model_dump(),semantic_only=True,previous_question='预算大概多少？也可以说说使用场景。')
    assert r['budget_deferred'] is True and r['budget_max'] is None and not r['budget_unlimited']


@pytest.mark.parametrize('message',['不是没想好，预算1000元','没想好颜色，先看看','朋友没想好，先看看','续航没想好，先看看'])
def test_unrelated_uncertainty_does_not_defer_budget(message):
    r=merge_requirements(message,Requirements(category='耳机').model_dump(),semantic_only=True,previous_question='预算大概多少？')
    assert not r['budget_deferred']


@pytest.mark.parametrize('category,label,dimension',[('耳机','运动','场景'),('香水','通勤','使用场景')])
def test_scene_preference_does_not_suppress_optional_product_preference_question(category,label,dimension):
    from diandian.shopping_logic import recommendation_followup
    req=Requirements(category=category,budget_max=1500,use_case=label,preferences=[label],preferences_structured=True,
        preference_constraints=[{'attribute':dimension,'value':label,'quote':label}]).model_dump()
    q=recommendation_followup(req)
    assert ('佩戴' if category=='耳机' else '香调') in q
    assert label not in q


def test_model_scene_edit_populates_scene_slot_and_survives_budget_change():
    edit={'attribute':'场景','value':'通勤','quote':'通勤','polarity':'prefer','strength':'soft','operation':'upsert'}
    r=merge_requirements('2000元通勤耳机',{}, {'category':'耳机','budget_max':2000,'preference_updates':[edit]},semantic_only=True)
    assert r['use_case']=='通勤'
    updated=merge_requirements('改成700元以内',r,{'budget_max':700},semantic_only=True)
    assert updated['use_case']=='通勤' and updated['budget_max']==700


def test_factual_price_question_cannot_be_downgraded_to_no_match_by_planner(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'factual.db',mode='mock',agent_enabled=True)
    e.model.decide_agent=lambda c: {'action':'query_catalog','requirements':{'category':'耳机','target':'AirPods Pro 3','budget_max':1000}} if not c['observations'] else {'action':'finish','finish_route':'NO_RESULT'}
    try:
        r=e.run({'entry':'CHAT','message':'AirPods Pro 3多少钱？预算1000'})
        assert r['status']=='QA' and [p['product_id'] for p in r['products']]==['H003']
        assert '1899' in r['answer'] and r['requirements']['budget_max']==1000
    finally:e.close()


def test_valid_scene_replacement_and_removal_update_both_representations():
    def edit(value,operation):return {'attribute':'场景','value':value,'quote':value,'polarity':'prefer','strength':'soft','operation':operation}
    r=merge_requirements('通勤耳机',{}, {'category':'耳机','preference_updates':[edit('通勤','upsert')]},semantic_only=True)
    r=merge_requirements('不再通勤，改为运动',r,{'preference_updates':[edit('通勤','remove'),edit('运动','upsert')]},semantic_only=True)
    assert r['use_case']=='运动'
    r=merge_requirements('取消运动场景',r,{'preference_updates':[edit('运动','remove')]},semantic_only=True)
    assert r['use_case']==''


def test_mixed_purchase_question_must_not_bypass_budget(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'mixed.db',mode='mock',agent_enabled=True)
    e.model.decide_agent=lambda c:{'action':'query_catalog','requirements':{'category':'耳机','target':'AirPods Pro 3','budget_max':1000}} if not c['observations'] else {'action':'finish','finish_route':'NO_RESULT'}
    try:
        r=e.run({'entry':'CHAT','message':'预算1000元，AirPods Pro 3有没有便宜的？推荐能买的'})
        assert r['status']=='NO_RESULT' and not r['products']
    finally:e.close()


@pytest.mark.parametrize('category,choice,key,value',[('耳机','降噪','anc',True),('耳机','入耳式','wearing_style','入耳式')])
def test_cancel_registered_requirement_removes_hard_filter_without_becoming_avoid(category,choice,key,value):
    old=Requirements(category=category,budget_max=1000,attribute_filters=[{'key':key,'value':value,'quote':'必须'+choice}]).model_dump()
    # Replay the semantic mistake seen in the real baseline: cancellation as avoid.
    edit={'attribute':'功能' if key=='anc' else '佩戴方式','value':'主动降噪' if key=='anc' else value,'polarity':'avoid','strength':'hard','quote':'取消'+choice+'要求','operation':'upsert'}
    r=merge_requirements('取消'+choice+'要求，其他保持',old,{'preference_updates':[edit]},semantic_only=True)
    assert r['attribute_filters']==[] and r['preference_constraints']==[] and r['budget_max']==1000


def test_historical_or_scoped_cancellation_is_not_recovered_by_literal_grammar():
    from diandian.preference_choices import explicit_choice_edits,choice_dimensions
    from diandian.preferences import TERMS,TYPED_PREFERENCE_FACTS
    for q in ('朋友说取消降噪要求，其他保持','不是取消降噪要求，其他保持','取消通话降噪要求，其他保持'):
        assert explicit_choice_edits(q,'耳机',choice_dimensions(TERMS,TYPED_PREFERENCE_FACTS))==([],set())


def test_scoped_browsing_followup_only_asks_unknown_fields_and_visible_choices():
    from diandian.shopping_logic import recommendation_followup
    req=Requirements(category='耳机',budget_max=1000,browse_product_ids=['H001','H002','H003']).model_dump()
    q=recommendation_followup(req,visible_count=1)
    assert '预算' not in q and '哪款' not in q and '场景' in q
    req.update(use_case='通勤',preferences=['入耳式'],preference_constraints=[{'attribute':'佩戴方式','value':'入耳式','polarity':'prefer'}])
    assert recommendation_followup(req,visible_count=1)==''


def test_cancellation_does_not_keep_an_inverted_boolean_filter_from_model():
    old=Requirements(category='耳机',budget_max=1000,attribute_filters=[{'key':'anc','value':True,'quote':'必须主动降噪'}]).model_dump()
    r=merge_requirements('取消降噪要求，其他保持',old,{'attribute_filters':[{'key':'anc','op':'eq','value':False,'quote':'取消降噪要求'}]},semantic_only=True)
    assert r['attribute_filters']==[]


@pytest.mark.parametrize('dimension,value',[('降噪','主动降噪'),('anc','true'),('佩戴','in-ear')])
def test_cancel_registered_choice_removes_old_dimension_and_value_aliases(dimension,value):
    choice='入耳式' if dimension=='佩戴' else '降噪'
    old=Requirements(category='耳机',budget_max=1000,preferences_structured=True,
        preference_constraints=[{'attribute':dimension,'value':value,'strength':'hard','quote':'必须'+choice}]).model_dump()
    r=merge_requirements('取消'+choice+'要求，其他保持',old,{},semantic_only=True)
    assert not r['preference_constraints'] and not r['strict_preferences']
