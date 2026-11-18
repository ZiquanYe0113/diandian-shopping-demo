"""Persist validated per-image observations; a failed request never erases successes."""
import hashlib,json,os,tempfile,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from .note_analysis import ImageObservation

VISION_VERSION='note-image-v1'

def cached_observations(images,model,path):
    """Read existing image evidence without scheduling any paid visual requests."""
    try:
        stored=json.loads(Path(path).read_text())
        if not isinstance(stored,dict):return []
    except (FileNotFoundError,json.JSONDecodeError):return []
    namespace=f'{VISION_VERSION}|{model.mode}|{getattr(model,"model", "mock")}|{getattr(getattr(model,"client",None),"base_url","")}'
    result=[]
    for image in images:
        key=hashlib.sha256((namespace+'|'+image['data_url']).encode()).hexdigest()
        try:
            observation=ImageObservation.model_validate(stored[key]).model_dump()
            observation['image_index']=image['index'];result.append(observation)
        except (KeyError,ValueError,TypeError):continue
    return result

def inspect_images(images,model,path,progress=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    try:
        stored=json.loads(path.read_text())
        if not isinstance(stored,dict):stored={}
    except (FileNotFoundError,json.JSONDecodeError):stored={}
    lock=threading.Lock();observations={};hits=0;pending=[]
    namespace=f'{VISION_VERSION}|{model.mode}|{getattr(model,"model", "mock")}|{getattr(getattr(model,"client",None),"base_url","")}'
    for image in images:
        key=hashlib.sha256((namespace+'|'+image['data_url']).encode()).hexdigest()
        try:
            cached=ImageObservation.model_validate(stored[key]).model_dump()
            cached['image_index']=image['index']
            observations[image['index']]=cached;hits+=1
        except (KeyError,ValueError,TypeError):pending.append((image,key))
    if progress:progress(f'复用图片识别 {hits}/{len(images)}，待识别 {len(pending)} 张')

    def inspect(image,key):
        raw=model.inspect_note_image(image)
        observation=ImageObservation.model_validate({**raw,'image_index':image['index']}).model_dump()
        if not any(observation[k].strip() for k in ('ocr_text','description','uncertainty')):
            raise ValueError('图片识别结果为空，请重试该图片')
        with lock:
            stored[key]=observation
            fd,tmp=tempfile.mkstemp(prefix='.vision-',dir=path.parent)
            try:
                with os.fdopen(fd,'w') as out:
                    json.dump(stored,out,ensure_ascii=False)
                os.replace(tmp,path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        return observation

    errors=[]
    with ThreadPoolExecutor(max_workers=2,thread_name_prefix='note-image') as pool:
        futures={pool.submit(inspect,image,key):image for image,key in pending}
        for future in as_completed(futures):
            try:
                observation=future.result();observations[observation['image_index']]=observation
            except Exception as error:errors.append((futures[future]['index'],error))
            if progress:progress(f'图片已识别 {len(observations)}/{len(images)}，失败 {len(errors)} 张')
    stats={'image_count':len(images),'image_cache_hits':hits,'image_model_calls':len(pending),
           'failed_image_indexes':sorted(index for index,_ in errors),'vision_version':VISION_VERSION}
    if errors:
        # Preserve the original exception type for correct quota/timeout reporting.
        error=errors[0][1];error.image_stats=stats
        raise error
    return [observations[im['index']] for im in images],stats
