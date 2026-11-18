"""Conservative, inspectable preference checks; unknown is never a match."""
import re
from pydantic import ValidationError
from .preference_contract import PreferenceUpdate, PreferenceEvidence
from .note_analysis import matching_products

RELAX_SWEET=re.compile(r'(?:可以|能|愿意|也能|也可以)接受.{0,4}甜|不再要求.{0,3}不甜|甜度不限|甜不甜都(?:可以|行)')
STRICT_SWEET=re.compile(r'(?:绝对|一定|必须|坚决).{0,4}(?:不甜|不要甜|不能甜)|(?:不要|不接受|不能接受|不可以接受).{0,3}甜(?:香|味|的)?')
NOT_SWEET=re.compile(r'(?:完全|一点也|一点都)?不(?:偏)?甜(?:腻|润|美|香|感|味)?|没有甜(?:味|感)|无甜(?:味|感)')
SWEET=re.compile(r'偏甜|很甜|有点甜|太甜|甜润|奶甜|甜果|甜香|甜腻|甜美|甜感|甜味|甜度(?:较高|很高|高|明显)')
TERMS={'清新':('清新','清爽'),'木质':('木质',),'花香':('花香',),'柑橘':('柑橘',)}

# Exact, documented dimension/value pairs only: call noise reduction, passive
# isolation, comfort and vague battery priorities have no objective mapping.
# New objective dimensions can add an entry without inspecting user sentences.
TYPED_PREFERENCE_FACTS=(
    {'key':'anc','type':bool,'category':'耳机','choice_attribute':'功能','canonical_value':'主动降噪',
     'dimensions':{'功能','属性','feature','features','降噪','主动降噪','anc','noise cancellation'},
     'values':{'降噪':True,'主动降噪':True,'anc':True,'active noise cancellation':True,
               'active noise cancelling':True,'active noise canceling':True},
     'scoped_dimensions':{'降噪','主动降噪','anc','noise cancellation'},
     'scoped_values':{'支持':True,'true':True,'不支持':False,'false':False}},
    {'key':'wearing_style','type':str,'category':'耳机','choice_attribute':'佩戴方式',
     'dimensions':{'佩戴','佩戴方式','佩戴形式','wearing_style','wearing style','属性'},
     'values':{'入耳式':'入耳式','入耳':'入耳式','in-ear':'入耳式','in ear':'入耳式',
               '头戴包耳式':'头戴包耳式','包耳式':'头戴包耳式','over-ear':'头戴包耳式','over ear':'头戴包耳式',
               '头戴贴耳式':'头戴贴耳式','贴耳式':'头戴贴耳式','on-ear':'头戴贴耳式','on ear':'头戴贴耳式',
               '无耳塞式':'无耳塞式'},
     'scoped_dimensions':set(),'scoped_values':{}},
)


def canonical_boolean_choice(edit):
    """Recover a neutral feature choice when the model invented a quality value.

    Only a complete neutral quote is eligible. A performance request, negation,
    removal or avoid polarity keeps the original semantic constraint unchanged.
    """
    if edit['operation']!='upsert' or edit['polarity']!='prefer':return edit
    dimension=' '.join(edit['attribute'].casefold().split())
    quote=' '.join(edit['quote'].casefold().split())
    for rule in TYPED_PREFERENCE_FACTS:
        if rule['type'] is not bool or dimension not in rule['dimensions']:continue
        aliases=[re.escape(alias) for alias,value in rule['values'].items() if value is True]
        pattern=r'(?:'+'|'.join(aliases)+r')\s*吧?\s*(?:[，,]\s*别的无所谓)?[。.!！]?'
        if re.fullmatch(pattern,quote):return {**edit,'value':rule['canonical_value']}
    return edit


def typed_preference_sources(product,constraint,sources):
    """Return known presence with the existing source schema, never inferred text."""
    from .product_facts import verified_attributes
    dimension=' '.join(constraint['attribute'].casefold().split())
    value=' '.join(constraint['value'].casefold().split())
    byfield={s['field']:s for s in sources if s['type']=='catalog'}
    for rule in TYPED_PREFERENCE_FACTS:
        if dimension not in rule['dimensions']:continue
        values=dict(rule['values'])
        if dimension in rule['scoped_dimensions']:values.update(rule['scoped_values'])
        if value not in values:continue
        wanted=values[value];result=[]
        for index,fact in verified_attributes(product):
            if fact['key']!=rule['key'] or type(fact['value']) is not rule['type']:continue
            actual=fact['value']
            if isinstance(actual,str):
                # Unknown enum values cannot prove either presence or absence.
                actual=rule['values'].get(' '.join(actual.casefold().split()))
                if actual is None:continue
            source=byfield.get(f'attributes.{index}')
            if source:result.append((actual==wanted,{**source,'interpretation':'rule'}))
        return result
    return []


