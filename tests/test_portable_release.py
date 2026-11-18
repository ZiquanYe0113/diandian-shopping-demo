"""Public reproduction boundary, independent of personal keys and source fixtures."""
import importlib.util,json,zipfile,re
from pathlib import Path
from fastapi.testclient import TestClient
from diandian.workflow import Engine
from diandian.server import create_app
ROOT=Path(__file__).resolve().parents[1]


def test_explicit_mock_overrides_local_env_and_needs_no_key(monkeypatch,tmp_path):
    from diandian.__main__ import runtime_options
    monkeypatch.setenv('MODEL_MODE','real');monkeypatch.delenv('DASHSCOPE_API_KEY',raising=False)
    options=runtime_options(['--mode','mock','--port','4190'])
    assert options['settings']['mode']=='mock'
    e=Engine(tmp_path/'s.db',agent_enabled=True,**options['settings'])
    try:
        with TestClient(create_app(e)) as client:
            assert client.get('/api/health').json()['mode']=='mock'
            catalog=client.get('/api/catalog').json()
            assert len(catalog['products'])==25
            assert any(n.get('curated') for n in catalog['notes'])
            assert not any(n.get('local_example') for n in catalog['notes'])
            assert client.get('/web/examples/airpods-5.png').status_code==200
            r=client.post('/api/chat',json={'entry':'CHAT','message':'1000元耳机通勤'}).json()
            assert r['status']=='READY' and r['products']
            assert all(p['category']=='耳机' and p['reference_price_cny']<=1000 for p in r['products'])
    finally:e.close()


def test_release_excludes_runtime_secrets_and_unreviewed_media(tmp_path):
    spec=importlib.util.spec_from_file_location('release',ROOT/'scripts/package_release.py')
    assert spec is not None
    release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
    output=release.package(tmp_path/'public.zip')
    with zipfile.ZipFile(output) as z:
        names=set(z.namelist())
        assert 'README.md' in names and 'data/source/headphones.json' in names and 'web/examples/airpods-5.png' in names
        assert '.env.example' in names
        assert all(n['text']=='' for n in json.loads(z.read('data/curated-notes.json'))['notes'])
        assert not any(n=='.env' or n.startswith(('runtime/','results/','.venv/','web/reference/assets/')) or n.endswith('.pyc') for n in names)
        assert not any(re.search(r'ws-[a-z0-9]+\.cn-',z.read(n).decode('utf-8',errors='ignore')) for n in names if n.endswith(('.py','.md','.html','.js','.example')))
