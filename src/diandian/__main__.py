"""Portable local entry: python -m diandian --mode mock."""
import argparse,os
from .config import settings

def runtime_options(argv=None):
    parser=argparse.ArgumentParser(description='点点本地导购：mock无需Key；real使用本地.env或环境变量')
    parser.add_argument('--mode',choices=('mock','real'))
    parser.add_argument('--host',choices=('127.0.0.1','localhost'),default='127.0.0.1')
    parser.add_argument('--port',type=int,default=4186)
    args=parser.parse_args(argv)
    if not 1<=args.port<=65535:parser.error('port须在1–65535之间')
    config=settings()
    if args.mode:config['mode']=args.mode
    return {'host':args.host,'port':args.port,'settings':config}

def main(argv=None):
    import uvicorn
    from .server import create_app
    options=runtime_options(argv);config=options['settings']
    if config['mode']=='real' and not config['key']:
        raise SystemExit('真实模式尚未配置DASHSCOPE_API_KEY。请在本地.env配置，或先用 --mode mock 启动。')
    os.environ['MODEL_MODE']=config['mode']
    os.environ['LANGSMITH_TRACING']='false';os.environ['LANGCHAIN_TRACING_V2']='false'
    uvicorn.run(create_app(),host=options['host'],port=options['port'])

if __name__=='__main__':main()