def legacy_update_preferences(message,requirements,previous=None):
    req=dict(requirements)
    preferences=list(req.get('preferences',[]));strict=list(req.get('strict_preferences',[]))
    previous=previous or {}
    replacement=re.search(r'(?:偏好|香调|风格)(?:改成|改为)|(?:改成|改为|换成)(?:木质|花香|柑橘|清新)',message)
    if not replacement:preferences=list(dict.fromkeys(previous.get('preferences',[])+preferences))
    strict=list(dict.fromkeys(previous.get('strict_preferences',[])+strict))
    relax=any(not re.search(r'(?:不|未|没)(?:太)?$',message[max(0,m.start()-3):m.start()]) for m in RELAX_SWEET.finditer(message))
    if relax:
        preferences=[p for p in preferences if p not in ('不甜','绝对不甜','不要甜香')]
        strict=[p for p in strict if p!='不甜']
    elif STRICT_SWEET.search(message):
        if '不甜' not in preferences:preferences.append('不甜')
        if '不甜' not in strict:strict.append('不甜')
    elif NOT_SWEET.search(message) and '不甜' not in preferences:
        preferences.append('不甜')
    removed={p for p in preferences+strict if re.search(r'(?:不要|不喜欢|不想要|取消|去掉)\s*'+re.escape(p)+r'|'+re.escape(p)+r'.{0,2}(?:不再要求|不要了)',message)}
    preferences=[p for p in preferences if p not in removed]
    strict=[p for p in strict if p not in removed]
    req.update(preferences=list(dict.fromkeys(preferences+strict)),strict_preferences=strict)
    return req


SCENE_DIMENSIONS={'场景','使用场景','用途','使用用途'}

def constraint_label(c):
    if c['polarity']=='prefer':return c['value']
    return '不甜' if c['value']=='甜' else '避免'+c['value']


def constraints(requirements):
    if requirements.get('preference_constraints') or requirements.get('preferences_structured'):
        return requirements.get('preference_constraints',[])
    result=[]
    for label in dict.fromkeys(requirements.get('preferences',[])+requirements.get('strict_preferences',[])):
        avoid=label.startswith(('不','避免'))
        value=label.removeprefix('避免') if label.startswith('避免') else (label[1:] if avoid else label)
        if not value:continue
        result.append({'attribute':'甜度' if value=='甜' else ('香调' if value in TERMS else '属性'),
            'value':value,'polarity':'avoid' if avoid else 'prefer',
            'strength':'hard' if label in requirements.get('strict_preferences',[]) else 'soft','quote':label})
    return result


