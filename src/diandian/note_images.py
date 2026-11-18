"""Bounded public XHS image downloads; no cookies, proxies or model credentials."""
import hashlib,io,os,tempfile
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import httpx
from PIL import Image,ImageOps

MAX_IMAGES=20
MAX_BYTES=8*1024*1024

def image_url(raw):
    candidates=[]
    if isinstance(raw,dict):
        candidates += [item.get('url') for item in raw.get('infoList',raw.get('info_list',[])) if isinstance(item,dict) and item.get('imageScene',item.get('image_scene'))=='WB_DFT']
        candidates += [raw.get('urlDefault'),raw.get('url_default'),raw.get('url')]
        candidates += [item.get('url') for item in raw.get('infoList',raw.get('info_list',[])) if isinstance(item,dict)]
    for url in candidates:
        if not isinstance(url,str) or len(url)>6000:continue
        try:
            p=urlsplit(url);host=p.hostname or ''
            if p.scheme not in ('https','http') or p.port not in (None,443) or p.username or p.password:continue
            if not any(host==domain or host.endswith('.'+domain) for domain in ('xhscdn.com','xhsimg.com')):continue
            # Upstream may return an HTTP CDN URL; fetch the same resource over HTTPS only.
            return urlunsplit(('https',p.netloc,p.path,p.query,''))
        except ValueError:continue
    return ''

def save_image(client,url,folder):
    key=hashlib.sha256(url.encode()).hexdigest();path=folder/(key+'.jpg')
    if path.exists():
        data=path.read_bytes()
        if len(data)<=MAX_BYTES:return path,hashlib.sha256(data).hexdigest()
    with client.stream('GET',url,timeout=httpx.Timeout(12,connect=5)) as response:
        response.raise_for_status()
        if response.is_redirect:raise ValueError('图片地址发生跳转')
        if int(response.headers.get('content-length','0'))>MAX_BYTES:raise ValueError('图片过大')
        chunks=[];size=0
        for chunk in response.iter_bytes():
            size+=len(chunk)
            if size>MAX_BYTES:raise ValueError('图片过大')
            chunks.append(chunk)
    with Image.open(io.BytesIO(b''.join(chunks))) as original:
        if original.width*original.height>30_000_000:raise ValueError('图片尺寸过大')
        picture=ImageOps.exif_transpose(original).convert('RGB')
        picture.thumbnail((2400,2400),Image.Resampling.LANCZOS)
        out=io.BytesIO();picture.save(out,format='JPEG',quality=92)
    data=out.getvalue()
    if len(data)>MAX_BYTES:raise ValueError('图片过大')
    folder.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=folder,prefix='.image-')
    try:
        with os.fdopen(fd,'wb') as f:f.write(data)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
    return path,hashlib.sha256(data).hexdigest()
