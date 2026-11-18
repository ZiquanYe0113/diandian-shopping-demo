from pathlib import Path
import os
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
def settings():
    env={**dotenv_values(ROOT/'.env'),**{k:v for k,v in os.environ.items() if k in ('MODEL_MODE','MODEL_NAME','MODEL_BASE_URL','DASHSCOPE_API_KEY')}}
    return {'mode':env.get('MODEL_MODE','mock'),'key':env.get('DASHSCOPE_API_KEY',''),'model':env.get('MODEL_NAME','qwen3.5-flash'),'base_url':env.get('MODEL_BASE_URL','https://dashscope.aliyuncs.com/compatible-mode/v1')}
