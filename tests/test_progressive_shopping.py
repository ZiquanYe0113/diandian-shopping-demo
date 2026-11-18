"""Recommend on a usable partial answer; refinement must not gate useful results."""
import pytest
from diandian.workflow import Engine


@pytest.fixture
def engine(tmp_path):
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    yield e
    e.close()


def run(e,message,sid=None):
    return e.run({'entry':'CHAT','message':message,'session_id':sid})


def test_opening_question_covers_budget_scene_and_preferences(engine):
    r=run(engine,'耳机')
    assert r['status']=='CLARIFY'
    assert all(word in r['answer'] for word in ('预算','通勤','运动','居家','佩戴','降噪','续航'))


def test_budget_only_answer_recommends_before_asking_optional_questions(engine):
    first=run(engine,'耳机')
    r=run(engine,'2000',first['session_id'])
    assert r['status']=='READY' and r['products']
    assert all(p['reference_price_cny'] is not None and p['reference_price_cny']<=2000 for p in r['products'])
    assert '通勤' in r['followup_question'] and '佩戴' in r['followup_question']
    assert r['answer'].endswith(r['followup_question'])
    assert r['requirements']['use_case']==''


@pytest.mark.parametrize('message',['没想好','预算还没定，先看看','预算暂时没想好'])
def test_unsure_budget_gives_explicitly_provisional_candidates_not_unlimited(engine,message):
    first=run(engine,'耳机')
    r=run(engine,message,first['session_id'])
    assert r['status']=='READY' and r['products']
    assert r['requirements']['budget_deferred'] is True
    assert r['requirements']['budget_unlimited'] is False
    assert r['requirements']['budget_max'] is None
    assert '预算还没定' in r['answer']
    refined=run(engine,'预算1000元',first['session_id'])
    assert refined['requirements']['budget_deferred'] is False
    assert all(p['reference_price_cny']<=1000 for p in refined['products'])


def test_scene_only_partial_answer_does_not_invent_a_budget(engine):
    first=run(engine,'耳机')
    r=run(engine,'通勤',first['session_id'])
    assert r['status']=='CLARIFY'
    assert r['requirements']['budget_max'] is None
    assert r['requirements']['budget_unlimited'] is False
    assert '通勤还是' not in r['answer']


def test_known_scene_is_not_asked_again_after_budget_only_recommendation(engine):
    r=run(engine,'2000元通勤耳机')
    assert r['status']=='READY' and r['products']
    assert '通勤' not in r['followup_question']
    assert '佩戴' in r['followup_question']


def test_perfume_uses_same_partial_answer_policy_without_headphone_questions(engine):
    first=run(engine,'香水')
    assert '预算' in first['answer'] and '香调' in first['answer']
    r=run(engine,'1500',first['session_id'])
    assert r['status']=='READY' and r['products']
    assert '香调' in r['followup_question']
    assert not any(w in r['followup_question'] for w in ('佩戴','续航','降噪'))


def test_fully_specified_request_has_no_repetitive_followup(engine):
    r=run(engine,'1000元通勤耳机，必须主动降噪')
    assert r['status']=='READY' and r['products']
    assert r['followup_question']==''


@pytest.mark.parametrize('message',['预算还没定，先控制在1000以内','预算不确定，别超过1000就行','预算不是没定，就是1000'])
def test_numeric_ceiling_wins_over_deferral_language(message):
    from diandian.agent import merge_requirements
    from diandian.model_client import Requirements
    r=merge_requirements(message,Requirements(category='耳机').model_dump(),{'budget_max':1000},semantic_only=True,previous_question='预算大概多少？')
    assert r['budget_max']==1000 and not r['budget_deferred']


def test_user_can_defer_old_budget_even_if_model_echoes_it():
    from diandian.agent import merge_requirements
    from diandian.model_client import Requirements
    r=merge_requirements('预算还没定，先看看',Requirements(category='耳机',budget_max=1000).model_dump(),{'budget_max':1000},semantic_only=True)
    assert r['budget_max'] is None and r['budget_deferred']


@pytest.mark.parametrize('message',['预算还没定，先看看WH-1000XM6','预算还没定，希望续航1000小时'])
def test_product_or_battery_numbers_do_not_keep_an_echoed_old_budget(message):
    from diandian.agent import merge_requirements
    from diandian.model_client import Requirements
    r=merge_requirements(message,Requirements(category='耳机',budget_max=1000).model_dump(),{'budget_max':1000},semantic_only=True)
    assert r['budget_max'] is None and r['budget_deferred']


def test_deferred_budget_with_written_chinese_ceiling_stays_bounded():
    from diandian.agent import merge_requirements
    from diandian.model_client import Requirements
    r=merge_requirements('预算还没定，先把上限定在一千元',Requirements(category='耳机').model_dump(),{'budget_max':1000},semantic_only=True)
    assert r['budget_max']==1000 and not r['budget_deferred']


def test_ambiguous_product_question_keeps_target_clarification(tmp_path):
    from diandian.model_client import Requirements
    e=Engine(tmp_path/'s.db',mode='mock')
    e.model.understand=lambda *a,**kw:{'route':'CLARIFY','requirements':Requirements(category='耳机',target='索尼',budget_max=1000).model_dump(),'clarification_question':'你想了解哪一款索尼耳机的佩戴方式？'}
    try:
        r=run(e,'预算1000元，索尼耳机的佩戴方式是什么？')
        assert r['status']=='CLARIFY' and not r['products']
        assert '哪一款' in r['answer']
    finally:e.close()
