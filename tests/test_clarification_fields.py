"""Observed real failure: model asked for a nested product preference."""
import pytest
from pydantic import ValidationError
from diandian.agent_contract import AgentDecision
from diandian.workflow import Engine


@pytest.mark.parametrize('attribute',['wearing_style','connection','anc','battery_single','battery_total','weight','water_rating'])
def test_known_product_attribute_question_is_a_preference_question(attribute):
    d=AgentDecision.model_validate({'action':'ask_user','ask_field':attribute})
    assert d.ask_field=='preferences'


def test_unknown_actions_and_arbitrary_fields_remain_rejected():
    for raw in ({'action':'delete_catalog'},{'action':'ask_user','ask_field':'service_token'}):
        with pytest.raises(ValidationError):AgentDecision.model_validate(raw)


def test_search_to_chat_followup_keeps_budget_and_sport_on_attribute_question(tmp_path):
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    decisions=iter([
        {'action':'ask_user','ask_field':'use_case','requirements':{'category':'耳机'}},
        {'action':'ask_user','ask_field':'wearing_style','requirements':{'category':'耳机','budget_max':1000,'use_case':'运动'}},
        {'action':'finish','product_ids':['H001']},
        {'action':'query_catalog'},
        {'action':'finish','product_ids':['H001']},
    ])
    e.model.decide_agent=lambda context:next(decisions)
    try:
        first=e.run({'entry':'SEARCH','message':'耳机'})
        second=e.run({'entry':'SEARCH','message':'运动 预算1000以下','session_id':first['session_id']})
        assert second['status']=='READY' and '佩戴' in second['followup_question']
        assert '预算' not in second['followup_question']
        assert second['requirements']['budget_max']==1000 and second['requirements']['use_case']=='运动'
        third=e.run({'entry':'SEARCH','message':'先按这些条件推荐吧','session_id':first['session_id']})
        assert third['status']=='READY' and third['products'][0]['product_id']=='H001'
    finally:e.close()


def test_followup_budget_without_yuan_is_not_lost():
    from diandian.agent import merge_requirements
    from diandian.model_client import Requirements
    req=merge_requirements('运动 预算1000以下',Requirements(category='耳机').model_dump(),{'use_case':'运动'},semantic_only=True)
    assert req['budget_max']==1000 and req['use_case']=='运动'


@pytest.mark.parametrize('message',['预算1000以下太少了，改成2000','预算1000元太少了，改成2000','预算1000元，后来改为2000元'])
def test_budget_fallback_does_not_override_explicit_semantic_change(message):
    from diandian.agent import merge_requirements
    from diandian.model_client import Requirements
    r=merge_requirements(message,Requirements(category='耳机',budget_max=1000,use_case='运动').model_dump(),{'budget_max':2000},semantic_only=True)
    assert r['budget_max']==2000
