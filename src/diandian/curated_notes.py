"""Source references with verbatim cached text; never substitute editorial copy."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def notes():
    path=ROOT/'data/curated-notes.json'
    result=json.loads(path.read_text())['notes'] if path.exists() else []
    for note in result:
        nid=note.get('source_note_id','')
        if not re.fullmatch(r'xhs:[a-f0-9]{24}',nid) or note.get('source_url')!='https://www.xiaohongshu.com/explore/'+nid[4:]:
            raise ValueError('整理笔记来源无效')
    from .xhs_source import XhsSource
    try:cached={n['note_id']:n for n in XhsSource(ROOT/'runtime/xhs-mcp/notes.json').list_notes()}
    except ValueError:cached={}
    return [with_cached_images(n,cached) for n in result]

def with_cached_images(note,by_id):
    if not note.get('curated'):return note
    original=by_id.get(note['source_note_id'],{})
    images=original.get('images',[])
    text=original.get('text','')
    title=original.get('title',note.get('original_title',''))
    author=original.get('author',note.get('source_author',''))
    return {**note,'title':title,'text':text,'displayText':text,'author':author,
        'source_author':author,'original_title':title,'images':images,'image_total':len(images),
        'image_revision':original.get('image_revision',''),'original_image_total':original.get('image_total',0)}

def analysis_images(note_id,source=None):
    note=next((n for n in notes() if n['note_id']==note_id),None)
    if not note:raise ValueError('整理笔记不存在')
    if source is None:return []
    original=next((n for n in source.list_notes() if n['note_id']==note['source_note_id']),None)
    if not original or not original.get('images'):return []
    return source.analysis_images(original['note_id'])