def update_preferences(message,requirements,previous=None,*,semantic_only=False):
    previous=previous or {};req=dict(requirements);valid=[]
    for raw in req.get('preference_updates',[])[:12]:
        try:edit=PreferenceUpdate.model_validate(raw).model_dump()
        except (ValidationError,TypeError):continue
        if edit['quote'].strip() and edit['quote'] in message:valid.append(canonical_boolean_choice(edit))
    structured=previous.get('preferences_structured',bool(previous.get('preference_constraints')))
    # Shared, bounded recovery for complete registered choices in any supported
    # category. Safe model edits remain primary; literal contradictions are the
    # only reason to discard an edit in a dimension the whole answer specifies.
    from .preference_choices import choice_dimensions, explicit_choice_edits,same_typed_choice
    recovered,replaced=(explicit_choice_edits(message,req.get('category'),
        choice_dimensions(TERMS,TYPED_PREFERENCE_FACTS)) if semantic_only or structured else ([],set()))
    if recovered:
        removals=[e for e in recovered if e['operation']=='remove']
        matches_removal=lambda c:any(same_typed_choice(c,e,TYPED_PREFERENCE_FACTS,req.get('category')) for e in removals)
        if removals:
            previous={**previous,'preference_constraints':[c for c in constraints(previous) if not matches_removal(c)],'preferences_structured':True}
            valid=[e for e in valid if not matches_removal(e)]
        dimensions={e['attribute'] for e in recovered}
        expected={(e['attribute'],e['value'],e['polarity'],e['operation']) for e in recovered}
        valid=[e for e in valid if e['attribute'] not in dimensions or
               (e['attribute'],e['value'],e['polarity'],e['operation']) in expected]
        for edit in recovered:
            if any((e['attribute'],e['value'],e['polarity'],e['operation'])==
                   (edit['attribute'],edit['value'],edit['polarity'],edit['operation']) for e in valid):continue
            if any(all(c[k]==edit[k] for k in ('attribute','value','polarity')) and c['strength']=='hard'
                   for c in constraints(previous)):edit['strength']='hard'
            valid.append(edit)
        if replaced:
            # Keep same-value evidence for no-op replacement and other dimensions.
            targets={(e['attribute'],e['value']) for e in recovered}
            previous={**previous,'preference_constraints':[c for c in constraints(previous)
                if c['attribute'] not in replaced or (c['attribute'],c['value']) in targets],
                'preferences_structured':True}
    if valid or structured or semantic_only or req.get('preference_updates'):
        active=constraints(previous)
        for edit in valid:
            if edit['operation']=='upsert' and any(all(c[k]==edit[k] for k in ('attribute','value','polarity','strength')) for c in active):
                continue  # A no-op echo must not replace the user's original evidence.
            # Attribute/value identify the constraint; a new polarity replaces the old one.
            active=[c for c in active if (c['attribute'],c['value'])!=(edit['attribute'],edit['value'])]
            if edit['operation']=='upsert':active.append({k:v for k,v in edit.items() if k!='operation'})
        req['preference_constraints']=active;req['preferences_structured']=True
        req['preferences']=[constraint_label(c) for c in active]
        req['strict_preferences']=[constraint_label(c) for c in active if c['strength']=='hard']
    else:
        # Compatibility only: old sessions and the explicitly non-semantic mock model.
        req=legacy_update_preferences(message,req,previous)
        req['preference_constraints']=constraints({k:v for k,v in req.items() if k!='preference_constraints'})
        req['preferences_structured']=False
    req['preference_updates']=[]
    return req


def preference_status(text,wanted):
    if wanted=='不甜':
        positive=bool(NOT_SWEET.search(text))
        rest=re.sub(r'不(?:是|算)?(?:太|很|特别|那么)甜','',NOT_SWEET.sub('',text))
        negative=bool(SWEET.search(rest))
        return positive,negative
    terms=TERMS.get(wanted,(wanted,))
    negative=any(re.search(r'(?:不太|并不|不是|不够|不|没有|缺乏)\s*'+re.escape(t),text) for t in terms)
    cleaned=text
    for t in terms:cleaned=re.sub(r'(?:不太|并不|不是|不够|不|没有|缺乏)\s*'+re.escape(t),'',cleaned)
    return any(t.casefold() in cleaned.casefold() for t in terms),negative


def unique_version_product(quote,products):
    # Detect subjects BEFORE concentration filtering, so EDC on one product
    # cannot hide a second Cologne subject in the same sentence.
    named=[p for p in products if any(len(a.strip())>2 and a.casefold() in quote.casefold() for a in [p['product_name']]+p['aliases'].split(';'))]
    matched=matching_products(quote,products)
    if len(named)!=1 and not (named and all(p.get('category')=='耳机' for p in named) and len(matched)==1):return None
    return matched[0] if len(matched)==1 else None


def product_sources(product,evidence,catalog=None):
    sources=[{'type':'catalog','product_id':product['product_id'],'field':f,'quote':str(product[f]),'source_url':product.get('source_url','')}
        for f in ('scent_family','selling_points','cautions') if product.get(f)]
    from .product_facts import fact_sources
    sources+=fact_sources(product)
    # Check against the full catalog when possible: note-wide IDs cannot attribute a sentence.
    if catalog is None:
        from .catalog import Catalog
        catalog=Catalog().products
    universe=catalog
    for note in evidence:
        if product['product_id'] not in note.get('product_ids',[]):continue
        for sentence in re.split(r'(?<=[。！？；;\n])',note.get('text','')):
            quote=sentence.strip();matched=unique_version_product(quote,universe)
            if quote and matched and matched['product_id']==product['product_id']:
                sources.append({'type':'note','product_id':product['product_id'],'note_id':note['note_id'],'field':'text',
                    'title':note.get('title',''),'quote':quote,'source_url':note.get('source_url','')})
    return sources


