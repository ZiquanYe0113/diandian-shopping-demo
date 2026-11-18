"""Deterministic continuations and answers backed by recorded catalog fields."""
import re
from .note_analysis import matching_products

CONFIRMATIONS={'是的','是','对','对的','没错','嗯','好的','确认','按这个条件'}

def is_factual_product_question(message):
    """An attribute/price question is not a request for budget-qualified picks."""
    return bool(re.search(r'多少钱|什么价格|价格(?:是|多少)|售价|区别|对比|比较|是什么|(?:支持|兼容|有没有).{0,16}[吗么？?]|(?:续航|重量|防水等级|佩戴方式).{0,8}(?:多久|多少|几|哪种|是什么)',message))

def explicit_unlimited_budget(message):
    """Bind unlimited to its own monetary subject, not another preference."""
    if message.strip().rstrip('。！!')=='不限':return True
    pattern=r'(?:预算|价格上限|价位)(?:是|为|可以|暂时|先)?(?:不限|不设上限|没有上限)|不限预算'
    for match in re.finditer(pattern,message):
        prefix=re.split(r'[，,；;。！？!?]',message[:match.start()])[-1]
        if not re.search(r'(?:不是|并非|不能|不要|别|不再)\s*$',prefix):return True
    return False

def defer_budget(message,previous,previous_question=''):
    q=message.strip().rstrip('。！!')
    explicit=bool(re.search(r'预算(?:我|还|也|暂时|目前|具体|是|暂且|都|没)?[^\d，。；]{0,6}(?:没想好|没定|没确定|不确定)',q))
    if re.search(r'预算[^\d，。；]{0,6}(?:不是|并非).{0,4}(?:没定|没想好|不确定)',q):explicit=False
    uncertain=('没想好','还没想好','暂时没想好','没确定','还没定','不确定')
    browse=('先看看','先推荐几个','先给几个方向')
    clauses=[v.strip() for v in re.split(r'[，,；;。！!\n]',q) if v.strip()]
    # Complete answer acts may be combined, but unrelated prose is model-owned.
    short=bool(clauses) and all(v in uncertain+browse for v in clauses)
    return explicit or (short and '预算' in previous_question and previous.get('budget_max') is None and not previous.get('budget_unlimited'))

def current_budget_ceiling(message,amount):
    """Require current money/bound context, not digits inside a model or battery."""
    if amount is None:return False
    for clause in re.split(r'[，,；;。\n]',message):
        if not re.search(r'预算|价位|价格|上限|控制在|超过|最多|以内|以下|之内|元|块',clause):continue
        numbers=re.finditer(r'(?<![\da-zA-Z.])(\d+(?:\.\d+)?)(?![\da-zA-Z.]|\s*(?:小时|小時|分钟|克))',clause)
        if any(float(n[1])==amount for n in numbers):return True
        # The semantic parser owns written Chinese amounts; this gate only
        # establishes that a fresh monetary expression exists in this clause.
        if re.search(r'[零〇一二三四五六七八九十百千万两]+\s*(?:元|块|以内|以下|之内)',clause):return True
    return False

def budget_question(req):
    """Ask together once; known optional fields are never asked again."""
    text='预算大概多少？也可以回复不限或暂时没想好。'
    refinement=recommendation_followup(req)
    return text+(' '+refinement if refinement else '')

def recommendation_followup(req,visible_count=None):
    scene=not req.get('use_case')
    from .preferences import constraints,SCENE_DIMENSIONS
    active=constraints(req)
    product_preferences=[c for c in active if c['attribute'] not in SCENE_DIMENSIONS and c['value']!=req.get('use_case')]
    preference=not (product_preferences or req.get('attribute_filters'))
    if req.get('browse_product_ids') is not None:
        count=len(req['browse_product_ids']) if visible_count is None else visible_count
        lead='想先了解哪款？' if count>1 else ''
        missing=(['预算'] if req.get('budget_max') is None and not req.get('budget_unlimited') and not req.get('budget_deferred') else [])
        missing+=(['使用场景'] if scene else [])+(['看重的功能'] if preference else [])
        return lead+('也可以告诉我'+'、'.join(missing)+'，我再帮你看看是否合适。' if missing else '')
    if req.get('target') or req.get('target_ids') or not (scene or preference):return ''
    if req.get('category')=='耳机':
        parts=(['主要用来通勤、运动还是居家聆听'] if scene else [])+(['偏好哪种佩戴方式，或更看重降噪、续航'] if preference else [])
    elif req.get('category')=='香水':
        parts=(['主要用在通勤、约会还是送礼'] if scene else [])+(['喜欢什么香调，例如清新、花香或木质'] if preference else [])
    else:return ''
    return '也可以告诉我，'+'，'.join(parts)+'？没想好也没关系，可以先看看。'

