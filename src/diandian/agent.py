"""A bounded decide/act/observe loop with read-only, validated tools."""
import copy,json,re,time
from .agent_contract import AgentDecision,LIMITS,STOP_LABELS
from .model_client import Requirements
from .product_facts import grounded_filter,recovered_priority
from .shopping_logic import explicit_budget,budget_reply,defer_budget,budget_question,current_budget_ceiling,is_factual_product_question,explicit_unlimited_budget
from .note_analysis import matching_products
from .product_scope import resolve_browse_scope
from .preferences import update_preferences,order_candidates,selection_records,candidate_evidence,unique_version_product,product_sources,validate_interpretations

QUESTIONS={'category':'你想选购哪一类商品？例如香水或耳机。','budget':'预算上限是多少？也可以回复不限。',
    'use_case':'你主要想在什么场景使用？例如通勤、约会或送礼。',
    'preferences':'你偏好什么香调或风格？例如清新、花香或木质。',
    'target':'你想了解哪款商品？可以告诉我名称或上一轮商品序号。'}

def explicit_category(message):
    # Literal fallback for mock/first action only; real understanding supplies category.
    found=[]
    for match in re.finditer('香水|耳机',message):
        prefix=message[max(0,match.start()-6):match.start()]
        if not re.search(r'(?:不买|不要|不选|不考虑|不想买|不是)\s*$',prefix):found.append(match.group())
    return found[-1] if found else ''

def reset_task_for_category(message,old,category):
    if not category or not old.get('category') or category==old['category']:return dict(old)
    fresh=Requirements(category=category).model_dump()
    if re.search(r'(?:沿用|保持|还是|同样).{0,5}预算|预算不变',message):
        for key in ('budget_min','budget_max','budget_unlimited','budget_deferred'):fresh[key]=old.get(key,fresh[key])
    if re.search(r'(?:沿用|保持|还是|同样).{0,5}(?:场景|用途)|场景不变',message):fresh['use_case']=old.get('use_case','')
    return fresh

