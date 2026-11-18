"""Validated semantic fields must not be overwritten by unordered keyword scans."""
import pytest
from diandian.agent import merge_requirements
from diandian.model_client import Requirements

@pytest.mark.parametrize('category',['香水','耳机'])
@pytest.mark.parametrize('message,scene',[
    ('以前通勤用，这次是送礼','送礼'),
    ('通勤和运动都想用','通勤、运动'),
    ('居家办公时用','居家办公'),
])
def test_current_semantic_scene_wins_over_literal_first_keyword(category,message,scene):
    r=merge_requirements(message,Requirements(category=category).model_dump(),{'use_case':scene},semantic_only=True)
    assert r['use_case']==scene


def test_ambiguous_scene_prose_is_not_guessed_when_model_omits_edit():
    r=merge_requirements('以前通勤用，这次是送礼',Requirements(category='香水').model_dump(),{},semantic_only=True)
    assert r['use_case']==''
