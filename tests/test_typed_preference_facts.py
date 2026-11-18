"""Objective preferences consume current verified facts, retaining their provenance."""
from copy import deepcopy

import pytest

from diandian.catalog import Catalog
from diandian.preferences import assess, order_candidates


@pytest.fixture
def catalog():
    return Catalog().products


def product_with(catalog, key, value):
    return next(p for p in catalog if p['category']=='耳机' and any(
        a['key']==key and type(a['value']) is type(value) and a['value']==value
        for a in p['attributes']))


def requirement(attribute='功能', value='降噪', polarity='prefer', strength='soft'):
    return {'preferences_structured':True, 'preference_constraints':[
        {'attribute':attribute, 'value':value, 'polarity':polarity, 'strength':strength,
         'quote':value}]}


@pytest.mark.parametrize('actual,polarity,status', [
    (True,'prefer','supported'), (False,'prefer','conflict'),
    (True,'avoid','conflict'), (False,'avoid','supported'),
])
def test_verified_anc_controls_preference_polarity_and_retains_source(catalog,actual,polarity,status):
    product=product_with(catalog,'anc',actual)
    match=assess(product,requirement(polarity=polarity),[],catalog)['matches'][0]
    assert match['status']==status
    sources=match['support'] if status=='supported' else match['conflict']
    index=next(i for i,a in enumerate(product['attributes']) if a['key']=='anc')
    assert sources[0]['field']==f'attributes.{index}'
    assert sources[0]['source_url']==product['attributes'][index]['source_url']
    assert sources[0]['source_quote']==product['attributes'][index]['source_quote']


@pytest.mark.parametrize('dimension,value', [
    ('功能','主动降噪'), ('降噪','ANC'), ('anc','true'),
    ('feature','active noise cancellation'), ('功能','active noise cancelling'),
])
def test_explicit_anc_dimension_value_aliases(catalog,dimension,value):
    product=product_with(catalog,'anc',True)
    assert assess(product,requirement(dimension,value),[],catalog)['matches'][0]['status']=='supported'


@pytest.mark.parametrize('dimension,value', [
    ('功能','通话降噪'), ('功能','被动隔音'), ('功能','call noise reduction'),
    ('续航','长'), ('音质','好'), ('佩戴','舒适'), ('外观','降噪'),
])
def test_unrelated_subjective_and_non_anc_preferences_remain_unknown(catalog,dimension,value):
    product=product_with(catalog,'anc',True)
    assert assess(product,requirement(dimension,value),[],catalog)['matches'][0]['status']=='unknown'


@pytest.mark.parametrize('changed', [
    {'verified':False}, {'source_url':'https://example.com/specs'},
    {'source_quote':''}, {'value':None}, {'value':'true'},
])
def test_unverified_or_untyped_anc_cannot_prove_preference(catalog,changed):
    product=deepcopy(product_with(catalog,'anc',True))
    for fact in product['attributes']:
        if fact['key']=='anc':fact.update(changed)
    assert assess(product,requirement(),[],catalog)['matches'][0]['status']=='unknown'


@pytest.mark.parametrize('actual,presence,status', [(False,'present','conflict'),(True,'absent','supported')])
def test_verified_fact_cannot_be_overridden_by_model_claim(catalog,actual,presence,status):
    product=product_with(catalog,'anc',actual)
    claim={'product_id':product['product_id'],'attribute':'功能','value':'降噪','presence':presence,
           'source':{'type':'catalog','field':'selling_points','quote':product['selling_points']}}
    match=assess(product,requirement(),[],catalog,interpretations=[claim])['matches'][0]
    assert match['status']==status
    assert all(s['field'].startswith('attributes.') for s in match['support']+match['conflict'])


@pytest.mark.parametrize('value', ['入耳式','in-ear','in ear'])
def test_wearing_style_aliases_use_exact_verified_fact(catalog,value):
    product=product_with(catalog,'wearing_style','入耳式')
    match=assess(product,requirement('佩戴方式',value),[],catalog)['matches'][0]
    assert match['status']=='supported'
    assert match['support'][0]['field'].startswith('attributes.')


def test_wearing_style_difference_is_conflict_without_equating_comfort(catalog):
    product=product_with(catalog,'wearing_style','头戴贴耳式')
    assert assess(product,requirement('wearing_style','over-ear'),[],catalog)['matches'][0]['status']=='conflict'


def test_hard_anc_excludes_official_false_and_missing_facts(catalog):
    positive=product_with(catalog,'anc',True)
    negative=product_with(catalog,'anc',False)
    missing=deepcopy(positive);missing['product_id']='unknown-anc'
    missing['attributes']=[a for a in missing['attributes'] if a['key']!='anc']
    good,rejected,assessments=order_candidates([positive,negative,missing],requirement(strength='hard'),[],catalog)
    assert [p['product_id'] for p in good]==[positive['product_id']]
    assert {p['product_id'] for p in rejected}=={negative['product_id'],'unknown-anc'}
    assert assessments['unknown-anc']['matches'][0]['status']=='unknown'


@pytest.mark.parametrize('quote', ['降噪吧','主动降噪','ANC','降噪吧，别的无所谓'])
def test_neutral_boolean_choice_recovers_misplaced_quality_value(catalog,quote):
    from diandian.preferences import update_preferences
    edit={'operation':'upsert','attribute':'降噪','value':'好','quote':quote,
          'polarity':'prefer','strength':'soft'}
    req=update_preferences('在家里听，'+quote,{'preference_updates':[edit]},semantic_only=True)
    constraint=req['preference_constraints'][0]
    assert constraint['quote']==quote
    assert constraint['value']=='主动降噪'
    assert req['preferences']==['主动降噪']
    product=product_with(catalog,'anc',True)
    assert assess(product,req,[],catalog)['matches'][0]['status']=='supported'


@pytest.mark.parametrize('quote,polarity', [
    ('降噪效果好','prefer'),('降噪强','prefer'),('更安静','prefer'),
    ('通话降噪','prefer'),('被动降噪','prefer'),('不降噪','prefer'),
    ('不要降噪','avoid'),('降噪吧','avoid'),
])
def test_boolean_choice_recovery_preserves_quality_and_negation(quote,polarity):
    from diandian.preferences import update_preferences
    edit={'operation':'upsert','attribute':'降噪','value':'好','quote':quote,
          'polarity':polarity,'strength':'hard'}
    req=update_preferences(quote,{'preference_updates':[edit]},semantic_only=True)
    assert req['preference_constraints']==[{k:v for k,v in edit.items() if k!='operation'}]