def explicit_budget(message):
    """Read a numeric yuan budget embedded in an otherwise normal query."""
    currency=r'(?<!\d)(\d+(?:\.\d+)?)(?:\s*[-–—~～至到]\s*(\d+(?:\.\d+)?))?\s*(?:元|块)'
    named=r'预算\s*(?:是|为|在|约|大概)?\s*(\d+(?:\.\d+)?)(?:\s*[-–—~～至到]\s*(\d+(?:\.\d+)?))?\s*(?:元|块|以内|以下|左右|之内|内|(?=[，。；,;\s]|$))'
    matches=list(re.finditer(currency,message)) or list(re.finditer(named,message))
    if len(matches)!=1:return None
    match=matches[0]
    # Do not reinterpret a former budget as the current one when the user revises
    # it later in the sentence. The model's explicit edit handles such ambiguity.
    if re.search(r'(?:改成|改为|改到|提高到|降到|调整到)\s*\d',message[match.end():]):return None
    return {
        'budget_min':float(match[1]) if match[2] else None,
        'budget_max':float(match[2] or match[1]),
        'budget_unlimited':False,
    }

def is_confirmation(message):
    return message.strip().rstrip('。！!') in CONFIRMATIONS

def budget_reply(message,old):
    match=re.fullmatch(r'(?:预算(?:是|为)?\s*)?(\d+(?:\.\d+)?)(?:\s*[-–—~～至到]\s*(\d+(?:\.\d+)?))?\s*(?:元|块)?(?:以内|左右)?[。！!]?',message.strip())
    if match:
        return {**old,'budget_min':float(match[1]) if match[2] else None,'budget_max':float(match[2] or match[1]),'budget_unlimited':False}
    if message.strip().rstrip('。！!') in ('不限','预算不限','不限预算'):
        return {**old,'budget_min':None,'budget_max':None,'budget_unlimited':True}
    return None

def followup(message,old,recommended,selected):
    """Resolve explicit positional references without guessing an ambiguous target."""
    q=message.strip(); req=dict(old)
    if any(w in q for w in ('换一批','换几款','再推荐几款')) or re.search(r'(?:别的|其他|其它|别款).{0,8}(?:推荐|选择|选项)|(?:推荐|看看).{0,6}(?:别的|其他|其它)',q):
        req.update(target='',target_ids=[],excluded_product_ids=list(dict.fromkeys(old.get('excluded_product_ids',[])+[p['product_id'] for p in recommended])))
        return 'READY',req,''
    rejecting_brand='不要' in q and any(w in q for w in ('牌子','品牌'))
    if rejecting_brand:
        numbered=re.search(r'第([一二三123])(?:款|个|瓶)',q)
        referred=selected
        if numbered:
            index='一二三'.find(numbered[1]) if numbered[1] in '一二三' else int(numbered[1])-1
            referred=recommended[index:index+1]
        elif not any(w in q for w in ('这个','这款','该品牌')):
            return None
        brands={p['brand'] for p in referred}
        if len(brands)!=1:
            return 'CLARIFY',req,'你想排除哪一个品牌？请指定商品序号或品牌。'
        req.update(target='',target_ids=[],exclude=list(dict.fromkeys(old.get('exclude',[])+list(brands))))
        return 'READY',req,''
    compare=any(w in q for w in ('两款比较','两款对比','前两款','这两款','两款有什么区别'))
    positions=re.findall(r'第([一二三123])(?:款|个|瓶)',q)
    position=re.search(r'第([一二三123])(?:款|个|瓶)',q)
    chosen=[]
    if len(set(positions))>1 and any(w in q for w in ('比较','对比','区别')):
        indices=['一二三'.find(value) if value in '一二三' else int(value)-1 for value in dict.fromkeys(positions)]
        chosen=[recommended[index] for index in indices if index<len(recommended)]
        compare=True
    elif compare: chosen=recommended[:2]
    elif position:
        index='一二三'.find(position[1]) if position[1] in '一二三' else int(position[1])-1
        chosen=recommended[index:index+1]
    elif any(w in q for w in ('这款','这个','它')) and any(w in q for w in ('香调','规格','留香','价格','多少钱','适合','浓度','续航','降噪','佩戴','防水','蓝牙','重量')):
        chosen=selected
    else: return None
    if not chosen or (compare and len(chosen)<2) or (not compare and len(chosen)!=1):
        return 'CLARIFY',req,'请指定想了解的商品序号或名称。'
    req.update(target='',target_ids=[p['product_id'] for p in chosen])
    return 'QA',req,''

