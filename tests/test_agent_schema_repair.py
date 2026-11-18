import pytest
from pydantic import ValidationError
from diandian.model_client import RealModel


def model():return RealModel('test-only','https://example.test/v1','test')
def invalid():return {'action':'query_catalog','requirements':{'category':'耳机','preference_updates':[{'attribute':'功能','value':'主动降噪','polarity':'prefer','strength':'soft','quote':'喜欢降噪'}]}}


def test_missing_required_edit_field_has_one_validated_repair_with_original_context():
    m=model();calls=[];context={'request':{'message':'喜欢降噪'}}
    def call(prompt,payload,**kw):
        calls.append((payload,kw));m.usage.append({'stage':kw.get('stage')})
        if len(calls)==1:return invalid()
        r=invalid();r['requirements']['preference_updates'][0]['operation']='upsert';return r
    m.json_call=call
    r=m.decide_agent(context)
    assert r['requirements']['preference_updates'][0]['operation']=='upsert'
    assert len(calls)==2 and calls[1][1]['stage']=='agent_schema_repair'
    assert calls[1][0]['context']==context


def test_invalid_repair_stays_an_error_and_no_third_call():
    m=model();calls=[]
    def call(*args,**kw):calls.append(kw);return invalid()
    m.json_call=call
    with pytest.raises(ValidationError):m.decide_agent({})
    assert len(calls)==2


def test_repair_budget_is_once_per_request_and_invalid_actions_are_not_repaired():
    m=model();m.usage=[{'stage':'agent_schema_repair'}];calls=[]
    def call(*args,**kw):calls.append(kw);return invalid()
    m.json_call=call
    with pytest.raises(ValidationError):m.decide_agent({})
    assert len(calls)==1
    m.usage=[];calls.clear();m.json_call=lambda *a,**kw: calls.append(kw) or {'action':'delete_everything'}
    with pytest.raises(ValidationError):m.decide_agent({})
    assert len(calls)==1