def validate_interpretations(claims,requirements,pool,evidence,catalog):
    """Validate provenance, not the truth of the model's semantic interpretation."""
    wanted={(c['attribute'],c['value']) for c in constraints(requirements)}
    byid={p['product_id']:p for p in pool};notes={n['note_id']:n for n in evidence};accepted=[]
    for raw in claims[:144]:  # Four decisions, each schema-limited to 36 new claims.
        try:c=PreferenceEvidence.model_validate(raw).model_dump()
        except (ValidationError,TypeError):continue
        if (c['attribute'],c['value']) not in wanted or c['product_id'] not in byid:continue
        p=byid[c['product_id']];quote=c['quote']
        if not quote.strip():continue
        if c['source_type']=='catalog':
            if c['field'].startswith('attributes.'):
                from .product_facts import fact_sources
                source=next((s for s in fact_sources(p) if s['field']==c['field'] and s['quote']==quote),None)
                if source:accepted.append({**c,'source':{**source,'interpretation':'model'}})
                continue
            if c['field'] not in ('scent_family','selling_points','cautions','suitable_scenarios','key_notes'):continue
            if quote not in str(p.get(c['field'],'')):continue
            # Full field prevents cherry-picking away a negation within a short description.
            if quote!=str(p.get(c['field'],'')):continue
            source={'type':'catalog','product_id':p['product_id'],'field':c['field'],'quote':quote,'source_url':p.get('source_url','')}
        else:
            note=notes.get(c['note_id'])
            if not note or quote not in note.get('text',''):continue
            sentence=next((line.strip() for line in re.split(r'(?<=[。！？；;\n])',note['text']) if quote==line.strip()),None)
            if not sentence:continue
            matched=unique_version_product(sentence,catalog)
            if not matched or matched['product_id']!=p['product_id']:continue
            source={'type':'note','product_id':p['product_id'],'field':'text','note_id':note['note_id'],
                'title':note.get('title',''),'quote':quote,'source_url':note.get('source_url','')}
        accepted.append({**c,'source':{**source,'interpretation':'model'}})
    return list({str(c):c for c in accepted}.values())


def assess(product,requirements,evidence,catalog=None,*,interpretations=()):
    sources=product_sources(product,evidence,catalog);matches=[]
    for c in constraints(requirements):
        support=[];conflict=[]
        typed=typed_preference_sources(product,c,sources)
        for present,source in typed:
            yes=present==(c['polarity']=='prefer')
            (support if yes else conflict).append(source)
        claims=[v for v in interpretations if v['product_id']==product['product_id'] and (v['attribute'],v['value'])==(c['attribute'],c['value'])]
        # A verified typed fact decides this objective dimension. Text or model
        # interpretations must not reverse an official true/false or enum value.
        if typed:claims=[]
        for source in sources:
            # Only legacy scent dimensions have a bounded literal fallback. A value
            # in an unrelated attribute (glass bottle vs glass cap) proves nothing.
            if not ((c['attribute']=='甜度' and c['value']=='甜') or (c['attribute']=='香调' and c['value'] in TERMS)):continue
            # Validated semantic interpretations take priority for that exact source only.
            if any(v['source']['type']==source['type'] and v['source']['quote']==source['quote'] for v in claims):continue
            if c['value']=='甜':
                absent,present=preference_status(source['quote'],'不甜')
            else:present,absent=preference_status(source['quote'],c['value'])
            yes,no=(present,absent) if c['polarity']=='prefer' else (absent,present)
            tagged={**source,'interpretation':'rule'}
            if yes:support.append(tagged)
            if no:conflict.append(tagged)
        for v in claims:
            if v['presence']=='uncertain':continue
            yes=(v['presence']=='present')==(c['polarity']=='prefer')
            (support if yes else conflict).append(v['source'])
        matches.append({'preference':constraint_label(c),'attribute':c['attribute'],'value':c['value'],'polarity':c['polarity'],
            'status':'conflict' if conflict else ('supported' if support else 'unknown'),
            'strict':c['strength']=='hard','support':support,'conflict':conflict})
    return {'product_id':product['product_id'],'matches':matches}