def spec(p):
    if p.get('category')=='耳机':return p.get('model_identifier') or '耳机本体（具体版本见名称）'
    value=p.get('actual_spec_value'); unit=p.get('actual_spec_unit')
    return f'{value:g}{unit}' if value is not None and unit else '规格未知'

def price(p):
    value=p.get('reference_price_cny')
    return f'¥{value:g}' if value is not None else '价格未知'

def recommendation_details(products,req,evidence,catalog_products=None,*,interpretations=()):
    from .preferences import assess
    details=[]
    for p in products:
        reasons=[]; sources=[]
        def field_reason(field,label):
            value=p.get(field)
            if value is None or value=='': return
            reasons.append(f'{label}：{value}')
            sources.append({'type':'catalog','product_id':p['product_id'],'field':field,'quote':str(value),'source_url':p.get('source_url','')})
        if p.get('category')=='耳机':
            from .product_facts import fact_sources
            facts=fact_sources(p);reasons.extend(s['quote'] for s in facts[:3]);sources.extend(facts)
        else:field_reason('scent_family','收录香调')
        for wanted in [req.get('use_case','')]+req.get('preferences',[]):
            if not wanted: continue
            for field,label in [('suitable_scenarios','收录场景'),('key_notes','香调原料'),('selling_points','资料描述')]:
                if wanted.casefold() in str(p.get(field,'')).casefold():
                    field_reason(field,label); break
        for field in ('reference_price_cny','actual_spec_value','actual_spec_unit'):
            if p.get(field) is not None:
                sources.append({'type':'catalog','product_id':p['product_id'],'field':field,'quote':str(p[field]),'source_url':p.get('price_source_url',p.get('source_url','')) if field=='reference_price_cny' else p.get('source_url','')})
        if req.get('budget_max') is not None:
            reasons.append(f'当前实际规格{spec(p)}参考价{price(p)}，在预算上限¥{req["budget_max"]:g}内')
        cautions=[p['cautions']] if p.get('cautions') else ['资料未记录具体使用提醒，建议自行确认实际体验。']
        if p.get('cautions'):
            sources.append({'type':'catalog','product_id':p['product_id'],'field':'cautions','quote':p['cautions'],'source_url':p.get('source_url','')})
        use_case=req.get('use_case','')
        if use_case and use_case.casefold() not in str(p.get('suitable_scenarios','')).casefold():
            cautions.append(f'资料未直接记录适合“{use_case}”场景')
        matches=assess(p,req,evidence,catalog_products,interpretations=interpretations)['matches']
        for match in matches:
            wanted=match['preference'];support=match['support'];conflict=match['conflict']
            if match['status']=='unknown':cautions.append(f'“{wanted}”：资料不足，无法确认，建议先确认实际体验。')
            elif conflict:
                cautions.append(f'“{wanted}”：资料存在冲突，降低推荐优先级。'+('不同来源描述不一致，体验因人而异。' if support else ''))
            else:
                source=next((s for s in support if s['type']=='note'),support[0])
                reasons.append(('笔记作者个人体验' if source['type']=='note' else '商品资料')+f'对“{wanted}”有支持：“{source["quote"]}”')
            for source in support+conflict:
                if source not in sources:sources.append(source)
        details.append({'product_id':p['product_id'],'reasons':list(dict.fromkeys(reasons)),'cautions':cautions,'sources':sources,'preference_matches':matches})
    return details

