"""No-result explanations stay readable and alternatives never relax hard facts."""
import copy

from diandian.catalog import Catalog


def respond(catalog, requirements):
    from diandian.alternatives import no_result_response
    _, rejected = catalog.filter(catalog.search(requirements), requirements)
    return no_result_response(catalog, requirements, rejected)


def test_no_result_names_products_and_makes_budget_tradeoff_explicit():
    catalog = Catalog()
    req = {'category': '香水', 'budget_max': 800}
    original = copy.deepcopy(req)
    answer, alternatives = respond(catalog, req)
    assert 'P001' not in answer
    assert '尼罗河花园' in answer
    assert '1030' in answer and '800' in answer
    assert len(alternatives) == 2
    assert [p['product_id'] for p in alternatives] == ['P003', 'P001']
    assert all('预算' in p['condition'] and '超出' in p['reason'] for p in alternatives)
    assert all(p['mismatches'][0]['field'] == 'budget_max' for p in alternatives)
    assert req == original


def test_alternatives_keep_target_version_and_budget_floor():
    _, alternatives = respond(Catalog(), {'category': '香水', 'target_ids': ['P001'],
        'budget_min': 700, 'budget_max': 800, 'spec_ml': 50, 'concentration': 'EDT'})
    assert [p['product_id'] for p in alternatives] == ['P001']
    assert alternatives[0]['reference_price_cny'] == 1030
    _, wrong_version = respond(Catalog(), {'category': '香水', 'target_ids': ['P001'],
        'budget_max': 800, 'concentration': 'EDP'})
    assert wrong_version == []
    _, lower_floor = respond(Catalog(), {'category': '香水', 'target_ids': ['P001'],
        'budget_min': 1100, 'budget_max': 800})
    assert lower_floor == []


def test_alternatives_do_not_offer_unknown_hard_quality_or_excluded_products():
    catalog = Catalog()
    req = {'category': '香水', 'budget_max': 800, 'strict_preferences': ['绝对不甜']}
    _, alternatives = respond(catalog, req)
    assert alternatives == []
    _, excluded = respond(catalog, {'category': '香水', 'budget_max': 800,
        'excluded_product_ids': ['P001', 'P002', 'P003', 'P009']})
    assert excluded == []
    _, stock = respond(catalog, {'category': '香水', 'budget_max': 800, 'must_in_stock': True})
    assert stock == []


def test_unverified_target_is_named_but_never_becomes_an_alternative():
    answer, alternatives = respond(Catalog(), {'category': '香水', 'budget_max': 800,
        'target_ids': ['P013']})
    assert '蓝风铃' in answer and '核验' in answer
    assert 'P013' not in answer
    assert alternatives == []


def test_unknown_rejected_ids_and_empty_catalog_have_no_identifier_leaks():
    from diandian.alternatives import no_result_response
    answer, alternatives = no_result_response(Catalog(), {'category': '不支持'},
        [{'product_id': 'SECRET_ID', 'reason': '规格不符'}])
    assert 'SECRET_ID' not in answer
    assert alternatives == []


def flower_request(**changes):
    return {'category': '香水', 'budget_max': 600, 'preferences_structured': True,
        'preference_constraints': [{'attribute': '香调', 'value': '花香',
            'polarity': 'prefer', 'strength': 'soft', 'quote': '喜欢花香'}], **changes}


def test_supported_flower_alternatives_rank_before_cheaper_unknown_scents():
    # This regression must also run in the public package without private notes.
    catalog=Catalog();catalog.notes=[]
    _, alternatives = respond(catalog, flower_request())
    assert [p['product_id'] for p in alternatives] == ['P002', 'P003']
    assert alternatives[0]['optional_preference_warnings']==[]
    assert alternatives[1]['optional_preference_warnings'][0]['status']=='unknown'


def test_unknown_flower_preference_is_visible_with_recorded_scent_context():
    _, alternatives = respond(Catalog(), flower_request(target_ids=['P003']))
    assert len(alternatives) == 1
    alternative = alternatives[0]
    assert '花香' in alternative['reason'] and '资料不足' in alternative['reason']
    assert '柑橘、木质' in alternative['reason']
    warning = alternative['optional_preference_warnings'][0]
    assert warning['preference'] == '花香' and warning['status'] == 'unknown'
    assert warning['sources'][0]['quote'] == '柑橘、木质'


def test_soft_conflict_is_warned_with_actual_evidence_and_ranked_after_unknown():
    catalog = Catalog()
    # Controlled fixture keeps real product/version data and changes only the
    # recorded scent description; a literal negation supplies conflict evidence.
    catalog.products = [copy.deepcopy(p) for p in catalog.products if p['product_id'] in ('P001', 'P002', 'P003')]
    catalog.notes = []
    for product in catalog.products:
        product['scent_family'] = '不是花香'
        product['selling_points'] = product['key_notes'] = product['cautions'] = ''
    catalog.products[0]['scent_family'] = '木质'
    _, alternatives = respond(catalog, flower_request())
    assert [p['product_id'] for p in alternatives] == ['P001', 'P003']
    conflicting = alternatives[1]
    assert '花香' in conflicting['reason'] and '冲突' in conflicting['reason']
    assert '不是花香' in conflicting['reason']
    warning = conflicting['optional_preference_warnings'][0]
    assert warning['status'] == 'conflict'
    assert warning['sources'][0]['quote'] == '不是花香'
