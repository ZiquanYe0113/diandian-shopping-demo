"""Original post text and image-only fallbacks stay separate from AI summaries."""
from fastapi.testclient import TestClient
from diandian.catalog import Catalog
from diandian.workflow import Engine
from diandian.server import create_app
from diandian.xhs_source import XhsSource


def test_reader_notes_have_real_sources_and_never_supply_catalog_prices():
    c=Catalog(); curated=[n for n in c.notes if n.get('curated')]
    assert len(curated)==3
    for n in curated:
        assert n['source_note_id'].startswith('xhs:')
        assert n['source_url']=='https://www.xiaohongshu.com/explore/'+n['source_note_id'][4:]
        assert n['source_author'] and n['original_title']
        assert not n.get('real') and not n.get('local_example')
        assert 'reference_price_cny' not in n
    product=next(p for p in c.products if p['product_id']=='H005')
    assert product['price_verified'] and product['price_source_url'].startswith('https://www.sonystyle.com.cn/')


def test_only_corresponding_original_images_are_attached():
    from diandian.curated_notes import with_cached_images
    note={'note_id':'curated:test','curated':True,'source_note_id':'xhs:'+'a'*24}
    other={'note_id':'xhs:'+'b'*24,'images':[{'index':1,'src':'/wrong'}]}
    assert not with_cached_images(note,{other['note_id']:other})['images']
    raw={'note_id':note['source_note_id'],'images':[{'index':1,'src':'/api/xhs/images/'+'a'*24+'/1'}],'image_total':1,'image_revision':'v'}
    decorated=with_cached_images(note,{raw['note_id']:raw})
    assert decorated['images']==raw['images'] and decorated['image_revision']=='v'
    assert 'images' not in note


def test_cached_original_replaces_all_editorial_copy_verbatim():
    from diandian.curated_notes import with_cached_images
    seed={'note_id':'curated:test','curated':True,'source_note_id':'xhs:'+'a'*24,
          'title':'编辑标题','text':'编辑归纳','displayText':'旧展示摘要','source_author':'旧作者'}
    raw={'note_id':seed['source_note_id'],'title':'原帖标题','text':'第一段\n\n作者原话 #标签', 'author':'原作者'}
    result=with_cached_images(seed,{raw['note_id']:raw})
    assert result['title']=='原帖标题' and result['author']=='原作者'
    assert result['text']=='第一段\n\n作者原话 #标签'
    assert not result.get('displayText') or result['displayText']==result['text']
    assert with_cached_images(seed,{})['text']==''
    raw['text']=''
    assert with_cached_images(seed,{raw['note_id']:raw})['text']==''


def test_curated_notes_are_usable_without_mcp_or_an_api_key(tmp_path):
    e=Engine(tmp_path/'s.db',mode='mock')
    try:
        with TestClient(create_app(e,source=XhsSource(tmp_path/'no-cache.json'))) as client:
            note=next(n for n in client.get('/api/catalog').json()['notes'] if n.get('curated'))
            assert note['images']==[]
            r=client.post('/api/chat',json={'entry':'NOTE','note_action':'summary','message':'帮我总结一下这篇笔记。','note_context':{k:note[k] for k in ('note_id','title','text')}}).json()
            assert r['status']=='NOTE_SUMMARY' and r['usage']==[]
    finally:e.close()


def test_normal_catalog_does_not_expose_internal_fact_cards():
    c=Catalog()
    assert any(n.get('curated') for n in c.notes)
    assert all(not n.get('local_example') for n in c.notes)


def test_agent_reads_original_body_instead_of_seed_or_cached_editorial_copy(tmp_path):
    from diandian.agent import AgentTools
    from diandian.curated_notes import notes
    e=Engine(tmp_path/'s.db',mode='mock')
    seed=notes()[0]
    class Source:
        def list_notes(self):return [{'note_id':seed['source_note_id'],'title':'原帖','author':'作者','text':'作者原话，不是点点的总结。'}]
    e.agent_source=Source()
    try:
        r=AgentTools(e).read(seed['note_id'])
        assert r['text']=='作者原话，不是点点的总结。'
        assert r['title']=='原帖' and r['author']=='作者'
    finally:e.close()