def order_candidates(products,requirements,evidence,catalog=None,*,interpretations=(),allow_unverified_hard=False,allow_conflicting_hard=False):
    assessments={p['product_id']:assess(p,requirements,evidence,catalog,interpretations=interpretations) for p in products}
    good=[];rejected=[]
    for p in products:
        blocked=[m for m in assessments[p['product_id']]['matches'] if m['strict'] and
            ((m['status']=='conflict' and not allow_conflicting_hard) or (m['status']=='unknown' and not allow_unverified_hard))]
        if blocked:
            conflict=[m['preference'] for m in blocked if m['status']=='conflict'];unknown=[m['preference'] for m in blocked if m['status']=='unknown']
            reason=('与明确要求冲突：'+'、'.join(conflict) if conflict else '')
            if unknown:reason+=('；' if reason else '')+'硬要求资料不足，无法确认：'+'、'.join(unknown)
            rejected.append({'product_id':p['product_id'],'reason':reason})
        else:good.append(p)
    def key(p):
        matches=assessments[p['product_id']]['matches']
        return (sum(m['status']=='conflict' for m in matches),-sum(m['status']=='supported' for m in matches))
    return sorted(good,key=key),rejected,assessments


def selection_records(pool,selected,requirements,evidence,rejected,catalog,*,interpretations=()):
    selected_ids=[p['product_id'] for p in selected];reasons={r['product_id']:r['reason'] for r in rejected}
    # Recheck the complete pool, including items beyond the model observation window.
    _,policy_rejected,_=order_candidates(pool,requirements,evidence,catalog,interpretations=interpretations)
    for r in policy_rejected:reasons.setdefault(r['product_id'],r['reason'])
    records=[]
    for p in pool:
        item=assess(p,requirements,evidence,catalog,interpretations=interpretations);pid=p['product_id']
        conflicts=[m['preference'] for m in item['matches'] if m['status']=='conflict']
        if pid in reasons:status='excluded';why='本轮排除：'+reasons[pid]
        elif conflicts:
            status='selected' if pid in selected_ids else 'deprioritized'
            why='与“'+'、'.join(conflicts)+'”存在资料冲突，降低优先级'+('；仍作为备选，建议先试香' if pid in selected_ids else '')
        elif pid in selected_ids:
            status='selected';why='通过本轮硬条件检查，按偏好证据与候选顺序选入；未知项仍需确认'
        else:status='not_selected';why='进入过本轮候选，但未选入最终结果；未记录更具体的模型取舍理由'
        records.append({**item,'product_name':p['product_name'],'status':status,'selected':pid in selected_ids,
            'rank':selected_ids.index(pid)+1 if pid in selected_ids else None,'decision_reason':why})
    return records


def candidate_evidence(catalog,pool,read_notes=()):
    ids={p['product_id'] for p in pool}
    evidence={n['note_id']:n for n in catalog.evidence(list(ids))}
    for note in read_notes:
        quotes=[];matched_ids=set()
        for sentence in re.split(r'(?<=[。！？；;\n])',note.get('text','')):
            matched=unique_version_product(sentence,catalog.products)
            if matched and matched['product_id'] in ids:
                quotes.append(sentence.strip());matched_ids.add(matched['product_id'])
        if quotes:evidence[note['note_id']]={**note,'text':'\n'.join(quotes),'product_ids':sorted(matched_ids)}
    return list(evidence.values())


def explain_selection(message,records,catalog,recommended):
    if not re.search(r'为什么|为何|怎么没|为啥',message) or not re.search(r'选|推荐|排|这款|这个|第.{1,2}款',message):return None
    named=[p for p in catalog if any(len(a)>2 and a.casefold() in message.casefold() for a in [p['product_name']]+p['aliases'].split(';'))]
    if not named:
        pos=re.search(r'第([一二三123])款',message)
        if pos:
            i='一二三'.find(pos[1]) if pos[1] in '一二三' else int(pos[1])-1
            named=recommended[i:i+1]
    if not named:return '本轮没有这个商品的取舍记录。请指定商品名称或推荐序号。'
    byid={r['product_id']:r for r in records};lines=[]
    for p in named:
        record=byid.get(p['product_id'])
        if not record:lines.append(p['product_name']+'：未记录本轮对它的比较或排除原因。');continue
        lines.append(p['product_name']+'：'+record['decision_reason']+'。')
        for match in record['matches']:
            state={'supported':'有支持资料','conflict':'存在冲突','unknown':'资料不足，无法确认'}[match['status']]
            lines.append('• '+match['preference']+'：'+state)
            for source in (match['conflict'] or match['support'])[:2]:
                lines.append(('笔记作者个人体验' if source['type']=='note' else '商品资料')+'：“'+source['quote']+'”')
    return '\n'.join(lines)
