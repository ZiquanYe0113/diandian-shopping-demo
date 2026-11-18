"""Typed catalog facts. Unknown values and incompatible test modes never pass."""
from urllib.parse import urlparse
import re

STYLE_ALIASES={'in-ear':'入耳式','in ear':'入耳式','over-ear':'头戴包耳式','over ear':'头戴包耳式','on-ear':'头戴贴耳式','on ear':'头戴贴耳式'}

def numeric_quote_values(f):
    units=r'(?:小时|小時|hours?|hrs?|h)' if f['key'].startswith('battery') else r'(?:克|grams?|g)'
    return list(re.finditer(r'(\d+(?:\.\d+)?)\s*'+units,f['quote'],re.I))

def recovered_priority(f):
    # Preserve the original request without manufacturing a number or relaxing an
    # explicitly measurable/mandatory requirement. Unrelated budget digits are fine.
    strength='hard' if numeric_quote_values(f) or re.search(r'必须|一定要|绝对|至少|最多|不超过',f['quote']) else 'soft'
    return {'attribute':f['key'],'value':f['quote'],'polarity':'prefer','strength':strength,'quote':f['quote']}

def grounded_filter(raw):
    """Do not promote a vague priority to a made-up measurable threshold."""
    from .model_client import AttributeFilter
    f=AttributeFilter.model_validate(raw).model_dump()
    if f['op']=='remove':return f
    if f['key']=='wearing_style' and isinstance(f['value'],str):
        f['value']=STYLE_ALIASES.get(f['value'].casefold(),f['value'])
    if f['key'] in ('battery_single','battery_total','weight'):
        matches=[]
        for match in numeric_quote_values(f):
            prefix=f['quote'][:match.start()]
            scopes=list(re.finditer(r'单次|单充|一次充电|充一次|含盒|含充电盒|总计|总续航|累计',prefix))
            scope=('battery_single' if scopes[-1].group() in ('单次','单充','一次充电','充一次') else 'battery_total') if scopes else ''
            if f['key'].startswith('battery') and ((scope and scope!=f['key']) or (not scope and f['key']=='battery_total')):continue
            if not isinstance(f['value'],bool) and isinstance(f['value'],(int,float)) and float(match[1])==f['value']:matches.append(match)
        if not matches:return None
        modes={'anc_on':r'(?<!不)开(?:启)?降噪|降噪开|ANC\s*(?:on|开启)',
               'anc_off':r'关(?:闭)?降噪|不开(?:启)?降噪|降噪关|ANC\s*(?:off|关闭)',
               'anc_on_spatial':r'空间音频|spatial','workout':r'运动(?:心率监测|模式)|workout',
               'ambient_on':r'(?<!不)开(?:启)?环境声|环境声开','ambient_off':r'关(?:闭)?环境声|不开(?:启)?环境声|环境声关',
               'standard':r'标准模式|standard'}
        # Bind modes to the same clause as that number, not another test condition.
        grounded_modes=[]
        for match in matches:
            start=max((m.end() for m in re.finditer(r'[，,；;。\n]',f['quote'][:match.start()])),default=0)
            end=re.search(r'[，,；;。\n]',f['quote'][match.end():])
            clause=f['quote'][start:match.end()+end.start() if end else len(f['quote'])]
            # A trailing standalone mode clause is unambiguous only when there
            # is exactly one quoted quantity; otherwise keep modes separate.
            if not any(re.search(pattern,clause,re.I) for pattern in modes.values()) and len(numeric_quote_values(f))==1:clause=f['quote']
            clause=re.sub(r'(?:关闭|关掉|禁用|不开启|不启用|不要开启)\s*(?:空间音频|spatial)','',clause,flags=re.I)
            found={mode for mode,pattern in modes.items() if re.search(pattern,clause,re.I)}
            if 'anc_on_spatial' in found:found.discard('anc_on')
            if len(found)>1:return None  # Conflicting modes cannot become a looser unqualified filter.
            grounded_modes.append(next(iter(found)) if found else '')
        f['qualifier']=grounded_modes[0] if len(set(grounded_modes))==1 else ''
    return f

OFFICIAL_DOMAINS=('apple.com.cn','sony.com','sony.com.cn','sonystyle.com.cn','sony.net','hermes.cn','yslbeautycn.com')

def official_url(url):
    host=urlparse(url or '').hostname or ''
    return urlparse(url or '').scheme=='https' and any(host==d or host.endswith('.'+d) for d in OFFICIAL_DOMAINS)

def verified_attributes(product):
    return [(i,a) for i,a in enumerate(product.get('attributes',[])) if a.get('verified') is True and official_url(a.get('source_url')) and a.get('source_quote') and a.get('value') is not None]

def attribute_text(a):
    value=('支持' if a['value'] else '不支持') if isinstance(a['value'],bool) else str(a['value'])
    return f"{a.get('label',a['key'])}：{value}{a.get('unit','')}"+(f"（{a['qualifier']}）" if a.get('qualifier') else '')

def fact_sources(product):
    return [{'type':'catalog','product_id':product['product_id'],'field':f'attributes.{i}','label':a.get('label',a['key']),
        'quote':attribute_text(a),'source_quote':a['source_quote'],'source_url':a['source_url']} for i,a in verified_attributes(product)]

def normalize(product):
    p=dict(product)
    for key in ('aliases','scent_family','key_notes','suitable_scenarios','suitable_season','concentration','actual_spec_unit','selling_points','cautions','price_updated_at','price_type'):
        p.setdefault(key,'')
    p.setdefault('actual_spec_value',None);p.setdefault('attributes',[])
    # Provenance gates apply even if the input JSON accidentally marks a price verified.
    if not (p.get('price_verified') is True and official_url(p.get('price_source_url')) and p.get('price_source_quote')):
        p.update(reference_price_cny=None,price_verified=False)
    p['search_text']=';'.join(str(p.get(k,'')) for k in ('product_name','aliases','brand','scent_family','key_notes','selling_points','suitable_scenarios'))+';'+';'.join(attribute_text(a) for _,a in verified_attributes(p))
    return p

def attribute_rejection(product,filters):
    for f in filters:
        candidates=[a for _,a in verified_attributes(product) if a['key']==f['key'] and a.get('unit','')==f.get('unit','')]
        mode=f.get('qualifier','')
        if mode:candidates=[a for a in candidates if a.get('mode','')==mode]
        # An unqualified single-charge requirement cannot silently choose the best mode.
        if not mode and f['key'].startswith('battery') and len({a.get('mode','') for a in candidates})>1:
            return f"{f['key']}测试模式未明确，无法确认硬条件"
        if not candidates:return f"{f['key']}缺少同单位、同模式的核验事实"
        def passes(a):
            value=a['value']; wanted=f['value']
            if f['op']=='eq':
                if isinstance(value,bool) or isinstance(wanted,bool):return type(value) is type(wanted) and value==wanted
                return value==wanted
            if isinstance(value,bool) or isinstance(wanted,bool) or not isinstance(value,(float,int)) or not isinstance(wanted,(float,int)):return False
            return value>=wanted if f['op']=='gte' else value<=wanted
        # If several test codecs share a mode, all must pass; do not select the best codec.
        if not all(passes(a) for a in candidates):return f"{f['key']}不满足明确属性条件"
    return None
