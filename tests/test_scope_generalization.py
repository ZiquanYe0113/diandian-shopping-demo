"""Catalog identities generalize; semantics may narrow the literal target."""
import pytest
from diandian.product_scope import resolve_browse_scope


@pytest.fixture
def products():
    return [
        {'product_id':'X1', 'brand':'Lumen 流明', 'product_name':'Lumen Orbit 7 咖啡机', 'aliases':'Orbit 7;环轨七代', 'category':'咖啡机'},
        {'product_id':'X2', 'brand':'Lumen 流明', 'product_name':'Lumen Orbit 8 咖啡机', 'aliases':'Orbit 8;环轨八代', 'category':'咖啡机'},
        {'product_id':'Y1', 'brand':'Nova 新星', 'product_name':'Nova Halo 2 咖啡机', 'aliases':'Halo 2', 'category':'咖啡机'},
    ]


def test_unseen_catalog_category_and_alias_are_grounded(products):
    result = resolve_browse_scope('看看流明咖啡机', products)
    assert result['browse_product_ids'] == ['X1','X2']
    assert result['category'] == '咖啡机'
    assert resolve_browse_scope('环轨七代', products)['browse_product_ids'] == ['X1']


def test_category_suffix_negation_is_catalog_derived(products):
    result = resolve_browse_scope('流明咖啡机不考虑了，看看新星咖啡机', products)
    assert result['browse_product_ids'] == ['Y1']
    assert result['excluded_product_ids'] == ['X1','X2']


@pytest.mark.parametrize('message', ['流明望远镜', '流明帐篷', 'Lumen telescope'])
def test_brand_does_not_invent_catalog_category_for_arbitrary_noun(message, products):
    assert resolve_browse_scope(message, products)['browse_product_ids'] is None


def test_semantics_can_identify_an_unsupported_category_without_code_vocabulary(products):
    result = resolve_browse_scope('流明望远镜', products, semantic_context={'category':'望远镜'})
    assert result['browse_product_ids'] is None
    assert result['category'] == '望远镜'


def test_semantic_target_avoids_historical_product_and_category_mentions(products):
    result = resolve_browse_scope('之前用Orbit 7咖啡机，现在看看Halo 2', products,
        semantic_context={'category':'咖啡机', 'scope_text':'Halo 2'})
    assert result['browse_product_ids'] == ['Y1']


def test_semantic_context_cannot_invent_a_model(products):
    result = resolve_browse_scope('看看Orbit 999', products,
        semantic_context={'category':'咖啡机', 'scope_text':'Orbit 999'})
    assert result['browse_product_ids'] == []


def test_semantic_scope_text_must_be_literal_user_evidence(products):
    result = resolve_browse_scope('看看Halo 2', products,
        semantic_context={'category':'咖啡机', 'scope_text':'Orbit 7'})
    assert result['browse_product_ids'] == ['Y1']


def test_brand_prefix_inside_another_word_is_not_identity(products):
    assert resolve_browse_scope('Lumenous咖啡机', products)['browse_product_ids'] is None


def test_semantic_quote_requires_exact_substring(products):
    result = resolve_browse_scope('Orbit 7和Halo 2', products,
        semantic_context={'category':'咖啡机', 'scope_text':'ORBIT7'})
    assert result['browse_product_ids'] == ['X1','Y1']


def test_semantic_target_does_not_strip_negation_governing_the_quote(products):
    result = resolve_browse_scope('不要Orbit 7', products,
        semantic_context={'category':'咖啡机', 'scope_text':'Orbit 7'})
    assert result['browse_product_ids'] is None
    assert result['excluded_product_ids'] == ['X1']


def test_semantic_unknown_brand_qualified_model_does_not_expand_to_brand(products):
    result = resolve_browse_scope('看看流明Rocket999', products,
        semantic_context={'category':'咖啡机', 'scope_text':'流明Rocket999'})
    assert result['browse_product_ids'] == []


def test_agent_uses_current_semantic_target_evidence_not_all_historical_mentions(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'scope.db',mode='mock',agent_enabled=True)
    e.model.mode='real'
    e.model.decide_agent=lambda c:{'action':'query_catalog','requirements':{'category':'耳机','target_quote':'索尼耳机'}} if not c['observations'] else {'action':'finish','finish_route':'READY'}
    try:
        r=e.run({'entry':'CHAT','message':'以前用AirPods，现在想看看索尼耳机'})
        assert r['status']=='READY' and r['products']
        assert all('Sony' in p['brand'] for p in r['products'])
        assert set(r['requirements']['browse_product_ids'])=={'H004','H005','H006','H007'}
        assert r['requirements']['budget_max'] is None
    finally:e.close()