def merge_requirements(message,old,updates=None,*,semantic_only=False,previous_question=''):
    # Full-schema defaults from a model are not an explicit user request to erase memory.
    updates={k:v for k,v in (updates or {}).items() if v is not None and v!='' and v!=[]}
    if old.get('budget_unlimited') and updates.get('budget_unlimited') is False and 'budget_max' not in updates:
        updates.pop('budget_unlimited')
    category=(updates.get('category') or explicit_category(message)) if semantic_only else (explicit_category(message) or updates.get('category',''))
    old=reset_task_for_category(message,old,category)
    # Repair persisted filters as well as new output; existing sessions must recover.
    old=dict(old);filters=[];recovered=[]
    for f in old.get('attribute_filters',[]):
        checked=grounded_filter(f)
        if checked:filters.append(checked)
        else:recovered.append(recovered_priority(f))
    if recovered:
        from .preferences import constraints
        active=constraints(old)
        old.update(preference_constraints=active+[c for c in recovered if c not in active],preferences_structured=True)
    old['attribute_filters']=filters
    req={**old,**updates}
    if category:req['category']=category
    filters=list(old.get('attribute_filters',[]));soft=[]
    for f in updates.get('attribute_filters',[]):
        if not f.get('quote') or f['quote'] not in message:continue
        checked=grounded_filter(f)
        if not checked:
            soft.append({**recovered_priority(f),'operation':'upsert'})
            continue
        f=checked
        identity=lambda v:(v['key'],v.get('unit',''),v.get('qualifier',''),v.get('op','eq'))
        if f.get('op')=='remove':
            filters=[v for v in filters if not (v['key']==f['key'] and (not f.get('qualifier') or v.get('qualifier','')==f['qualifier']))]
        else:
            filters=[v for v in filters if identity(v)!=identity(f)]+[f]
    # Mock mode only: deterministic demonstrator, never described as semantic model validation.
    if not semantic_only and '必须' in message and '主动降噪' in message:
        filters=[f for f in filters if f['key']!='anc']+[{'key':'anc','op':'eq','value':True,'quote':message}]
    # Complete registered cancellation removes the same objective condition as
    # its soft preference. "Cancel ANC requirement" does not mean "avoid ANC".
    from .preference_choices import explicit_choice_edits,choice_dimensions
    from .preferences import TERMS,TYPED_PREFERENCE_FACTS
    choices,_=explicit_choice_edits(message,req.get('category'),choice_dimensions(TERMS,TYPED_PREFERENCE_FACTS))
    for edit in choices:
        if edit['operation']!='remove':continue
        for fact in TYPED_PREFERENCE_FACTS:
            if fact['category']!=req.get('category') or fact['choice_attribute']!=edit['attribute']:continue
            value=next((v for alias,v in fact['values'].items() if alias==edit['value'].casefold()),None)
            if value is None and fact.get('canonical_value')==edit['value']:value=True
            if value is not None:filters=[f for f in filters if not (f['key']==fact['key'] and f.get('op','eq')=='eq' and (fact['type'] is bool or f['value']==value))]
    req['attribute_filters']=filters
    req['preference_updates']=list(updates.get('preference_updates',[]))+soft
    parsed=explicit_budget(message) or budget_reply(message,req)
    if parsed: req.update(parsed);req['budget_deferred']=False
    elif defer_budget(message,old,previous_question):
        # A fresh explicit ceiling wins over "not sure yet". An old amount echoed
        # by the model does not: it must also occur in this user's current text.
        ceiling=updates.get('budget_max')
        current_ceiling=current_budget_ceiling(message,ceiling)
        if not current_ceiling:req.update(budget_min=None,budget_max=None,budget_unlimited=False,budget_deferred=True)
    if not parsed and explicit_unlimited_budget(message):req.update(budget_min=None,budget_max=None,budget_unlimited=True)
    scenes=('通勤','约会','送礼','居家','运动')
    if not semantic_only:
        for scene in scenes:
            if scene in message and not re.search(r'(?:不要|不用于|不是)\s*'+scene,message):req['use_case']=scene;break
        preferences=[p for p in ('清新','不甜','木质','花香','柑橘') if p in message and not re.search(r'(?:不要|不喜欢|不想要)\s*'+p,message)]
        if preferences:req['preferences']=list(dict.fromkeys(req.get('preferences',[])+preferences))
    elif not updates.get('use_case') and message.strip().rstrip('。！!') in scenes:
        # Complete menu choices can be recovered; prose, compound uses and
        # historical mentions belong to the semantic parser, not list order.
        req['use_case']=message.strip().rstrip('。！!')
    if req.get('budget_max') is not None or req.get('budget_unlimited'):req['budget_deferred']=False
    if req.get('budget_unlimited'):req.update(budget_min=None,budget_max=None)
    req=update_preferences(message,req,old,semantic_only=semantic_only)
    # The model may express the same scene in structured preferences instead of
    # use_case. Normalize that validated representation, without keyword inference
    # or overriding an explicit scene field supplied in this turn.
    from .preferences import SCENE_DIMENSIONS,constraints
    old_scene_values=list(dict.fromkeys(c['value'] for c in constraints(old)
        if c['attribute'] in SCENE_DIMENSIONS and c['polarity']=='prefer'))
    scene_values=list(dict.fromkeys(c['value'] for c in req.get('preference_constraints',[])
        if c['attribute'] in SCENE_DIMENSIONS and c['polarity']=='prefer'))
    if not updates.get('use_case') and (scene_values!=old_scene_values or not req.get('use_case')):
        if scene_values or old_scene_values:req['use_case']='、'.join(scene_values)
    return Requirements.model_validate(req).model_dump()

