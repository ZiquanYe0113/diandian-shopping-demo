"""Explicit shopping identities remain catalog constraints, not first-SKU guesses."""
import pytest
from diandian.catalog import Catalog
from diandian.model_client import Requirements, ModelRequirements


def scope(message, previous=None):
    from diandian.product_scope import resolve_browse_scope
    return resolve_browse_scope(message, Catalog().products, previous)


def test_scope_is_code_owned_and_not_model_editable():
    assert Requirements().model_dump().get('browse_product_ids', 'missing') is None
    assert 'browse_product_ids' not in ModelRequirements.model_json_schema()['properties']
    assert 'browse_product_ids' not in ModelRequirements.model_validate({'browse_product_ids':['H004']}).model_dump()


@pytest.mark.parametrize('message', ['苹果耳机', '苹果的耳机', 'Apple耳机', 'apple headphones'])
def test_brand_browsing_returns_every_matching_model(message):
    result=scope(message)
    assert result['browse_product_ids'] == ['H001','H002','H003','H008']
    assert result['category'] == '耳机'


@pytest.mark.parametrize('message', ['AirPods', 'airpods耳机', '看看 AIRPODS'])
def test_family_browsing_is_case_insensitive(message):
    assert scope(message)['browse_product_ids'] == ['H001','H002','H003','H008']


@pytest.mark.parametrize('message', ['AirPods 5', 'airpods5', '想看看苹果AirPods5'])
def test_model_browsing_retains_matching_versions(message):
    assert scope(message)['browse_product_ids'] == ['H001','H002']


def test_more_specific_version_wins_over_model():
    assert scope('AirPods 5无线充电盒款')['browse_product_ids'] == ['H002']


@pytest.mark.parametrize('message', ['AirPods Pro 999', 'AirPodsPro999', 'AirPods 5999', 'AirPods Pro 30'])
def test_unknown_model_never_falls_back_to_family_or_prefix(message):
    assert scope(message)['browse_product_ids'] == []


def test_brand_and_perfume_aliases_come_from_catalog():
    assert scope('索尼耳机')['browse_product_ids'] == ['H004','H005','H006','H007']
    assert scope('sony WH-CH720N')['browse_product_ids'] == ['H005']
    assert scope('爱马仕香水')['category'] == '香水'
    assert 'P001' in scope('爱马仕香水')['browse_product_ids']
    assert scope('尼罗河花园')['browse_product_ids'] == ['P001']


@pytest.mark.parametrize('message', ['不要苹果耳机', '不考虑Apple耳机', '排除AirPods', '不想要索尼耳机'])
def test_excluded_identities_are_not_positive_browse_scope(message):
    assert scope(message)['browse_product_ids'] is None


def test_scope_persists_followups_and_clears_on_category_switch():
    previous={'category':'耳机','browse_product_ids':['H001','H002'], 'budget_max':1200}
    assert scope('预算1000', previous)['browse_product_ids'] == ['H001','H002']
    assert scope('换成香水', previous)['browse_product_ids'] is None
    assert scope('索尼耳机', previous)['browse_product_ids'] == ['H004','H005','H006','H007']
    assert 'budget_max' not in scope('苹果耳机', previous)


def test_search_intersects_scope_with_target_ids_and_target():
    catalog=Catalog()
    req={'category':'耳机','browse_product_ids':['H001','H002'], 'target_ids':['H004']}
    assert catalog.search(req) == []
    req.pop('target_ids'); req['target']='Sony'
    assert catalog.search(req) == []
    req.pop('target')
    assert [p['product_id'] for p in catalog.search(req)] == ['H001','H002']
    assert catalog.search({**req,'browse_product_ids':[]}) == []


def test_filter_enforces_scope_and_hard_budget_even_for_forged_candidates():
    catalog=Catalog()
    req={'category':'耳机','browse_product_ids':['H001','H002'],'budget_max':1000}
    good,_=catalog.filter(catalog.products, req)
    assert [p['product_id'] for p in good] == ['H001']
    assert catalog.filter(catalog.products, {**req,'browse_product_ids':[]})[0] == []


@pytest.mark.parametrize('message', ['苹果AirPodsPro999', 'Apple AirPods Pro 999', 'Sony WH-CH999', '索尼WHCH999'])
def test_unknown_model_does_not_fall_back_to_its_explicit_brand(message):
    assert scope(message)['browse_product_ids'] == []


def test_browse_label_is_code_owned_and_persists():
    assert Requirements().browse_label == ''
    assert 'browse_label' not in ModelRequirements.model_json_schema()['properties']
    first=scope('苹果耳机')
    assert first['browse_label'] == '苹果'
    assert scope('预算1000', {**first,'category':'耳机'})['browse_label'] == '苹果'
    assert scope('换成香水', {**first,'category':'耳机'})['browse_label'] == ''


@pytest.mark.parametrize('message', ['苹果手机', '索尼相机', '苹果水果'])
def test_brand_does_not_turn_unrelated_product_types_into_headphones(message):
    result=scope(message)
    assert result['browse_product_ids'] is None
    assert result.get('category') != '耳机'


def test_negative_brand_clears_prior_positive_scope():
    previous={'category':'耳机','browse_product_ids':['H001','H002','H003','H008'],'browse_label':'苹果'}
    assert scope('不要苹果', previous)['browse_product_ids'] is None


