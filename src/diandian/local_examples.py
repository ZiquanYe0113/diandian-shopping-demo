"""Own, fixed fact-card images: no MCP, network, or user filesystem paths."""
import base64,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def notes():
    path=ROOT/'data/local-examples.json'
    return json.loads(path.read_text())['notes'] if path.exists() else []

def analysis_images(note_id):
    if note_id.startswith('curated:'):
        from .curated_notes import analysis_images as curated_images
        return curated_images(note_id)
    note=next((n for n in notes() if n['note_id']==note_id),None)
    if not note:raise ValueError('本地图文示例不存在')
    result=[]
    for image in note.get('images',[])[:3]:
        name=Path(image['src']).name
        if image['src']!='/web/examples/'+name or not name.endswith('.png'):raise ValueError('非法本地示例图片')
        data=(ROOT/'web/examples'/name).read_bytes()
        result.append({'index':image['index'],'data_url':'data:image/png;base64,'+base64.b64encode(data).decode()})
    return result
