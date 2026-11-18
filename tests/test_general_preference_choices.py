import pytest
from diandian.preferences import update_preferences


def apply(message, category='耳机', previous=None, updates=()):
    return update_preferences(message, {'category': category, 'preference_updates': list(updates)}, previous, semantic_only=True)


@pytest.mark.parametrize('message,attribute,value,polarity', [
    ('入耳式', '佩戴方式', '入耳式', 'prefer'),
    ('我偏好 over-ear 吧', '佩戴方式', '头戴包耳式', 'prefer'),
    ('不要入耳式', '佩戴方式', '入耳式', 'avoid'),
    ('ANC', '功能', '主动降噪', 'prefer'),
    ('清爽、木质', '香调', '清新', 'prefer'),
])
def test_complete_registered_choices(message, attribute, value, polarity):
    result = apply(message, '香水' if attribute == '香调' else '耳机')
    assert any((c['attribute'], c['value'], c['polarity']) == (attribute, value, polarity)
               for c in result['preference_constraints'])


@pytest.mark.parametrize('message', ['入耳式好吗？', '不是不要入耳式', '朋友喜欢入耳式', '入耳式或者头戴式', 'ANC越强越好', '续航'])
def test_free_language_is_left_to_model(message):
    assert apply(message)['preference_constraints'] == []


def test_remove_replace_and_preserve_other_dimensions():
    previous = apply('入耳式、ANC')
    result = apply('改成包耳式', previous=previous)
    assert {(c['attribute'], c['value']) for c in result['preference_constraints']} == {('佩戴方式', '头戴包耳式'), ('功能', '主动降噪')}
    assert [c['value'] for c in apply('取消ANC', previous=result)['preference_constraints']] == ['头戴包耳式']


def test_echo_preserves_hardness_and_original_evidence():
    c = dict(attribute='佩戴方式', value='入耳式', polarity='prefer', strength='hard', quote='必须入耳式')
    result = apply('入耳', previous={'preferences_structured': True, 'preference_constraints': [c]})
    assert result['preference_constraints'] == [c]


def test_safe_model_updates_are_primary():
    edit = dict(attribute='佩戴方式', value='入耳式', polarity='prefer', strength='hard', quote='入耳式', operation='upsert')
    assert apply('入耳式', updates=[edit])['preference_constraints'][0]['strength'] == 'hard'


def test_literal_ground_truth_corrects_wrong_registered_choice():
    edit = dict(attribute='佩戴方式', value='头戴包耳式', polarity='prefer', strength='soft', quote='入耳式', operation='upsert')
    assert [c['value'] for c in apply('入耳式', updates=[edit])['preference_constraints']] == ['入耳式']


def test_semantic_dimension_and_unquantified_battery_remain_model_owned():
    edit = dict(attribute='续航', value='续航优先', polarity='prefer', strength='soft', quote='续航', operation='upsert')
    assert apply('续航', updates=[edit])['preference_constraints'] == [{k: v for k, v in edit.items() if k != 'operation'}]


def test_ambiguous_combination_is_atomic_and_category_scoped():
    assert apply('ANC、续航')['preference_constraints'] == []
    assert apply('入耳式', category='香水')['preference_constraints'] == []


def test_explicit_replacement_echo_preserves_hard_evidence():
    old = dict(attribute='香调', value='木质', polarity='prefer', strength='hard', quote='一定要木质')
    assert apply('换成木质', category='香水', previous={'preference_constraints': [old], 'preferences_structured': True})['preference_constraints'] == [old]


def test_shared_negation_scope_is_not_guessed():
    assert apply('不要入耳式和ANC')['preference_constraints'] == []
