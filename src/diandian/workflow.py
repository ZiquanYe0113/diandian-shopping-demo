import sqlite3,time,uuid,threading,re,json,hashlib,copy
from pathlib import Path
from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.sqlite import SqliteSaver
from .catalog import Catalog
from .model_client import MockModel,RealModel,Understanding,Requirements
from .note_analysis import validate_analysis,NOTE_ANALYSIS_VERSION
from .note_vision import inspect_images,VISION_VERSION
from .shopping_logic import budget_reply,explicit_budget,is_confirmation,followup,spec,price,qa_answer,qa_evidence,recommendation_details,budget_question,recommendation_followup
from .preferences import update_preferences,order_candidates,selection_records,explain_selection,validate_interpretations

class State(TypedDict,total=False):
    request:dict
    requirements:dict
    route:str
    question:str
    followup_question:str
    summary:str
    products:list
    alternatives:list
    evidence:list
    rejected:list
    trace:list
    answer:str
    history:list
    note_analysis:dict
    note_identity:str
    last_result:dict
    last_request:dict
    recommended_products:list
    selected_products:list
    recommendation_details:list
    agent:dict
    agent_clarifications:int
    candidate_pool:list
    preference_evidence:list
    selection_record:list

class Engine:
    def __init__(self,db,mode='real',key='',base_url='',model='qwen3.5-flash',agent_enabled=False):
        self.catalog=Catalog(); self.lock=threading.Lock(); self._progress=None
        from .local_examples import analysis_images
        self.note_image_loader=analysis_images
        self.agent_enabled=agent_enabled
        self.model=MockModel() if mode=='mock' else RealModel(key,base_url,model)
        Path(db).parent.mkdir(parents=True,exist_ok=True)
        self.note_vision_cache_path=Path(db).parent/'image-analysis.json'
        self.conn=sqlite3.connect(str(db),check_same_thread=False)
        graph=StateGraph(State)
        graph.add_node('understand',self.understand); graph.add_node('retrieve_filter',self.retrieve); graph.add_node('rank_validate',self.rank); graph.add_node('answer',self.answer)
        graph.add_node('analyze_note',self.analyze_note)
        graph.add_node('agent',self.agent_step)
        graph.add_edge(START,'understand')
        graph.add_conditional_edges('understand',lambda s:'agent' if s['route']=='AGENT' else ('analyze_note' if s['route'] in ('NOTE_SUMMARY','NOTE_EXTRACT') else ('retrieve_filter' if s['route'] in ('READY','QA') else 'answer')))
        graph.add_edge('agent','answer')
        graph.add_edge('analyze_note','answer')
        graph.add_conditional_edges('retrieve_filter',lambda s:'rank_validate' if s['route']=='READY' and s['products'] else 'answer')
        graph.add_edge('rank_validate','answer'); graph.add_edge('answer',END)
        self.graph=graph.compile(checkpointer=SqliteSaver(self.conn))
    def close(self): self.conn.close()
    def mark(self,s,node,details,start): return s.get('trace',[])+[{'node':node,'elapsed_ms':round((time.perf_counter()-start)*1000),'details':details}]
    def stage(self,name):
        if self._progress: self._progress(name)
    def agent_step(self,s):
        from .agent import run_agent
        return run_agent(self,s)
    def understand(self,s):
        self.stage('理解需求')
        if s['request']['entry']=='NOTE' and s['request'].get('note_action') in ('summary','extract'):
            return {'route':'NOTE_SUMMARY' if s['request']['note_action']=='summary' else 'NOTE_EXTRACT','trace':s.get('trace',[])}
        start=time.perf_counter(); old=s.get('requirements',{}); q=s['request']['message'].strip()
        if s['request']['entry'] in ('CHAT','SEARCH') and not s['request'].get('images'):
            explanation=explain_selection(q,s.get('selection_record',[]),self.catalog.products,s.get('recommended_products',[]))
            if explanation is not None:
                return {'route':'SELECTION_EXPLANATION','summary':explanation,'requirements':old,'trace':self.mark(s,'selection_explanation',{'record_count':len(s.get('selection_record',[]))},start)}
        from .agent import reset_task_for_category,explicit_category
        category=explicit_category(q)
        old=reset_task_for_category(q,old,category)
        continuation=(s['request']['entry'] in ('CHAT','SEARCH') or (s['request']['entry']=='NOTE' and s['request'].get('note_action')=='shop')) and not s['request'].get('images') and bool(old.get('category'))
        budget=budget_reply(q,old) if continuation else None
        resolved=followup(q,old,s.get('recommended_products',[]),s.get('selected_products',[])) if continuation else None
        if self.agent_enabled and s['request']['entry'] in ('CHAT','SEARCH') and not s['request'].get('images') and (resolved is None or resolved[0]=='READY'):
            return {'route':'AGENT','requirements':resolved[1] if resolved else old,'question':s.get('question',''),'trace':s.get('trace',[])}
        if budget is not None:
            req=budget; route='READY'; result={'clarification_question':'','summary':''}
            if req['budget_min'] is not None and req['budget_min']>req['budget_max']:
                return {'requirements':old,'route':'CLARIFY','question':'预算区间的下限大于上限，请重新填写，例如600–1000元。','trace':self.mark(s,'understand',{'route':'CLARIFY'},start)}
            # A budget answer must not erase an unresolved product/target question.
            if s.get('route')=='CLARIFY' and s.get('question') and '预算' not in s['question']:
                route='CLARIFY'; result['clarification_question']=s['question']
        elif resolved is not None:
            route,req,question=resolved; result={'clarification_question':question,'summary':''}
        else:
            result=Understanding.model_validate(self.model.understand(s['request'],old,self.catalog.products,[{**m,'text':m['text'][:3000]} for m in s.get('history',[])[-6:]],s.get('question',''))).model_dump()
            req=result['requirements']; route=result['route']
            if req.get('target') and req.get('target')!=old.get('target'):
                req['target_ids']=[]
        old=reset_task_for_category(q,old,req.get('category',''))
        parsed_budget=explicit_budget(q)
        if parsed_budget is not None and not req.get('budget_unlimited'):
            req.update(parsed_budget)
        if req.get('budget_unlimited'): req.update(budget_min=None,budget_max=None)
        if old.get('strict_preferences') and not req.get('strict_preferences'):
            req['strict_preferences']=old['strict_preferences']
        from .agent import merge_requirements,apply_browse_scope
        cleaned=merge_requirements(q,old,req,semantic_only=self.model.mode=='real',previous_question=s.get('question',''))
        browsing=route in ('READY','OUT_OF_SCOPE') or (route=='CLARIFY' and bool(re.search(r'预算|价位|多少钱',result.get('clarification_question',''))))
        cleaned=apply_browse_scope(q,cleaned,self.catalog.products,clear_target=browsing,semantic_context={'category':req.get('category'),'scope_text':req.get('target_quote'),'exclusion_quotes':req.get('exclusion_quotes')})
        for field in ('browse_product_ids','browse_label','excluded_product_ids'):
            req[field]=cleaned[field]
        if cleaned.get('browse_product_ids') is not None:
            req.update(category=cleaned['category'],browse_product_ids=cleaned['browse_product_ids'],browse_label=cleaned['browse_label'])
            if browsing:
                req.update(target=cleaned['target'],target_ids=cleaned['target_ids'])
                if route in ('CLARIFY','OUT_OF_SCOPE'):route='READY';result['clarification_question']=''
        for field in ('budget_min','budget_max','budget_unlimited','attribute_filters','preferences','strict_preferences','preference_constraints','preference_updates','preferences_structured','budget_deferred'):
            req[field]=cleaned[field]
        if cleaned['budget_deferred']:
            req.update(budget_min=None,budget_max=None,budget_unlimited=False)
        budget_ready=req.get('budget_max') is not None or req.get('budget_unlimited') or req.get('budget_deferred') or req.get('browse_product_ids') is not None
        if route=='CLARIFY' and s['request']['entry'] in ('CHAT','SEARCH') and not s['request'].get('images') and not req['target'] and not req['target_ids'] and req['category'] in ('香水','耳机') and budget_ready and re.search(r'预算|场景|偏好|喜欢|味道|香调|风格|品牌|价位|佩戴|降噪|续航|通勤|运动|居家',result.get('clarification_question','')):
            route='READY';result['clarification_question']=''
        if route=='CLARIFY' and not req['target'] and not req['target_ids'] and req['category'] in ('香水','耳机') and (req['budget_max'] is not None or req['budget_unlimited']) and re.search(r'预算|价位|价格|多少钱|不限',result.get('clarification_question','')):
            result['clarification_question']='你主要想在什么场景使用？例如通勤、约会或送礼。' if not req['use_case'] else '你偏好什么香调或风格？例如清新、花香或木质。'
            if req['category']=='耳机':result['clarification_question']='你主要用来通勤、运动，还是居家聆听？' if not req['use_case'] else '你偏好哪种佩戴方式，或更看重降噪、续航？'
        if route=='CLARIFY' and s['request']['entry'] in ('CHAT','SEARCH') and not s['request'].get('images') and req['category'] in ('香水','耳机') and not req['target'] and (req['budget_max'] is not None or req['budget_unlimited']) and re.search(r'(?:偏好|喜欢).{0,5}品牌|品牌.{0,5}(?:偏好|要求|喜欢)',result.get('clarification_question','')):
            route='READY'
        if route=='READY' and not req['category'] and not req['target']:
            route='CLARIFY'; result['clarification_question']='你想选购哪一类商品？例如香水。'
        note_shopping=s['request']['entry']=='NOTE' and s['request'].get('note_action')=='shop'
        if (route=='READY' or (note_shopping and route=='QA')) and req['category'] in ('香水','耳机') and (not req['target'] or note_shopping) and not budget_ready:
            route='CLARIFY'; result['clarification_question']=budget_question(req)
        if route=='CLARIFY' and not budget_ready and req['category'] in ('香水','耳机') and '预算' in result.get('clarification_question',''):
            result['clarification_question']=budget_question(req)
        return {'requirements':req,'route':route,'question':result['clarification_question'] or '请补充最关键的选购条件。','summary':result['summary'],'trace':self.mark(s,'understand',{'route':route,'requirements':req},start)}
    def analyze_note(self,s):
        self.stage('分析笔记')
        start=time.perf_counter(); request=s['request']; note=request.get('note_context',{})
        images=[]
        if note.get('note_id','').startswith(('xhs:','local:','curated:')) and getattr(self,'note_image_loader',None):
            self.stage('读取笔记图片')
            images=self.note_image_loader(note['note_id'])
        stats={'image_count':len(images),'image_cache_hits':0,'image_model_calls':0}
        observations=[]
        if images:
            observations,stats=inspect_images(images,self.model,self.note_vision_cache_path,self.stage)
            note={**note,'image_observations':observations}
        self.stage('分析正文与图片')
        history=[{**m,'text':m['text'][:3000]} for m in s.get('history',[])[-6:]]
        raw=self.model.analyze_note(note,request['note_action'],self.catalog.products,request['message'],history)
        if images:raw={**raw,'image_observations':observations}
        analysis=validate_analysis(raw,{**note,'image_indexes':[im['index'] for im in images]},self.catalog.products)
        ids=[m['product_id'] for m in analysis['mentions'] if m['product_id']]
        products=[p for p in self.catalog.products if p['product_id'] in ids] if request['note_action']=='extract' else []
        return {'note_analysis':analysis,'products':products,'trace':self.mark(s,'analyze_note',{'action':request['note_action'],'matched_ids':ids,'mention_count':len(analysis['mentions']),**stats},start)}
    def retrieve(self,s):
        self.stage('检索并筛选商品')
        start=time.perf_counter(); found=self.catalog.search(s['requirements'])
        products,rejected=self.catalog.filter(found,s['requirements']) if s['route']=='READY' else (found[:3],[])
        evidence=self.catalog.evidence([p['product_id'] for p in products])
        if s['route']=='READY':
            products,strict_rejected,_=order_candidates(products,s['requirements'],evidence,self.catalog.products,allow_unverified_hard=True,allow_conflicting_hard=True)
            rejected+=strict_rejected
        if s['route']=='QA': evidence=qa_evidence(s['request']['message'],evidence)
        return {'products':products,'candidate_pool':found,'rejected':rejected,'evidence':evidence,'trace':self.mark(s,'retrieve_filter',{'candidate_ids':[p['product_id'] for p in found],'rejected':rejected},start)}
    def rank(self,s):
        self.stage('排序并校验候选')
        start=time.perf_counter();ranking=self.model.rank(s['requirements'],s['products'],s['evidence']);ids=ranking['ids']
        byid={p['product_id']:p for p in s['products']}
        if len(ids)>3 or len(set(ids))!=len(ids) or not set(ids)<=set(byid): raise ValueError('INVALID_RANKING')
        interpretations=validate_interpretations(ranking.get('preference_evidence',[]),s['requirements'],s['products'],s['evidence'],self.catalog.products)
        selected=[byid[i] for i in ids]
        combined=selected+[p for p in s['products'] if p not in selected]
        selected,rejected,_=order_candidates(combined,s['requirements'],s['evidence'],self.catalog.products,interpretations=interpretations)
        selected=selected[:len(ids)]
        return {'products':selected,'preference_evidence':interpretations,'rejected':s.get('rejected',[])+rejected,
            'evidence':self.catalog.evidence([p['product_id'] for p in selected]),
            'trace':self.mark(s,'rank_validate',{'model_selected_ids':ids,'selected_ids':[p['product_id'] for p in selected],'rejected':rejected},start)}

    def answer(self,s):
        self.stage('整理结果')
        start=time.perf_counter(); route=s['route']; products=s.get('products',[]);alternatives=[]
        if route in ('NOTE_SUMMARY','NOTE_EXTRACT'):
            a=s['note_analysis']; text=a['summary']
            if route=='NOTE_SUMMARY':
                if a['key_points']: text+='\n'+'\n'.join('• '+p for p in a['key_points'])
                if a['author_opinion']: text+='\n作者观点：'+a['author_opinion']
            else:
                text+='\n'+('\n'.join(m['name']+'：'+('已匹配商品资料' if m['product_id'] else '商品或版本尚未确认') for m in a['mentions']) if a['mentions'] else '本篇没有明确提及可提取的商品。')
        elif route=='CLARIFY': text=s['question']
        elif route=='OUT_OF_SCOPE': text='这里提供商品导购。你可以告诉我想选什么商品。'
        elif route=='IDENTIFY': text=s['summary'] or '目前无法可靠确认图片里的品牌和型号，请补充清晰图片或指定目标。'
        elif route=='SELECTION_EXPLANATION': text=s['summary']
        elif route=='CONTENT':
            text='这是普通内容搜索，请使用小红书原生搜索。' if s['request']['entry']=='SEARCH' else (s['summary'] or '这篇笔记没有可确认的商品。你可以指定想选购的用品类别。')
        elif route=='INCOMPLETE': text='这次还没完成商品查询，暂时无法判断有没有符合条件的商品。你可以补充条件或再试一次。'
        elif not products:
            from .alternatives import no_result_response
            route='NO_RESULT';text,alternatives=no_result_response(self.catalog,s.get('requirements',{}),s.get('rejected',[]))
        elif route=='QA':
            text=qa_answer(s['request']['message'],products,s.get('evidence',[]),self.catalog.products)
        else:
            text=('预算还没定，先给几款参考候选，暂未按预算筛选：\n' if s.get('requirements',{}).get('budget_deferred') else '根据当前条件，候选如下：\n')+'\n'.join(f"{i+1}. {p['product_name']}｜{p['concentration']+'｜' if p['concentration'] else ''}{spec(p)}｜参考价 {price(p)}" for i,p in enumerate(products))
        if products: text+='\n价格和在售状态为资料快照，不是实时库存；缺失属性不视为满足。'
        agent=s.get('agent',{})
        if agent and agent.get('stop_reason') not in ('completed','asked_user'):
            text+='\n'+('已根据本轮取得的资料整理候选。' if products else '本轮查询未继续执行，可以补充条件或重试。')
        if agent and any(o['result'].get('network_status')=='unavailable' for o in agent.get('observations',[])):
            text+='\n真实笔记搜索未完成，本次使用已保存或本地资料。'
        refinement=recommendation_followup(s.get('requirements',{}),visible_count=len(products)) if route=='READY' and s['request']['entry'] in ('CHAT','SEARCH') else ''
        if refinement:text+='\n'+refinement
        # Render factual cards verbatim; avoid free generation changing prices/versions.
        history=s.get('history',[])+[{'role':'user','text':s['request']['message']},{'role':'assistant','text':text}]
        context={}
        if route in ('READY','NO_RESULT'):
            pool=s.get('candidate_pool',[])
            # Agent records include real-note observations; fixed-flow records use its catalog evidence.
            records=s.get('selection_record',[]) if s.get('agent') else selection_records(pool,products,s.get('requirements',{}),self.catalog.evidence([p['product_id'] for p in pool]),s.get('rejected',[]),self.catalog.products,interpretations=s.get('preference_evidence',[]))
            context={'recommended_products':products,'selected_products':products,'selection_record':records}
        elif route=='QA': context={'selected_products':products}
        details=recommendation_details(products,s.get('requirements',{}),s.get('evidence',[]),self.catalog.products,interpretations=s.get('preference_evidence',[])) if route=='READY' else []
        return {**context,'alternatives':alternatives,'recommendation_details':details,'route':route,'answer':text,'followup_question':refinement,**({'question':refinement} if route=='READY' else {}),'history':history[-40:],'trace':self.mark(s,'answer',{'status':route,'product_count':len(products)},start)}
    def run(self,request,progress=None):
        with self.lock:
            sid=request.get('session_id') or str(uuid.uuid4()); config={'configurable':{'thread_id':sid}}
            start=time.perf_counter(); self.model.usage=[]; self._progress=progress
            try:
                previous=self.graph.get_state(config).values
                note=request.get('note_context',{})
                cache_identity={'note':note,'analysis_version':NOTE_ANALYSIS_VERSION,'vision_version':VISION_VERSION,'model':getattr(self.model,'model','mock'),'mode':self.model.mode,'catalog_revision':self.catalog.revision}
                identity=hashlib.sha256(json.dumps(cache_identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest() if request['entry']=='NOTE' else ''
                last=previous.get('last_result',{})
                revision_changed=bool(previous) and last.get('catalog_revision')!=self.catalog.revision
                same_note=identity and identity==previous.get('note_identity','') and request.get('note_action') in ('summary','extract') and previous.get('last_request',{}).get('note_action')==request.get('note_action') and previous.get('last_request',{}).get('message')==request.get('message')
                shopping_context=(request['entry'] in ('CHAT','SEARCH') and not previous.get('note_identity')) or (request['entry']=='NOTE' and request.get('note_action')=='shop' and identity==previous.get('note_identity'))
                confirmed=shopping_context and not request.get('images') and is_confirmation(request['message']) and last.get('status')=='READY' and last.get('requirements')==previous.get('requirements')
                if last and not revision_changed and last.get('status')!='ERROR' and (same_note or confirmed):
                    self.stage('复用已完成结果')
                    out={**copy.deepcopy(last),'cache_hit':True,'usage':[],'elapsed_ms':round((time.perf_counter()-start)*1000),'trace':[{'node':'cache','elapsed_ms':0,'details':{'cache_hit':True}}]}
                    self.graph.update_state(config,{'last_result':out,'last_request':request})
                    self._progress=None
                    return out
                initial={'request':request,'trace':[],'products':[],'alternatives':[],'candidate_pool':[],'preference_evidence':[],'evidence':[],'rejected':[],'note_analysis':{},'agent':{},'note_identity':identity,'requirements':previous.get('requirements',{})}
                if previous.get('last_result',{}).get('status')=='READY':initial['agent_clarifications']=0
                if revision_changed:initial.update(recommended_products=[],selected_products=[],selection_record=[],last_result={},last_request={},agent_clarifications=0)
                if identity!=previous.get('note_identity',''): initial.update(requirements={},history=[],recommended_products=[],selected_products=[],selection_record=[],last_result={},last_request={},agent_clarifications=0)
                result=self.graph.invoke(initial,config)
                out={'session_id':sid,'status':result['route'],'answer':result['answer'],'followup_question':result.get('followup_question',''),'products':result.get('products',[]),'alternatives':result.get('alternatives',[]),'evidence':result.get('evidence',[]),'requirements':result.get('requirements',{}),'note_analysis':result.get('note_analysis',{}),'recommendation_details':result.get('recommendation_details',[]),'trace':result['trace']}
                if result.get('agent'):out['agent']=result['agent']
                out['selection_record']=result.get('selection_record',[])
            except Exception as error:
                from openai import APIStatusError,APITimeoutError,APIConnectionError
                from pydantic import ValidationError
                code='MODEL_REQUEST_FAILED'; message='模型请求未完成，请重试。'
                if isinstance(error,APIStatusError):
                    code=f'MODEL_HTTP_{error.status_code}'
                    upstream_code=error.code or ''
                    if upstream_code in ('insufficient_quota','Arrearage','AllocationQuota.FreeTierOnly'): message='模型服务报告额度或余额不足，请检查阿里云控制台。'
                    elif error.status_code in (401,403): message='模型服务拒绝访问，请检查密钥及模型权限。'
                    elif error.status_code==429: message='模型服务限流，请稍后重试。'
                    else: message='模型服务暂时不可用，请稍后重试。'
                elif isinstance(error,(ValidationError,json.JSONDecodeError)):
                    code='MODEL_OUTPUT_INVALID'; message='模型返回格式不符合要求，请重试。'
                elif isinstance(error,APITimeoutError):
                    code='MODEL_TIMEOUT'; message='模型响应超时，请重试。'
                elif isinstance(error,APIConnectionError):
                    code='MODEL_CONNECTION_FAILED'; message='无法连接模型服务，请检查网络后重试。'
                elif isinstance(error,ValueError) and request.get('entry')=='NOTE' and ('图片' in str(error) or '真实笔记' in str(error)):
                    code='NOTE_IMAGES_UNAVAILABLE';message=str(error)
                elif str(error)=='MODEL_OUTPUT_TRUNCATED':
                    code='MODEL_OUTPUT_TRUNCATED'; message='模型输出被截断，请重试。'
                elif str(error) in ('API_KEY_NOT_CONFIGURED','INVALID_RANKING'): code=str(error); message='请配置本地密钥。' if code=='API_KEY_NOT_CONFIGURED' else '模型排序未通过校验，请重试。'
                out={'session_id':sid,'status':'ERROR','answer':'运行失败：'+code+'。'+message,'products':[],'evidence':[],'trace':[{'node':'error','details':{'code':code}}],'requirements':{}}
                if getattr(error,'agent_report',None):
                    out['agent']=error.agent_report
                    out['trace']=error.agent_trace+out['trace']
                if getattr(error,'image_stats',None):
                    out['trace'][0]['details'].update(error.image_stats)
                    out['answer']+=' 已完成的图片识别已保存，重试会复用这些结果。'
            out={**out,'catalog_revision':self.catalog.revision,'recommendation_details':out.get('recommendation_details',[]),'cache_hit':False,'mode':self.model.mode,'usage':self.model.usage,'elapsed_ms':round((time.perf_counter()-start)*1000)}
            self.graph.update_state(config,{'last_result':out,'last_request':request})
            self._progress=None
            return out
    def session(self,sid):
        with self.lock:
            value=self.graph.get_state({'configurable':{'thread_id':sid}}).values
            return {'session_id':sid,'requirements':value.get('requirements',{}),'history':value.get('history',[]),'last_result':value.get('last_result',{})}