def missing_fields(req):
    fields=[]
    if not req['category'] and not req['target']:fields.append('category')
    if req['budget_max'] is None and not req['budget_unlimited'] and not req.get('budget_deferred') and not req['target'] and req.get('browse_product_ids') is None:fields.append('budget')
    if not req['use_case']:fields.append('use_case')
    if not req['preferences'] and not req.get('attribute_filters'):fields.append('preferences')
    return fields

def apply_browse_scope(message,req,products,*,clear_target=True,semantic_context=None):
    """Keep catalog-resolved identities authoritative over model target guesses."""
    explicit=resolve_browse_scope(message,products,semantic_context=semantic_context)
    scoped=resolve_browse_scope(message,products,req,semantic_context=semantic_context)
    req=reset_task_for_category(message,req,scoped.get('category',''))
    req.update(scoped)
    if explicit['browse_product_ids'] is not None:
        if len(explicit['browse_product_ids'])==1:
            # A unique catalog identity supports factual lookup independently of
            # recommendation eligibility. READY is still filtered before output.
            chosen=next(p for p in products if p['product_id']==explicit['browse_product_ids'][0])
            req.update(target=chosen['product_name'],target_ids=[])
        elif clear_target:req.update(target='',target_ids=[])
    return Requirements.model_validate(req).model_dump()

def safe_note(note):
    text=note.get('text','')
    return {k:note.get(k,'') for k in ('note_id','title','source_url','author')} | {
        'text':text[:6000],'truncated':len(text)>6000,'source':'xhs' if note.get('real') else 'local',
        'image_total':note.get('image_total',0)}

class AgentTools:
    def __init__(self,engine):
        self.engine=engine;self.source=getattr(engine,'agent_source',None)
        self.local={n['note_id']:n for n in engine.catalog.notes};self.allowed=set(self.local)
        if self.source:
            from .curated_notes import with_cached_images
            cached={n['note_id']:n for n in self.source.list_notes()}
            self.local={i:with_cached_images(n,cached) for i,n in self.local.items()}
            self.allowed.update(cached)

    def search(self,query,scope='both'):
        # Product aliases also find local notes whose prose uses a different alias.
        products=[p for p in self.engine.catalog.products if any(a and a.casefold() in query.casefold() for a in p['aliases'].split(';')) or p['product_name'] in query]
        ids={p['product_id'] for p in products};words=[w for w in re.split(r'\s+|，|、',query) if w]
        local=list(self.local.values())
        if self.source:local+=self.source.list_notes()
        found=[safe_note(n) for n in local if ids&set(n.get('product_ids',[])) or any(w in (n['title']+' '+n['text']) for w in words)]
        found=[{k:v for k,v in n.items() if k not in ('text','truncated','image_total')} for n in found[:5]]
        network='not_configured';error=''
        if self.source and scope in ('xhs','both'):
            try:
                remote=self.source.search_notes(query);network='ok'
                found=remote if scope=='xhs' else found+remote
            except ValueError:
                network='unavailable';error='真实笔记搜索未完成，当前结果仅包含已保存或本地笔记。'
        found=list({n['note_id']:n for n in found}.values())[:10]
        self.allowed.update(n['note_id'] for n in found)
        used_scope=('xhs_only' if scope=='xhs' else 'local_and_xhs') if network=='ok' else 'local_only'
        return {'notes':found,'network_status':network,'error':error,'scope':used_scope}

    def read(self,note_id):
        if note_id not in self.allowed:raise ValueError('只能读取搜索结果或已保存的笔记')
        note=self.local.get(note_id)
        if note is None:
            if not self.source:raise ValueError('真实笔记读取工具未配置')
            note=self.source.read_searched_note(note_id)
        safe=safe_note(note)
        safe['image_observations']=[]
        if note.get('images') and getattr(self.engine,'note_image_loader',None):
            from .note_vision import cached_observations
            loader=self.source.analysis_images if note.get('real') and self.source else self.engine.note_image_loader
            try:safe['image_observations']=cached_observations(loader(note_id),self.engine.model,self.engine.note_vision_cache_path)
            except ValueError:safe['image_status']='unavailable'
        safe['unanalysed_images']=max(0,safe['image_total']-len(safe['image_observations']))
        return safe