def test_semantic_empty_exclusions_do_not_commit_historical_negation(products):
    result = resolve_browse_scope('以前不用流明咖啡机，现在想看看Orbit', products,
        semantic_context={'category':'咖啡机', 'scope_text':'Orbit', 'exclusion_quotes':[]})
    assert result['browse_product_ids'] == ['X1','X2']
    assert result['excluded_product_ids'] == []


def test_semantic_negative_evidence_commits_only_quoted_current_exclusion(products):
    result = resolve_browse_scope('不要流明，看看新星咖啡机', products,
        semantic_context={'category':'咖啡机', 'scope_text':'新星咖啡机', 'exclusion_quotes':['不要流明']})
    assert result['browse_product_ids'] == ['Y1']
    assert result['excluded_product_ids'] == ['X1','X2']


def test_empty_current_exclusions_preserve_previous_hard_exclusions(products):
    result = resolve_browse_scope('看看Orbit', products, {'excluded_product_ids':['X1']},
        semantic_context={'category':'咖啡机', 'scope_text':'Orbit', 'exclusion_quotes':[]})
    assert result['browse_product_ids'] == ['X2']
    assert result['excluded_product_ids'] == ['X1']


def test_invalid_exclusion_evidence_falls_back_conservatively(products):
    result = resolve_browse_scope('不要流明，看看新星咖啡机', products,
        semantic_context={'category':'咖啡机', 'scope_text':'新星咖啡机', 'exclusion_quotes':['不要新星']})
    assert result['excluded_product_ids'] == ['X1','X2']


def test_agent_historical_rejection_does_not_become_current_brand_exclusion(tmp_path):
    from diandian.workflow import Engine
    e=Engine(tmp_path/'history.db',mode='mock',agent_enabled=True);e.model.mode='real'
    e.model.decide_agent=lambda c: {'action':'query_catalog','requirements':{'category':'耳机','target_quote':'AirPods','exclusion_quotes':[]}} if not c['observations'] else {'action':'finish','finish_route':'READY'}
    try:
        r=e.run({'entry':'CHAT','message':'以前不用苹果耳机，现在想看看AirPods'})
        assert r['status']=='READY' and r['products']
        assert all('Apple' in p['brand'] for p in r['products'])
        assert r['requirements']['excluded_product_ids']==[]
    finally:e.close()


def test_later_semantic_target_supersedes_earlier_broad_negative_evidence(products):
    result = resolve_browse_scope('以前不用流明咖啡机，现在想看看Orbit', products,
        {'excluded_product_ids':['X1','X2','Y1']},
        semantic_context={'category':'咖啡机', 'scope_text':'现在想看看Orbit',
                          'exclusion_quotes':['以前不用流明咖啡机']})
    assert result['browse_product_ids'] == ['X1','X2']
    assert result['excluded_product_ids'] == ['Y1']


def test_later_broad_semantic_target_preserves_earlier_specific_rejection(products):
    result = resolve_browse_scope('不要Orbit 7，看看Orbit', products,
        semantic_context={'category':'咖啡机', 'scope_text':'看看Orbit',
                          'exclusion_quotes':['不要Orbit 7']})
    assert result['browse_product_ids'] == ['X2']
    assert result['excluded_product_ids'] == ['X1']


def test_negative_after_semantic_target_still_excludes(products):
    result = resolve_browse_scope('看看Orbit，但不要流明咖啡机', products,
        semantic_context={'category':'咖啡机', 'scope_text':'看看Orbit',
                          'exclusion_quotes':['不要流明咖啡机']})
    assert result['browse_product_ids'] == []
    assert result['excluded_product_ids'] == ['X1','X2']


def test_actual_historical_exclusion_quote_yields_to_current_airpods_selection():
    from diandian.catalog import Catalog
    products = Catalog().products
    result = resolve_browse_scope('以前不用苹果耳机，现在想看看AirPods', products,
        semantic_context={'category':'耳机', 'scope_text':'现在想看看AirPods',
                          'exclusion_quotes':['以前不用苹果耳机']})
    assert result['browse_product_ids'] == ['H001','H002','H003','H008']
    assert result['excluded_product_ids'] == []
