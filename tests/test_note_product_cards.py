from diandian.catalog import Catalog
from diandian.note_analysis import validate_analysis
from diandian.workflow import Engine


def test_exact_product_card_consolidates_text_and_image_evidence():
    quote='祖玛珑蓝风铃 Cologne'
    raw={'summary':'试香','mentions':[
        {'name':'蓝风铃','quote':quote,'product_id':'P013'},
        {'name':'蓝风铃香水','quote':quote,'product_id':'P013','source':'image_text','image_index':1}],
        'image_observations':[{'image_index':1,'ocr_text':quote}]}
    result=validate_analysis(raw,{'text':quote,'image_indexes':[1]},Catalog().products)
    cards=result['resolved_products']
    assert len(cards)==1
    assert cards[0]['product_id']=='P013'
    assert cards[0]['product_name']
    assert {v['source'] for v in cards[0]['mention_evidence']}=={'text','image_text'}


def test_paused_green_chance_exposes_only_historical_identity():
    quote='香奈儿绿邂逅淡香水'
    result=validate_analysis({'summary':'试香','mentions':[{'name':'绿邂逅','quote':quote,'product_id':'P016'}]}, {'text':quote},Catalog().products)
    mention=result['mentions'][0]
    assert mention['product_id'] is None
    assert mention['identity_product_id']=='P016'
    card=result['resolved_products'][0]
    assert card['resolution_status']=='identity_only'
    assert card['reference_price_cny'] is None
    assert not card.get('concentration')
    assert not card.get('key_notes')
    assert card['verified_for_recommendation'] is False
    assert '历史' in card['resolution_notice']


def test_ambiguous_family_and_visual_guess_do_not_resolve():
    products=[{'product_id':'a','product_name':'香水 EDT','aliases':'共同香水','category':'香水','concentration':'EDT'},
              {'product_id':'b','product_name':'香水 EDP','aliases':'共同香水','category':'香水','concentration':'EDP'}]
    result=validate_analysis({'summary':'试香','mentions':[{'name':'共同香水','quote':'共同香水','product_id':'a'}]}, {'text':'共同香水'},products)
    assert result['resolved_products']==[]
    result=validate_analysis({'summary':'试香','mentions':[{'name':'绿邂逅','quote':'绿色瓶子','product_id':'P016','source':'image_visual','image_index':1}], 'image_observations':[{'image_index':1,'description':'绿色瓶子'}]}, {'image_indexes':[1]},Catalog().products)
    assert result['resolved_products']==[]


def test_summary_exposes_cards_without_becoming_recommendations(tmp_path):
    engine=Engine(tmp_path/'s.db',mode='mock')
    quote='祖玛珑蓝风铃 Cologne'
    engine.model.analyze_note=lambda *args,**kwargs: {'summary':'试香','mentions':[{'name':'蓝风铃','quote':quote,'product_id':'P013'}]}
    result=engine.run({'entry':'NOTE','note_action':'summary','message':'总结','note_context':{'text':quote}})
    assert result['products']==[]
    assert result['note_analysis']['resolved_products'][0]['product_id']=='P013'
    engine.close()


def test_paused_unversioned_name_never_exposes_stale_full_card():
    products=Catalog().products
    product=next(p for p in products if p['product_id']=='P016')
    product['reference_price_cny']=1240
    product['selling_points']='旧的未核实描述'
    result=validate_analysis({'summary':'试香','mentions':[{'name':'绿邂逅','quote':'绿邂逅','product_id':'P016'}]}, {'text':'绿邂逅'},products)
    card=result['resolved_products'][0]
    assert card['resolution_status']=='identity_only'
    assert card['reference_price_cny'] is None and 'selling_points' not in card


def test_unique_title_can_ground_body_reference_but_not_other_named_product():
    catalog=Catalog().products
    quote='这款耳机最大的卖点在于轻'
    note={'title':'索尼 WH-CH720N 学生测评','text':quote}
    raw={'summary':'评测','mentions':[{'name':'Sony WH-CH720N','quote':quote}]}
    result=validate_analysis(raw,note,catalog)
    assert result['resolved_products'][0]['product_id']=='H005'
    raw['mentions'][0]['name']='AirPods Pro 3'
    assert validate_analysis(raw,note,catalog)['resolved_products']==[]