def test_model_compatibility_question_is_not_an_unrelated_phone_request():
    result=scope('AirPods Pro 3兼容苹果手机吗')
    assert result['category'] == '耳机'
    assert result['browse_product_ids'] == ['H003']


def test_negative_specific_model_does_not_exclude_the_entire_family():
    result=scope('预算2000元，不要AirPods Pro 3，看看AirPods')
    assert result['browse_product_ids'] == ['H001','H002','H008']
    assert result['excluded_product_ids'] == ['H003']
    followup=scope('预算改成3000', result)
    assert followup['browse_product_ids'] == ['H001','H002','H008']
    assert followup['excluded_product_ids'] == ['H003']
    assert 'H003' not in scope('看看AirPods', followup)['browse_product_ids']


def test_negative_brand_is_a_persistent_hard_exclusion_without_positive_scope():
    catalog=Catalog()
    result=scope('不要苹果耳机')
    assert result['excluded_product_ids'] == ['H001','H002','H003','H008']
    req={**result,'category':'耳机','budget_max':1000}
    good,_=catalog.filter(catalog.search(req), req)
    assert good and all(p['brand']=='Sony 索尼' for p in good)
    followup=scope('预算改成2000', req)
    assert followup['excluded_product_ids'] == result['excluded_product_ids']


def test_excluding_one_model_preserves_the_remaining_inherited_scope():
    previous=scope('苹果耳机')
    result=scope('不要AirPods Pro 3', previous)
    assert result['browse_product_ids'] == ['H001','H002','H008']
    assert result['excluded_product_ids'] == ['H003']


def test_explicit_unverified_identity_is_retrieved_then_rejected_with_reason():
    catalog=Catalog()
    product=next(p for p in catalog.products if p.get('verified_for_recommendation') is False)
    req={'category':product['category'],'browse_product_ids':[product['product_id']]}
    found=catalog.search(req)
    assert [p['product_id'] for p in found] == [product['product_id']]
    good,rejected=catalog.filter(found, req)
    assert good == []
    assert rejected == [{'product_id':product['product_id'],'reason':'商品事实待核验，暂停推荐'}]


@pytest.mark.parametrize('message', ['不用降噪的苹果耳机', '不想要入耳式的苹果耳机'])
def test_negated_feature_does_not_negate_the_product_brand(message):
    result=scope(message)
    assert result['browse_product_ids'] == ['H001','H002','H003','H008']
    assert result['excluded_product_ids'] == []


@pytest.mark.parametrize('message', ['不要苹果耳机而是索尼耳机', '苹果耳机不考虑了，看看索尼耳机'])
def test_negation_follows_its_brand_subject_not_the_contrasted_brand(message):
    result=scope(message)
    assert result['browse_product_ids'] == ['H004','H005','H006','H007']
    assert result['excluded_product_ids'] == ['H001','H002','H003','H008']


def test_brand_qualified_negative_model_excludes_only_that_model():
    result=scope('不要苹果AirPods Pro 3，看看苹果耳机')
    assert result['browse_product_ids'] == ['H001','H002','H008']
    assert result['excluded_product_ids'] == ['H003']


def test_explicit_exclusion_reason_does_not_claim_product_was_recommended():
    catalog=Catalog()
    product=next(p for p in catalog.products if p['product_id']=='H003')
    _,rejected=catalog.filter([product], {'excluded_product_ids':['H003']})
    assert rejected[0]['reason'] == '命中用户排除或换一批要求'


@pytest.mark.parametrize('message', ['当前想看AirPods Pro 3', '还是看看AirPods Pro 3', '重新考虑AirPods Pro 3', '取消排除AirPods Pro 3', '恢复推荐AirPods Pro 3', '想看看AirPods Pro 3'])
def test_explicit_reversal_restores_only_the_named_model(message):
    previous={**scope('预算2000元，不要AirPods Pro 3，看看AirPods'),'excluded_product_ids':['H003','H004'],'budget_max':2000}
    result=scope(message, previous)
    assert result['browse_product_ids'] == ['H003']
    assert result['excluded_product_ids'] == ['H004']
    merged={**previous,**result}
    assert merged['budget_max'] == 2000
    assert Catalog().filter(Catalog().search(merged), merged)[0]


@pytest.mark.parametrize('message', ['还有别的AirPods', '看看AirPods', '预算3000元', 'AirPods Pro 3降噪怎么样'])
def test_generic_browse_budget_or_product_question_does_not_cancel_exclusions(message):
    previous={**scope('不要AirPods Pro 3，看看AirPods'),'budget_max':2000}
    result=scope(message, previous)
    assert result['excluded_product_ids'] == ['H003']
    assert 'H003' not in (result['browse_product_ids'] or [])


def test_explicit_selection_reallows_a_product_removed_by_another_batch():
    previous={'category':'耳机','excluded_product_ids':['H001','H002','H003'],'budget_max':1200}
    result=scope('想看看AirPods 5', previous)
    assert result['browse_product_ids'] == ['H001','H002']
    assert result['excluded_product_ids'] == ['H003']


def test_reversal_never_weakens_existing_hard_budget():
    previous={'category':'耳机','excluded_product_ids':['H003'],'budget_max':1000}
    result=scope('还是看看AirPods Pro 3', previous)
    req={**previous,**result}
    assert result['browse_product_ids'] == ['H003']
    assert req['budget_max'] == 1000
    assert Catalog().filter(Catalog().search(req), req)[0] == []
