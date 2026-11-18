import base64,io,uuid
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlparse
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,field_validator
from PIL import Image
from .config import ROOT,settings
from .workflow import Engine
from .jobs import Jobs,JobConflict
from .xhs_source import XhsSource
from pathlib import Path

class ChatRequest(BaseModel):
    entry:Literal['NOTE','SEARCH','CHAT']
    message:str=Field(min_length=1,max_length=6000)
    session_id:uuid.UUID|None=None
    note_context:dict[str,str]=Field(default_factory=dict)
    images:list[str]=Field(default_factory=list,max_length=3)
    note_action:Literal['summary','extract','shop']|None=None
    @field_validator('note_context')
    @classmethod
    def validate_note(cls,v):
        if any(len(k)>100 or len(value)>20000 for k,value in v.items()) or len(v)>8: raise ValueError('笔记内容过长')
        return v
    @field_validator('images')
    @classmethod
    def validate_images(cls,images):
        for image in images:
            prefix,sep,raw=image.partition(',')
            if not sep or prefix not in ('data:image/jpeg;base64','data:image/png;base64','data:image/webp;base64'): raise ValueError('仅接受本地 JPEG/PNG/WebP 图片')
            if len(raw)>7_000_000: raise ValueError('图片超过5MB')
            data=base64.b64decode(raw,validate=True)
            if len(data)>5*1024*1024: raise ValueError('图片超过5MB')
            try:
                with Image.open(io.BytesIO(data)) as im:
                    if im.width*im.height>30_000_000: raise ValueError('图片尺寸过大')
                    im.verify()
            except Exception as e: raise ValueError('无效图片') from e
        return images

class JobRequest(ChatRequest):
    request_id:uuid.UUID

class XhsNoteRequest(BaseModel):
    url:str=Field(min_length=1,max_length=12000)

def create_app(engine=None, source=None):
    xhs=source or XhsSource(ROOT/'runtime/xhs-mcp/notes.json')
    owned=engine is None
    eng=engine or Engine(ROOT/'runtime/sessions.db',agent_enabled=True,**settings())
    from .local_examples import analysis_images
    from .curated_notes import analysis_images as curated_images,with_cached_images
    eng.note_image_loader=lambda note_id:analysis_images(note_id) if note_id.startswith('local:') else curated_images(note_id,xhs) if note_id.startswith('curated:') else xhs.analysis_images(note_id)
    eng.agent_source=xhs
    dbpath=eng.conn.execute('PRAGMA database_list').fetchone()[2]
    jobs=Jobs(Path(dbpath).parent/'requests.db' if dbpath else ':memory:',eng)
    @asynccontextmanager
    async def lifespan(app):
        yield
        jobs.close()
        if owned: eng.close()
    app=FastAPI(lifespan=lifespan)
    @app.middleware('http')
    async def local_only(request:Request,call_next):
        origin=request.headers.get('origin')
        host=request.headers.get('host','').split(':')[0]
        if host not in ('127.0.0.1','localhost','testserver'): return JSONResponse({'detail':'仅支持本地访问'},403)
        if request.method=='POST' and origin and urlparse(origin).netloc!=request.headers.get('host'): return JSONResponse({'detail':'禁止跨站请求'},403)
        if request.method=='POST' and int(request.headers.get('content-length','0'))>22_000_000: return JSONResponse({'detail':'请求过大'},413)
        return await call_next(request)
    @app.get('/api/xhs/status')
    def xhs_status(): return xhs.status()
    @app.post('/api/xhs/login')
    def xhs_login():
        try: return xhs.login()
        except ValueError as error: raise HTTPException(400,str(error))
    @app.post('/api/xhs/notes')
    def xhs_read(body:XhsNoteRequest):
        try: return {'note':xhs.read_note(body.url)}
        except ValueError as error: raise HTTPException(400,str(error))
    @app.get('/api/xhs/notes')
    def xhs_notes():
        try: return {'notes':xhs.list_notes()}
        except ValueError as error: raise HTTPException(400,str(error))
    @app.get('/api/xhs/images/{note_id}/{index}')
    def xhs_image(note_id:str,index:int):
        try:return FileResponse(xhs.image_path(note_id,index),media_type='image/jpeg',headers={'Cache-Control':'no-store'})
        except ValueError as error:raise HTTPException(404,str(error))
    @app.get('/api/health')
    def health(): return {'mode':eng.model.mode,'model':getattr(eng.model,'model','mock'),'key_configured':bool(getattr(eng.model,'key','')),'products':len(eng.catalog.products),'notes':len(eng.catalog.notes),'agent_enabled':eng.agent_enabled}
    @app.get('/api/catalog')
    def catalog():
        try:cached={n['note_id']:n for n in xhs.list_notes()}
        except ValueError:cached={}
        return {'products':eng.catalog.products,'notes':[with_cached_images(n,cached) for n in eng.catalog.notes]}
    @app.post('/api/chat')
    def chat(body:ChatRequest):
        payload=body.model_dump(mode='json'); return eng.run(payload)
    @app.post('/api/jobs')
    def submit_job(body:JobRequest):
        payload=body.model_dump(mode='json'); rid=payload.pop('request_id')
        try: return jobs.submit(rid,payload)
        except JobConflict as error: raise HTTPException(409,str(error))
    @app.get('/api/jobs/{rid}')
    def read_job(rid:uuid.UUID):
        result=jobs.get(str(rid))
        if result is None: raise HTTPException(404,'请求记录不存在，请手动重试')
        return result
    @app.get('/api/session/{sid}')
    def session(sid:uuid.UUID): return eng.session(str(sid))
    @app.get('/')
    def index(): return FileResponse(ROOT/'web/xhs/index.html')
    app.mount('/web',StaticFiles(directory=ROOT/'web'),name='web')
    return app
