"""The model cannot veto checked matches by inventing an empty catalog."""
import pytest
from diandian.workflow import Engine

@pytest.mark.parametrize('budget,expected',[(1000,'READY'),(1,'NO_RESULT')])
def test_finish_no_result_must_agree_with_verified_candidates(tmp_path,budget,expected):
    e=Engine(tmp_path/'s.db',mode='mock',agent_enabled=True)
    e.model.decide_agent=lambda c:{'action':'query_catalog'} if not c['observations'] else {'action':'finish','finish_route':'NO_RESULT'}
    try:
        r=e.run({'entry':'CHAT','message':f'{budget}元耳机'})
        assert r['status']==expected
        if expected=='READY':assert r['products'] and all(p['reference_price_cny']<=budget for p in r['products'])
        else:assert r['products']==[]
    finally:e.close()
