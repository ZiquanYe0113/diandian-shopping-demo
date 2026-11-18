"""Read-only adapter for the isolated localhost xiaohongshu-mcp service."""
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlencode
import httpx

HOSTS = {'xiaohongshu.com', 'www.xiaohongshu.com', 'xhslink.com', 'xhslink.cn', 'www.xhslink.com', 'www.xhslink.cn'}
SHORT_HOSTS = {'xhslink.com', 'xhslink.cn', 'www.xhslink.com', 'www.xhslink.cn'}
from .note_images import image_url,save_image,MAX_IMAGES

UNAVAILABLE = '本地小红书读取服务未就绪，请先启动服务'

class XhsPageError(ValueError): pass

class XhsSource:
    def __init__(self, cache_path: Path, *, transport=None):
        self.cache_path = Path(cache_path)
        self.transport = transport
        self.lock = threading.RLock()
        self.search_access = {}

    def _client(self):
        # No environment proxy, automatic redirects, cookie persistence or retries.
        return httpx.Client(timeout=httpx.Timeout(45, connect=5), follow_redirects=False,
                            trust_env=False, transport=self.transport)

    def _upstream(self, method, path, **kwargs):
        try:
            token_path = self.cache_path.parent/'data/service-token'
            headers = {}
            try:
                service_token = token_path.read_text(encoding='utf-8').strip() if token_path.exists() else ''
            except OSError: raise ValueError('本地服务凭证无法读取，请检查服务配置') from None
            if service_token:
                if not re.fullmatch(r'[A-Za-z0-9_.~-]{1,512}',service_token): raise ValueError('本地服务凭证格式无效')
                headers['Authorization'] = 'Bearer '+service_token
            with self._client() as client:
                response = client.request(method, 'http://127.0.0.1:18060/api/v1/'+path, headers=headers, **kwargs)
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict) or payload.get('success') is not True:
                raise XhsPageError('小红书页面读取失败，请重试登录检查或重新分享笔记链接')
            data = payload.get('data')
            if not isinstance(data, dict): raise ValueError('读取服务返回的数据无效')
            return data
        except httpx.TimeoutException:
            raise XhsPageError('小红书页面响应超时，登录状态暂未确认；已保存的笔记仍可分析') from None
        except httpx.HTTPStatusError:
            raise XhsPageError('小红书页面读取未完成，请重试；已保存的笔记仍可分析') from None
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            raise ValueError(UNAVAILABLE) from None

    def status(self):
        try:
            data = self._upstream('GET', 'login/status')
            logged_in = data.get('is_logged_in') is True
            return {'available': True, 'logged_in': logged_in,
                    'message': '已登录，可读取公开笔记' if logged_in else '请扫码登录小红书'}
        except XhsPageError as error:
            return {'available': True, 'logged_in': None, 'message':str(error)}
        except ValueError as error:
            return {'available': False, 'logged_in': False, 'message': str(error)}

    def login(self):
        data = self._upstream('GET', 'login/qrcode')
        if data.get('is_logged_in') is True:
            return {'image': '', 'timeout': 0, 'message': '已登录，可读取公开笔记'}
        image = data.get('img', '')
        if not isinstance(image, str) or not re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+', image) or len(image)>2_000_000:
            raise ValueError('登录二维码无效，请重试')
        duration = str(data.get('timeout', '300'))
        if duration.isdigit(): timeout = int(duration)
        elif re.fullmatch(r'(?:[0-9]+(?:\.[0-9]+)?[hms])+',duration):
            timeout = int(sum(float(value)*{'h':3600,'m':60,'s':1}[unit] for value,unit in re.findall(r'([0-9]+(?:\.[0-9]+)?)([hms])',duration)))
        else: raise ValueError('登录二维码有效期无效')
        return {'image': image, 'timeout': max(0, min(timeout, 600)), 'message': '请用小红书扫码，完成后检查登录状态'}

    def search_notes(self,query,limit=5):
        query=query.strip()
        if not query or len(query)>120 or not 1<=limit<=10:raise ValueError('笔记搜索参数无效')
        payload=self._upstream('POST','feeds/search',json={'keyword':query})
        feeds=payload.get('feeds')
        if not isinstance(feeds,list):raise ValueError('搜索服务返回的笔记列表无效')
        result=[];seen=set()
        with self.lock:
            for feed in feeds:
                if not isinstance(feed,dict):continue
                card=feed.get('noteCard',{});nid=feed.get('id','');token=feed.get('xsecToken','')
                if not isinstance(card,dict) or card.get('type')!='normal':continue
                if not isinstance(nid,str) or not re.fullmatch(r'[a-f0-9]{24}',nid) or nid in seen:continue
                if not isinstance(token,str) or not token or len(token)>2048:continue
                title=card.get('displayTitle','')
                if not isinstance(title,str):continue
                seen.add(nid);self.search_access[nid]=token
                result.append({'note_id':'xhs:'+nid,'title':title[:500],
                    'source_url':f'https://www.xiaohongshu.com/explore/{nid}','source':'xhs_search'})
                if len(result)>=limit:break
        return result

    def read_searched_note(self,note_id):
        if not isinstance(note_id,str) or not re.fullmatch(r'xhs:[a-f0-9]{24}',note_id):raise ValueError('笔记ID无效')
        with self.lock:
            cached=next((n for n in self.list_notes() if n['note_id']==note_id),None)
            token=self.search_access.get(note_id[4:])
        if cached:return cached
        if not token:raise ValueError('只能读取搜索结果或已保存的笔记')
        share=f'https://www.xiaohongshu.com/explore/{note_id[4:]}?'+urlencode({'xsec_token':token})
        return self.read_note(share)

    @staticmethod
    def _validate_url(url):
        try:
            parts = urlsplit(url)
            valid = parts.scheme == 'https' and parts.hostname in HOSTS and parts.port in (None, 443) and not parts.username and not parts.password
        except ValueError: valid = False
        if not valid: raise ValueError('仅支持 HTTPS 小红书笔记分享链接')
        return parts

    def _resolve(self, share):
        matches = re.findall(r'https?://[^\s<>"\u3000]+', share)
        if len(matches) != 1: raise ValueError('请粘贴一个完整的小红书笔记分享链接')
        url = matches[0].rstrip('，。；！）)]}')
        for hop in range(5):
            parts = self._validate_url(url)
            if parts.hostname not in SHORT_HOSTS:
                match = re.fullmatch(r'/(?:explore|discovery/item)/([a-fA-F0-9]{24})/?', parts.path)
                if not match: raise ValueError('链接必须指向一篇小红书笔记')
                tokens = parse_qs(parts.query).get('xsec_token', [])
                if len(tokens)!=1 or not tokens[0] or len(tokens[0])>2048:
                    raise ValueError('笔记链接缺少访问参数，请从小红书重新分享完整链接，或补充正文')
                return match[1].lower(), tokens[0]
            if not parts.path or parts.path=='/': raise ValueError('短链接无效，请重新分享')
            try:
                with self._client() as client: response = client.get(url)
            except httpx.HTTPError: raise ValueError('短链接读取失败，请重新分享完整链接') from None
            if response.status_code not in (301,302,303,307,308) or not response.headers.get('location'):
                raise ValueError('短链接没有返回笔记地址，请重新分享完整链接')
            url = urljoin(url, response.headers['location'])
            self._validate_url(url)
        raise ValueError('短链接跳转过多，请重新分享完整链接')

    def read_note(self, share):
        note_id, token = self._resolve(share)
        payload = self._upstream('POST','feeds/detail',json={'feed_id':note_id,'xsec_token':token,'load_all_comments':False})
        try: raw = payload['data']['note']
        except (KeyError, TypeError): raise ValueError('读取服务未返回笔记正文') from None
        if not isinstance(raw, dict) or str(raw.get('noteId', '')).lower()!=note_id:
            raise ValueError('读取服务返回的笔记与链接不一致')
        text = raw.get('desc')
        if not isinstance(text,str): raise ValueError('笔记正文格式无效')
        title = raw.get('title', '')
        if not isinstance(title,str): raise ValueError('笔记标题格式无效')
        if len(text)>20000 or len(title)>20000: raise ValueError('笔记正文超过 20000 字限制，请手动选择较短正文')
        user = raw.get('user', {})
        author = (user.get('nickname') or user.get('nickName') or '') if isinstance(user,dict) else ''
        note = {'note_id':'xhs:'+note_id,'title':title,'text':text,'source_url':f'https://www.xiaohongshu.com/explore/{note_id}',
                'author':author if isinstance(author,str) else '', 'fetched_at':datetime.now(timezone.utc).isoformat(), 'product_ids':[], 'real':True}
        note.update(self._read_images(note_id,raw.get('imageList',[])))
        if not text.strip() and not note['images']: raise ValueError('笔记正文与图片均未读取成功，请重新分享或换一篇笔记')
        with self.lock:
            notes = {n['note_id']:n for n in self.list_notes()}
            notes[note['note_id']] = note
            self.cache_path.parent.mkdir(parents=True,exist_ok=True)
            fd, name = tempfile.mkstemp(dir=self.cache_path.parent,prefix='.notes-',suffix='.json')
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as file:
                    json.dump(list(notes.values()),file,ensure_ascii=False); file.flush(); os.fsync(file.fileno())
                os.replace(name,self.cache_path)
            except OSError: raise ValueError('真实笔记保存失败，请检查运行目录权限后重试') from None
            finally:
                if os.path.exists(name): os.unlink(name)
        return note

    def list_notes(self):
        with self.lock:
            if not self.cache_path.exists(): return []
            try:
                data = json.loads(self.cache_path.read_text(encoding='utf-8'))
                if not isinstance(data,list): raise ValueError()
                result=[]
                for n in data:
                    if not isinstance(n,dict) or n.get('real') is not True or not re.fullmatch(r'xhs:[a-f0-9]{24}',n.get('note_id','')): raise ValueError()
                    if any(not isinstance(n.get(k),str) for k in ('title','text','author','fetched_at')) or len(n['text'])>20000: raise ValueError()
                    # Whitelist persisted fields; remove query parameters even from old caches.
                    safe = {k:n[k] for k in ('note_id','title','text','author','fetched_at')}
                    safe.update(source_url=f"https://www.xiaohongshu.com/explore/{n['note_id'][4:]}",product_ids=[],real=True)
                    images=[]
                    for item in n.get('images',[]):
                        if not isinstance(item,dict) or not isinstance(item.get('index'),int) or not 1<=item['index']<=MAX_IMAGES or not re.fullmatch(r'[a-f0-9]{64}',item.get('cache_key','')): raise ValueError()
                        images.append({'index':item['index'],'src':f"/api/xhs/images/{n['note_id'][4:]}/{item['index']}",'cache_key':item['cache_key']})
                    safe.update(images=images,image_total=n.get('image_total',len(images)),image_warnings=n.get('image_warnings',[]) if 'images' in n else ['旧版只保存了正文；请重新导入原分享链接，补齐笔记图片。'],image_revision=n.get('image_revision',''))
                    if not safe['text'].strip() and not images:raise ValueError()
                    result.append(safe)
                return result
            except (OSError,ValueError,TypeError): raise ValueError('真实笔记缓存损坏，请检查 notes.json 后重试') from None

    def _read_images(self,note_id,raw_images):
        raw_images=raw_images if isinstance(raw_images,list) else []
        def read(pair):
            index,raw=pair;url=image_url(raw)
            if not url:return None,f'第 {index} 张图片地址不可用，未参与分析。'
            try:
                with self._client() as client:path,digest=save_image(client,url,self.cache_path.parent/'images'/note_id)
                return {'index':index,'src':f'/api/xhs/images/{note_id}/{index}','cache_key':path.stem,'digest':digest},''
            except Exception:
                return None,f'第 {index} 张图片读取失败，未参与分析；可重新读取笔记重试。'
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(read,enumerate(raw_images[:MAX_IMAGES],1)))
        images=[item for item,_ in results if item];warnings=[warning for _,warning in results if warning]
        if len(raw_images)>MAX_IMAGES:warnings.append(f'本次最多分析 {MAX_IMAGES} 张图，其余图片未读取。')
        revision=hashlib.sha256(json.dumps([(im['index'],im['digest']) for im in images]).encode()).hexdigest() if raw_images else ''
        for item in images:item.pop('digest')
        return {'images':images,'image_total':len(raw_images),'image_warnings':warnings,'image_revision':revision}

    def image_path(self,note_id,index):
        if not re.fullmatch(r'[a-f0-9]{24}',note_id) or not 1<=index<=MAX_IMAGES:raise ValueError('图片不存在')
        note=next((n for n in self.list_notes() if n['note_id']=='xhs:'+note_id),None)
        item=next((im for im in note.get('images',[]) if im['index']==index),None) if note else None
        if not item:raise ValueError('图片不存在，请重新读取笔记')
        path=self.cache_path.parent/'images'/note_id/(item['cache_key']+'.jpg')
        if not path.is_file():raise ValueError('本地图片已缺失，请重新读取笔记')
        return path

    def analysis_images(self,note_id):
        note=next((n for n in self.list_notes() if n['note_id']==note_id),None)
        if not note:raise ValueError('真实笔记未保存，请先读取笔记')
        if note['image_total'] and not note['images']:raise ValueError('笔记图片全部读取失败，请重新读取后再分析')
        return [{'index':im['index'],'data_url':'data:image/jpeg;base64,'+base64.b64encode(self.image_path(note_id[4:],im['index']).read_bytes()).decode()} for im in note['images']]