def run_agent(engine,state):
    started=time.monotonic();request=state['request'];message=request['message']
    req=merge_requirements(message,state.get('requirements',{}),semantic_only=engine.model.mode=='real',previous_question=state.get('question',''))
    factual=is_factual_product_question(message)
    req=apply_browse_scope(message,req,engine.catalog.products,clear_target=not factual,semantic_context={'exclusion_quotes':[]} if engine.model.mode=='real' else None);tools=AgentTools(engine)
    counts={'decisions':0,'searches':0,'reads':0};observations=[];events=[];read_notes=[];interpretations=[];scope_context={}
    trace=state.get('trace',[]);products=[];rejected=[];candidate_pool=[];seen=set();stop='decision_limit';route='READY';question=''
    # One combined clarification per request; user turns never consume a lifetime
    # conversation allowance. ask_user returns immediately below.
    clarifications=0
    history=state.get('history',[])[-6:]
    for _ in range(LIMITS['decisions']):
        if time.monotonic()-started>=LIMITS['seconds']:stop='time_limit';break
        engine.stage('Agent 选择下一步')
        counts['decisions']+=1
        evidence=candidate_evidence(engine.catalog,candidate_pool,read_notes)
        _,_,checks=order_candidates(products,req,evidence,engine.catalog.products,interpretations=interpretations,allow_unverified_hard=True,allow_conflicting_hard=True)
        context={'request':{k:request[k] for k in ('entry','message')},'requirements':req,'conversation':history,
            'attribute_values':{'wearing_style':['入耳式','无耳塞式','头戴贴耳式','头戴包耳式']},
            'preference_assessments':list(checks.values()),
            'preference_sources':[{'product_id':p['product_id'],'sources':product_sources(p,evidence,engine.catalog.products)} for p in products] if req.get('preference_constraints') else [],
            'previous_question':state.get('question',''),'observations':copy.deepcopy(observations),
            'limits':LIMITS,'counts':dict(counts),'clarifications_used':clarifications,
            'available_sources':['local']+(['xhs'] if tools.source else []),
            'known_notes':[{'note_id':i,'title':n['title']} for i,n in tools.local.items()][:8]}
        decision_start=time.perf_counter()
        try:
            decision=AgentDecision.model_validate(engine.model.decide_agent(context))
        except Exception as error:
            error.agent_report={'version':'bounded-agent-v1','counts':dict(counts),'limits':LIMITS,
                'stop_reason':'model_error','stop_label':'模型请求失败，结束本轮',
                'events':events,'notes':read_notes,'observations':observations}
            from pydantic import ValidationError
            if isinstance(error,ValidationError):
                error.agent_report['validation_errors']=[{'field':'.'.join(map(str,e['loc'])),'type':e['type']} for e in error.errors(include_input=False,include_url=False)]
            error.agent_trace=trace
            raise
        edits=decision.requirements.model_dump(exclude_unset=True)
        req=merge_requirements(message,req,edits,semantic_only=engine.model.mode=='real',previous_question=state.get('question',''))
        scope_context.update({k:v for k,v in {'category':edits.get('category'),'scope_text':edits.get('target_quote')}.items() if v})
        if isinstance(edits.get('exclusion_quotes'),list):scope_context['exclusion_quotes']=edits['exclusion_quotes']
        req=apply_browse_scope(message,req,engine.catalog.products,clear_target=not factual,semantic_context=scope_context)
        interpretations=validate_interpretations([{k:v for k,v in c.items() if k!='source'} for c in interpretations]+[v.model_dump() for v in decision.preference_evidence],req,products,evidence,engine.catalog.products)
        action=decision.action
        events.append({'action':action,'reason':decision.reason})
        trace.append({'node':'agent_decision','elapsed_ms':round((time.perf_counter()-decision_start)*1000),
            'details':{'step':counts['decisions'],'action':action,'reason':decision.reason,'requirements':req}})
        if time.monotonic()-started>=LIMITS['seconds']:stop='time_limit';break
        if action=='finish' and decision.finish_route in ('READY','QA') and not observations and ('category' not in missing_fields(req) and 'budget' not in missing_fields(req)):
            action='query_catalog'
            trace[-1]['details']['applied_action']=action
        mandatory=next((f for f in missing_fields(req) if f in ('category','budget')),'')
        if action in ('ask_user','query_catalog') and mandatory:
            action='ask_user';decision.ask_field=mandatory
            trace[-1]['details']['applied_action']=action
        if action=='ask_user':
            missing=missing_fields(req)
            field=decision.ask_field
            if field not in missing:field=missing[0] if missing else ''
            if not field or field in ('use_case','preferences'):
                action='finish' if any(o['action']=='query_catalog' and o['ok'] for o in observations) else 'query_catalog'
                trace[-1]['details']['applied_action']=action
            else:
                clarifications+=1;route='CLARIFY';question=budget_question(req) if field=='budget' else QUESTIONS[field];stop='asked_user';break
        if action=='finish':
            route=decision.finish_route
            # A factual product question remains answerable above a purchase
            # budget. Observed catalog facts are not budget-qualified picks.
            purchase_intent=bool(re.search(r'推荐|选购|挑选|买|购入',message))
            if factual and not purchase_intent and products and route in ('READY','NO_RESULT'):
                route='QA';trace[-1]['details']['applied_finish_route']='QA'
            if route=='NO_RESULT':
                # Empty-result claims must agree with already observed facts.
                # Reapply current hard conditions; never expand the observed pool.
                products,rejected_now=engine.catalog.filter(products,req);rejected+=rejected_now
                products,strict_rejected,_=order_candidates(products,req,candidate_evidence(engine.catalog,candidate_pool,read_notes),engine.catalog.products,interpretations=interpretations)
                rejected+=strict_rejected
                if products:
                    route='READY';products=products[:3]
                    trace[-1]['details']['applied_finish_route']='READY'
            else:
                if route!='QA':
                    products,rejected_now=engine.catalog.filter(products,req);rejected+=rejected_now
                    products,strict_rejected,_=order_candidates(products,req,candidate_evidence(engine.catalog,candidate_pool,read_notes),engine.catalog.products,interpretations=interpretations)
                    rejected+=strict_rejected
                byid={p['product_id']:p for p in products}
                if len(set(decision.product_ids))!=len(decision.product_ids) or not set(decision.product_ids)<=set(byid):
                    stop='invalid_selection';products=products[:3];break
                selected=[byid[i] for i in decision.product_ids] if decision.product_ids else products[:3]
                # Keep the model's order within equal match groups, but do not lead
                # with an explicit conflict while a better observed candidate exists.
                combined=selected+[p for p in products if p not in selected]
                products=selected if route=='QA' else order_candidates(combined,req,candidate_evidence(engine.catalog,candidate_pool,read_notes),engine.catalog.products,interpretations=interpretations)[0][:len(selected)]
            stop='completed';break
        args=req if action=='query_catalog' else ({'query':decision.query,'scope':decision.search_scope} if action=='search_notes' else decision.note_id)
        signature=json.dumps([action,args],sort_keys=True,ensure_ascii=False)
        if signature in seen:stop='repeated_action';break
        seen.add(signature)
        if action=='search_notes':
            if counts['searches']>=LIMITS['searches']:stop='search_limit';break
            counts['searches']+=1
        elif action=='read_note':
            if counts['reads']>=LIMITS['reads']:stop='read_limit';break
            counts['reads']+=1
        engine.stage({'query_catalog':'Agent 查询商品库','search_notes':'Agent 搜索笔记','read_note':'Agent 读取笔记'}[action])
        tool_start=time.perf_counter();ok=True
        try:
            if action=='query_catalog':
                missing=missing_fields(req)
                if 'category' in missing or 'budget' in missing:
                    raise ValueError('需要先补充品类和预算，不能假定预算')
                candidates=engine.catalog.search(req)
                candidate_pool=candidates
                products,rejected=(candidates,[]) if req['target'] or req['target_ids'] or (factual and req.get('browse_product_ids') is not None) else engine.catalog.filter(candidates,req)
                products,strict_rejected,checks=order_candidates(products,req,candidate_evidence(engine.catalog,candidate_pool,read_notes),engine.catalog.products,interpretations=interpretations,allow_unverified_hard=True,allow_conflicting_hard=True)
                rejected+=strict_rejected;products=products[:6]
                fields=('category','attributes','price_verified','price_source_url','price_updated_at','product_id','product_name','brand','reference_price_cny','actual_spec_value','actual_spec_unit','concentration','scent_family','selling_points','key_notes','suitable_scenarios','cautions','availability')
                result={'products':[{**{k:p.get(k) for k in fields},'preference_matches':checks[p['product_id']]['matches']} for p in products],'rejected':rejected}
            elif action=='search_notes':
                if not decision.query.strip():raise ValueError('请提供有效的笔记搜索词')
                result=tools.search(decision.query,decision.search_scope)
            else:
                note=tools.read(decision.note_id);read_notes.append(note);result={'note':note}
        except ValueError:
            ok=False;result={'error':{'query_catalog':'商品查询未完成，请检查品类、预算及条件。','search_notes':'笔记搜索未完成，请使用已有资料或结束。','read_note':'笔记读取未完成，该ID不在可读范围或服务暂不可用。'}[action]}
        result=copy.deepcopy(result)
        observation={'action':action,'ok':ok,'result':result};observations.append(observation)
        trace.append({'node':'agent_tool','elapsed_ms':round((time.perf_counter()-tool_start)*1000),'details':{'action':action,'ok':ok,'result':result}})
    all_evidence=candidate_evidence(engine.catalog,candidate_pool,read_notes)
    if route!='QA':
        products,rejected_now=engine.catalog.filter(products,req);rejected+=rejected_now
        products,strict_rejected,_=order_candidates(products,req,all_evidence,engine.catalog.products,interpretations=interpretations)
        rejected+=strict_rejected
    products=products[:3]
    if route in ('CLARIFY','CONTENT','OUT_OF_SCOPE'):products=[]
    if route in ('READY','NO_RESULT') and not products and not any(o['action']=='query_catalog' and o['ok'] for o in observations):route='INCOMPLETE'
    evidence=engine.catalog.evidence([p['product_id'] for p in products])
    # Only exact, uniquely version-matched sentences can become recommendation evidence.
    for note in read_notes:
        quotes=[];ids=set()
        for sentence in re.split(r'(?<=[。！？；;\n])',note['text']):
            matched=unique_version_product(sentence,engine.catalog.products)
            if matched and matched['product_id'] in {p['product_id'] for p in products}:
                quotes.append(sentence);ids.add(matched['product_id'])
        if quotes and note['note_id'] not in {n['note_id'] for n in evidence}:
            evidence.append({**note,'text':'\n'.join(quotes),'product_ids':sorted(ids)})
    agent={'version':'bounded-agent-v1','counts':counts,'limits':LIMITS,'stop_reason':stop,'stop_label':STOP_LABELS[stop],
        'events':events,'notes':read_notes,'observations':observations}
    return {'route':route,'requirements':req,'question':question,'summary':'','products':products,'evidence':evidence,
        'rejected':rejected,'trace':trace,'agent':agent,'agent_clarifications':clarifications,
        'candidate_pool':candidate_pool,'preference_evidence':interpretations,
        **({'selection_record':selection_records(candidate_pool,products,req,all_evidence,rejected,engine.catalog.products,interpretations=interpretations)} if route in ('READY','NO_RESULT') or (route=='QA' and not products) else {})}
