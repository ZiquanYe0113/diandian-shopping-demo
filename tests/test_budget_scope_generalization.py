"""The same monetary boundary must survive unrelated unlimited preferences."""
import pytest
from diandian.agent import merge_requirements
from diandian.model_client import Requirements

@pytest.mark.parametrize('message',[
    '品牌不限，预算1000元','颜色不限，预算1000元','续航不限，预算1000元',
    '预算不是不限，最多1000元','不是预算不限，是1000元以内',
])
@pytest.mark.parametrize('category',['香水','耳机'])
def test_unrelated_or_negated_unlimited_never_removes_numeric_ceiling(message,category):
    r=merge_requirements(message,Requirements(category=category).model_dump(),{'budget_max':1000,'budget_unlimited':False},semantic_only=True)
    assert r['budget_max']==1000 and not r['budget_unlimited']

@pytest.mark.parametrize('message',['预算不限，先看看','不限预算，先看看','预算不设上限'])
def test_explicit_unlimited_budget_is_distinct_from_unknown_budget(message):
    r=merge_requirements(message,Requirements(category='耳机',budget_max=1000).model_dump(),{'budget_unlimited':True},semantic_only=True)
    assert r['budget_max'] is None and r['budget_unlimited'] and not r['budget_deferred']


def test_shopping_flow_with_other_unlimited_field_stays_inside_budget(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    try:
        r=e.run({'entry':'CHAT','message':'品牌不限，预算1000元，推荐耳机'})
        assert r['status']=='READY' and r['products']
        assert r['requirements']['budget_max']==1000 and not r['requirements']['budget_unlimited']
        assert all(p['reference_price_cny']<=1000 for p in r['products'])
    finally:e.close()


def test_fixed_flow_cannot_lose_explicit_budget_to_model_unlimited_echo(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'fixed.db',mode='mock')
    e.model.understand=lambda *args,**kwargs:{'route':'READY','requirements':Requirements(category='耳机',budget_unlimited=True).model_dump()}
    try:
        r=e.run({'entry':'CHAT','message':'品牌不限，预算1000元，推荐耳机'})
        assert r['requirements']['budget_max']==1000 and not r['requirements']['budget_unlimited']
        assert all(p['reference_price_cny']<=1000 for p in r['products'])
    finally:e.close()
