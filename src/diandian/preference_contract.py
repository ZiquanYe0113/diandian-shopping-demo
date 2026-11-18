"""Category-independent preference data. Interpretation is model-owned; gates are code-owned."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class PreferenceConstraint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    attribute: str = Field(min_length=1, max_length=60, description='属性维度；复用已知约束的维度和值，例如香调/木质、甜度/甜；其他品类按真实属性填写')
    value: str = Field(min_length=1, max_length=80, description='正向原子属性，避免将否定词写入值；例如甜而非不甜')
    polarity: Literal['prefer', 'avoid'] = 'prefer'
    strength: Literal['soft', 'hard'] = 'soft'
    quote: str = Field(min_length=1, max_length=500, description='用户当前消息中的连续原文，不能引用历史助手或笔记来修改用户要求')


class PreferenceUpdate(PreferenceConstraint):
    polarity: Literal['prefer', 'avoid']
    strength: Literal['soft', 'hard']
    operation: Literal['upsert', 'remove']


class PreferenceEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: str = Field(min_length=1, max_length=100)
    attribute: str = Field(min_length=1, max_length=60)
    value: str = Field(min_length=1, max_length=80)
    presence: Literal['present', 'absent', 'uncertain']
    source_type: Literal['catalog', 'note']
    field: str = Field(default='', max_length=80)
    note_id: str = Field(default='', max_length=100)
    quote: str = Field(min_length=2, max_length=1200, description='实际已观察资料中的连续原文，含必要的否定、程度和主体上下文；不可截去否定后声称肯定')
