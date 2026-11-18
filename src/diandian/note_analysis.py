"""Validate note mentions against visible text and catalog versions."""
import re
NOTE_ANALYSIS_VERSION="product-cards-20261017-v2"
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict

class Mention(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(max_length=300)
    quote:str=Field(max_length=1200)
    product_id:str|None=None
    source:Literal['text','image_text','image_visual']='text'
    image_index:int|None=Field(default=None,ge=1,le=20)
    confidence:Literal['confirmed','uncertain']='confirmed'

class ImageObservation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    image_index:int=Field(ge=1,le=20)
    ocr_text:str=Field(default='',max_length=12000)
    description:str=Field(default='',max_length=2000)
    uncertainty:str=Field(default='',max_length=1000)

class NoteAnalysis(BaseModel):
    model_config=ConfigDict(extra='forbid')
    summary:str=Field(max_length=3000)
    key_points:list[str]=Field(default_factory=list,description="归纳最多3条重点")
    author_opinion:str=Field(default='',max_length=2000)
    mentions:list[Mention]=Field(default_factory=list)
    image_observations:list[ImageObservation]=Field(default_factory=list,max_length=20)

def matching_products(quote,products):
    q=quote.casefold()
    matches=[]
    versions=set(re.findall(r'(?<![a-z])(?:edp|edt|edc|elixir|cologne|candle)(?![a-z])',q))
    if any(v in q for v in ('浓香水','淡香精','浓香精')): versions.add('edp')
    if '淡香水' in q: versions.add('edt')
    if '古龙水' in q: versions.update(('edc','cologne'))
    if '香精版' in q: versions.add('elixir')
    for p in products:
        aliases=[p['product_name']]+p['aliases'].split(';')
        if not any(len(a.strip())>2 and a.casefold() in q for a in aliases): continue
        if p.get('category')!='耳机' and versions and p.get('concentration','').casefold() not in versions: continue
        # Elixir is a distinct version; a generic name cannot confirm it.
        if p.get('concentration','').casefold()=='elixir' and 'elixir' not in versions: continue
        matches.append(p)
    # Specificity only disambiguates variants sharing a family alias. Independent
    # products in the same sentence must remain visible for attribution checks.
    earphones=[p for p in matches if p.get('category')=='耳机']
    compact=lambda v:re.sub(r'\s+','',v.casefold())
    aliases=lambda p:{compact(a) for a in [p['product_name']]+p['aliases'].split(';') if a}
    drop=set()
    for p in earphones:
        family=[other for other in earphones if aliases(p)&aliases(other)]
        unique=aliases(p)-set().union(*(aliases(other) for other in family if other is not p))
        identified=any(a in compact(q) for a in unique)
        if not identified:
            for other in family:
                other_unique=aliases(other)-set().union(*(aliases(v) for v in family if v is not other))
                if any(a in compact(q) for a in other_unique):drop.add(p['product_id'])
    matches=[p for p in matches if p['product_id'] not in drop]
    return matches

def validate_analysis(raw,note,products):
    parsed=NoteAnalysis.model_validate(raw).model_dump()
    # Remove literal duplication; this is not a semantic fact checker.
    normalize=lambda value: re.sub(r'[\s，。！？；：、,.!?;:•]', '', value)
    seen_points=[normalize(parsed['summary'])]
    points=[]
    for point in parsed['key_points']:
        normalized=normalize(point)
        if not normalized or any(normalized in old for old in seen_points): continue
        points.append(point); seen_points.append(normalized)
        if len(points)==3: break
    parsed['key_points']=points
    opinion=normalize(parsed['author_opinion'])
    if opinion and any(opinion in old for old in seen_points): parsed['author_opinion']=''
    text=note.get('text','')+'\n'+note.get('title','')
    image_indexes=set(note.get('image_indexes',[]))
    observations={}
    for observation in parsed['image_observations']:
        index=observation['image_index']
        if index in image_indexes and index not in observations:observations[index]=observation
    parsed['image_observations']=list(observations.values())
    parsed['image_coverage']={'provided':sorted(image_indexes),'analyzed':sorted(observations),'missing':sorted(image_indexes-set(observations))}
    mentions=[]; seen=set(); cards={}
    by_id={p['product_id']:p for p in products}
    for m in parsed['mentions']:
        quote=m['quote'].strip()
        source=m['source'];index=m['image_index']
        if source=='text':
            reference=text;m['image_index']=None
        else:
            observation=observations.get(index)
            if not observation:continue
            reference=observation['ocr_text'] if source=='image_text' else observation['description']
        signature=(m['name'],quote,source,index)
        if not quote or quote not in reference or signature in seen:continue
        seen.add(signature)
        candidates=matching_products(quote,products) if source!='image_visual' and m['confidence']=='confirmed' else []
        if source=='image_visual':m['confidence']='uncertain'
        pid=m['product_id']
        if len(candidates)!=1 or candidates[0]['product_id']!=pid: pid=None
        # A single-product title can ground "this product" in its body. Require
        # the model's name and the whole note to identify that same unique item;
        # comparison posts and image guesses must not inherit the title's facts.
        if not pid and not candidates and source=='text' and m['confidence']=='confirmed':
            titled=matching_products(note.get('title',''),products)
            named=matching_products(m['name'],products)
            whole=matching_products(text,products)
            if len(titled)==len(named)==len(whole)==1 and titled[0]['product_id']==named[0]['product_id']==whole[0]['product_id']:
                pid=titled[0]['product_id']
        # A paused historical index can identify a family, never a version or
        # recommendation. Resolve from quoted evidence, not the model's name.
        identity_pid=None
        if pid and by_id[pid].get('verified_for_recommendation') is False and not by_id[pid].get('concentration'):
            identity_pid=pid;pid=None
        if not pid and source!='image_visual' and m['confidence']=='confirmed':
            named=[p for p in products if any(len(a.strip())>2 and a.strip().casefold() in quote.casefold()
                for a in [p['product_name']]+p['aliases'].split(';'))]
            if len(named)==1 and not named[0].get('concentration') and named[0].get('verified_for_recommendation') is False:
                identity_pid=named[0]['product_id']
        mention={**m,'quote':quote,'product_id':pid,'match_status':'matched' if pid else 'unconfirmed',
            'identity_product_id':identity_pid}
        mentions.append(mention)
        card_id=pid or identity_pid
        if card_id:
            if card_id not in cards:
                product=by_id[card_id]
                if identity_pid:
                    # Whitelist identity labels: historical rows can retain stale
                    # attributes even when recommendation verification is paused.
                    card={k:product.get(k,'') for k in ('product_id','brand','product_name','category')}
                    card.update(reference_price_cny=None,actual_spec_value=None,actual_spec_unit='',
                        concentration='',verified_for_recommendation=False,
                        resolution_status='identity_only',resolution_notice='仅识别历史名称索引；具体版本、规格和价格尚未核验。')
                else:
                    card={**product,'resolution_status':'matched','resolution_notice':''}
                cards[card_id]={**card,'mention_evidence':[]}
            evidence={k:mention[k] for k in ('name','quote','source','image_index','confidence')}
            if evidence not in cards[card_id]['mention_evidence']:cards[card_id]['mention_evidence'].append(evidence)
    return {**parsed,'mentions':mentions,'resolved_products':list(cards.values())}
