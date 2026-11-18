#!/usr/bin/env python3
"""Isolated business workflow evaluation; no browser history or production sessions."""
import argparse,json,sys,time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from diandian.config import ROOT,settings
from diandian.workflow import Engine
from diandian.business_evaluation import validate_business_cases,check_business_result,summarize


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['mock','real'],default='mock')
    p.add_argument('--dataset',type=Path,default=ROOT/'evaluations/business-v2.json')
    p.add_argument('--cases',help='逗号分隔的ID；默认全部')
    p.add_argument('--token-budget',type=int,default=400000)
    p.add_argument('--label',default='baseline')
    a=p.parse_args()
    if a.token_budget<1:p.error('token-budget必须大于0')
    dataset=json.loads(a.dataset.read_text());cases=dataset['cases']
    # Reuse strict base schema without treating extra business checks as unknown.
    validate_business_cases(cases)
    if a.cases:
        ids=a.cases.split(',');known={c['id']:c for c in cases}
        if set(ids)-known.keys():p.error('未知用例ID')
        cases=[known[i] for i in ids]
    name=datetime.now(ZoneInfo('Australia/Brisbane')).strftime('%Y%m%d-%H%M%S')+'-'+a.mode+'-'+a.label
    directory=ROOT/'results/business'/name;directory.mkdir(parents=True,exist_ok=False)
    config=settings() if a.mode=='real' else {'mode':'mock'};config['mode']=a.mode
    if a.mode=='real' and not config.get('key'):p.error('未配置API密钥；未发起调用')
    engine=Engine(ROOT/'runtime/business-evaluations'/name/'sessions.db',agent_enabled=True,**config)
    rows=[];stop='';errors=0
    def save():
        metrics=summarize(rows,len(cases))
        report={'version':dataset['version'],'mode':a.mode,'agent_enabled':True,'model':config.get('model','MockModel'),
                'metrics':metrics,'stop_reason':stop,'semantic_review':'pending','cases':rows}
        (directory/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        lines=['# 业务链路自动测评',f"模式：{a.mode}；Agent：开启；完整场景 {metrics['completed_cases']}/{len(cases)}；通过 {metrics['passed_cases']}。",f"轮次通过 {metrics['passed_turns']}/{metrics['turns']}；错误 {metrics['error_turns']}；模型调用 {metrics['model_calls']}；tokens {metrics['total_tokens']}；平均 {metrics['mean_ms']}ms；P95 {metrics['p95_ms']}ms。",'这是工作流集成测评，不等同于浏览器端到端测试。自动门槛与语义复核分别记录。',f'停止原因：{stop or "正常完成"}','','|用例|完成|失败门槛|','|---|---|---|']
        for c in rows:lines.append(f"|{c['id']} {c['title']}|{c['complete']}|"+'；'.join(f"{i+1}轮：{','.join(t['failures'])}" for i,t in enumerate(c['turns']) if t['failures'])+'|')
        (directory/'report.md').write_text('\n'.join(lines))
        return metrics
    try:
        for case in cases:
            row={k:case[k] for k in ('id','title','split')};row.update(turns=[],complete=False);rows.append(row);sid=None
            for turn in case['turns']:
                if a.mode=='real' and summarize(rows,len(cases))['total_tokens']>=a.token_budget:stop='token预算到达；单次请求可能跨越阈值';break
                request={k:v for k,v in turn.items() if k!='expected'}
                if sid:request['session_id']=sid
                result=engine.run(request);sid=result['session_id']
                failures=check_business_result(turn['expected'],request,result)
                row['turns'].append({'request':request,'expected':turn['expected'],'result':result,'failures':failures})
                print(f"{case['id']} #{len(row['turns'])} {result['status']}: {','.join(failures) or 'PASS'}",flush=True)
                if result['status']=='ERROR':errors+=1
                row['complete']=len(row['turns'])==len(case['turns']);save()
                if errors>=3 and a.mode=='real':stop='累计3次模型/请求错误，停止付费批次';break
            if stop:break
    finally:
        engine.close();metrics=save()
    print(json.dumps(metrics,ensure_ascii=False));print(directory/'report.md')
    return 0 if metrics['passed_cases']==len(cases) and not stop else 1

if __name__=='__main__':raise SystemExit(main())
