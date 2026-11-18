"""The complete action allowlist and code-owned execution budgets."""
from typing import Literal,get_args
from pydantic import BaseModel,ConfigDict,Field,field_validator
from .model_client import ModelRequirements,AttributeFilter
from .preference_contract import PreferenceEvidence

LIMITS={'decisions':4,'searches':2,'reads':3,'clarifications':1,'seconds':180}

class AgentDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['ask_user','query_catalog','search_notes','read_note','finish']
    requirements:ModelRequirements=Field(default_factory=ModelRequirements,description='仅填写用户本轮明确提供或修改的需求；未改变的条件由代码保留。')
    preference_evidence:list[PreferenceEvidence]=Field(default_factory=list,max_length=36)
    query:str=Field(default='',max_length=120)
    search_scope:Literal['local','xhs','both']='both'
    note_id:str=Field(default='',max_length=100)
    product_ids:list[str]=Field(default_factory=list,max_length=3)
    ask_field:Literal['category','budget','use_case','preferences','target','']=Field(default='',description='ask_user时填写顶层待补充字段；佩戴方式、降噪、连接、续航等商品属性统一填写preferences。其他行动可留空。空值由代码根据实际缺失字段选择，不放宽权限。')
    @field_validator('ask_field',mode='before')
    @classmethod
    def product_attributes_are_preferences(cls,value):
        # Known nested product fields are legitimate clarification targets, not new
        # tools or permissions. Keep the execution contract at top-level fields.
        return 'preferences' if value in get_args(AttributeFilter.model_fields['key'].annotation) else value

    question:str=Field(default='',max_length=300)
    finish_route:Literal['READY','QA','CONTENT','OUT_OF_SCOPE','NO_RESULT']='READY'
    reason:str=Field(default='',max_length=180,description='一句简短的行动目的，不输出内部推理。')

STOP_LABELS={
    'completed':'资料足够，完成回答','asked_user':'等待用户补充',
    'decision_limit':'已达到本轮4次决策上限','search_limit':'已达到本轮2次笔记搜索上限',
    'read_limit':'已达到本轮3篇笔记读取上限',
    'repeated_action':'重复行动没有带来新信息，停止调用','time_limit':'本轮处理已达到时间上限',
    'invalid_selection':'模型选择未通过商品校验，使用已校验候选收尾',
}
