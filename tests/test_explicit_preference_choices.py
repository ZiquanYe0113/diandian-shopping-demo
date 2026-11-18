"""A concrete short choice must survive missing semantic updates."""
import pytest
from diandian.agent import merge_requirements
from diandian.model_client import Requirements
from diandian.workflow import Engine

@pytest.mark.parametrize('message,value', [('花香','花香'),('清新','清新'),('木质','木质'),('柑橘','柑橘'),('喜欢花香','花香'),('花香吧','花香')])
def test_missing_model_update_does_not_drop_explicit_perfume_choice(message,value):
    old=Requirements(category='香水',budget_max=600,use_case='通勤',preferences_structured=True).model_dump()
    r=merge_requirements(message,old,{},semantic_only=True)
    assert value in r['preferences']
    c=next(c for c in r['preference_constraints'] if c['value']==value)
    assert c['polarity']=='prefer' and c['strength']=='soft' and c['quote'] in message

@pytest.mark.parametrize('message',['不要花香','不是花香','花香不要了','花香是什么','这篇笔记写了花香','如果是花香呢'])
def test_negation_knowledge_and_note_text_do_not_become_positive_choice(message):
    r=merge_requirements(message,Requirements(category='香水').model_dump(),{},semantic_only=True)
    assert not any(c['value']=='花香' and c['polarity']=='prefer' for c in r['preference_constraints'])


def test_explicit_replacement_removes_previous_scent_without_erasing_other_constraints():
    old=merge_requirements('花香',Requirements(category='香水',budget_max=600,use_case='通勤').model_dump(),semantic_only=True)
    r=merge_requirements('改成木质',old,{},semantic_only=True)
    assert r['preferences']==['木质']
    assert r['budget_max']==600 and r['use_case']=='通勤'


def test_choice_replayed_through_real_mode_agent_does_not_repeat_question(tmp_path):
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    e.model.mode='real'
    def decide(c):
        # Actual failure shape: model asks scent question but omits preference edits.
        if not c['observations']:return {'action':'ask_user','ask_field':'preferences'}
        return {'action':'finish','finish_route':'READY'}
    e.model.decide_agent=decide
    sid='short-choice'
    e.graph.update_state({'configurable':{'thread_id':sid}}, {'requirements':Requirements(category='香水',budget_max=600,use_case='通勤',preferences_structured=True).model_dump(),'question':'你偏好什么香调？'})
    try:
        r=e.run({'entry':'CHAT','message':'花香','session_id':sid})
        assert r['status']=='NO_RESULT'
        assert r['requirements']['preferences']==['花香']
        assert r['agent']['observations'][0]['action']=='query_catalog'
        assert not r.get('followup_question')
    finally:e.close()


def test_short_echo_does_not_weaken_existing_hard_constraint():
    old=Requirements(category='香水',preferences_structured=True,preference_constraints=[{'attribute':'香调','value':'花香','polarity':'prefer','strength':'hard','quote':'必须花香'}]).model_dump()
    r=merge_requirements('花香',old,semantic_only=True)
    assert r['preference_constraints'][0]['strength']=='hard'
    assert r['preference_constraints'][0]['quote']=='必须花香'