def qa_answer(message,products,evidence,catalog_products=None):
    q=message.strip(); compare=any(w in q for w in ('比较','对比','区别'))
    fields=[]
    if compare or any(w in q for w in ('香调','香味','味道','原料','成分')): fields+=['scent_family','key_notes']
    if compare or any(w in q for w in ('价格','多少钱','多少元','贵')): fields+=['price']
    if compare or any(w in q for w in ('规格','容量','毫升','多少ml')): fields+=['spec']
    if compare or any(w in q for w in ('浓度','版本','EDP','EDT','Elixir')): fields+=['concentration']
    if any(w in q for w in ('场景','通勤','季节','适合')): fields+=['suitable_scenarios','suitable_season']
    if any(w in q for w in ('缺货','库存','有货','在售')): fields+=['availability']
    labels={'scent_family':'香调','key_notes':'香调原料','price':'实际规格参考价','spec':'规格','concentration':'浓度版本','suitable_scenarios':'收录场景','suitable_season':'收录季节','availability':'收录在售状态'}
    lines=[]
    for p in products:
        if p.get('category')=='耳机':
            from .product_facts import verified_attributes,attribute_text
            keys=set()
            for words,wanted in [(('续航','电池'),('battery_single','battery_total')),(('降噪',),('anc',)),(('佩戴',),('wearing_style',)),(('蓝牙','连接','有线'),('connection',)),(('重量','多重'),('weight',)),(('防水','防护'),('water_rating',))]:
                if compare or any(w in q for w in words):keys.update(wanted)
            attrs=[a for _,a in verified_attributes(p) if a['key'] in keys]
            bits=[attribute_text(a) for a in attrs]
            if compare or any(w in q for w in ('价格','多少钱','贵')):bits.append('中国官网价格快照：'+price(p))
            missing=keys-{a['key'] for a in attrs}
            if missing:bits.append('部分所问参数资料不足，无法确认')
            if not bits:bits=['资料未记录关于“'+q+'”的事实，无法确认']
            lines.append(p['product_name']+'：'+'；'.join(bits));continue
        bits=[]
        for field in dict.fromkeys(fields):
            value=price(p) if field=='price' else (spec(p) if field=='spec' else p.get(field))
            bits.append(labels[field]+'：'+(str(value) if value else '资料未记录，无法确认'))
        if '留香' in q or '扩香' in q:
            quotes=[]
            for note in evidence:
                if p['product_id'] not in note['product_ids']: continue
                for sentence in re.split(r'(?<=[。！？；;\n])',note['text']):
                    if not any(w in sentence for w in ('留香','扩香')): continue
                    subjects=matching_products(sentence,catalog_products or products)
                    # A note can contain several products. Attribute only a uniquely
                    # named and version-matched sentence, never the note-wide union.
                    if len(subjects)==1 and subjects[0]['product_id']==p['product_id']:
                        quotes.append(sentence.strip())
            bits.append('笔记作者个人体验：'+'；'.join(quotes) if quotes else '资料没有已确认版本的留香/扩香记录，无法确认')
        unknown=[w for w in ('研磨档位','研磨','档位','防水','孕妇','过敏','正品','生产日期','酒精含量','批次','保质期','成分比例') if w in q]
        if unknown: bits.append('资料未记录'+ '、'.join(dict.fromkeys(unknown))+'，无法确认')
        if not bits: bits=['资料未记录关于“'+q+'”的事实，无法确认']
        lines.append(p['product_name']+'：'+'；'.join(bits))
    return '\n'.join(lines)


def qa_evidence(message,evidence):
    """Keep only note passages relevant to the asked attributes."""
    groups=[(('香调','香味','味道','原料','成分','比较','对比','区别'),('香','气味','木质','柑橘')), (('留香','扩香','比较','对比','区别'),('留香','扩香')), (('适合','通勤','季节'),('适合','通勤','春','夏','秋','冬'))]
    keywords=[word for triggers,words in groups if any(t in message for t in triggers) for word in words]
    if not keywords: return []
    relevant=[]
    for note in evidence:
        sentences=[sentence.strip() for sentence in re.split(r'(?<=[。！？；;\n])',note['text']) if any(w in sentence for w in keywords)]
        if sentences: relevant.append({**note,'text':'\n'.join(sentences)})
    return relevant
