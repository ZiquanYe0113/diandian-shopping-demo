"""Build a standalone, explicitly scripted four-entry demo for GitHub Pages."""
from pathlib import Path
import shutil,json
ROOT=Path(__file__).resolve().parents[1]
def build():
 out=ROOT/'demo';out.mkdir(exist_ok=True)
 shutil.copytree(ROOT/'web/xhs',out/'web/xhs',dirs_exist_ok=True)
 shutil.copytree(ROOT/'web/examples',out/'web/examples',dirs_exist_ok=True)
 p=next(p for p in json.loads((ROOT/'data/source/headphones.json').read_text())['products'] if p['product_id']=='H005')
 note={'note_id':'demo:sony','title':'WH-CH720N：通勤前先看这几个参数','text':'索尼 WH-CH720N 是头戴包耳式耳机，支持主动降噪，重量约192g。官方测试开启降噪最长35小时，关闭降噪最长50小时。参数不能代替实际舒适度和音质体验。','product_ids':['H005'],'curated':True,'local_example':True,'source_author':'个人演示文案','original_title':'官方参数整理（非体验帖）','author':'点点 · 演示笔记','images':[{'index':1,'src':'./web/examples/sony-wh-ch720n-official.png'}],'image_total':1,'source_url':p['source_url']}
 titles=[('WH-CH720N：通勤前先看这几个参数',note['text']),('降噪开关不同，续航该怎么看？','索尼 WH-CH720N 开启降噪官方测试最长35小时，关闭降噪最长50小时。不同条件不能混为同一结论。'),('头戴包耳式，买前先确认佩戴需求','索尼 WH-CH720N 是头戴包耳式，重量约192g，不是入耳式。本演示没有舒适度实测结论。'),('只看参数还不够：这款耳机的选购提醒','索尼 WH-CH720N 支持主动降噪，但功能支持不能证明主观效果。颜色与实际结算价格需要另行核实。')]
 photos=['sony-wh-ch720n-official.png','sony-wh-ch720n-1.jpg','sony-wh-ch720n-2.jpg','sony-wh-ch720n-3.jpg']
 notes=[{**note,'images':[{'index':1,'src':'./web/examples/'+photos[i]}],'note_id':'demo:sony' if i==0 else 'demo:sony-'+str(i),'title':title,'text':body} for i,(title,body) in enumerate(titles)]
 (out/'fixtures.json').write_text(json.dumps({'products':[p],'notes':notes},ensure_ascii=False))
 html=(ROOT/'web/xhs/index.html').read_text().replace('/web/','./web/').replace('正在连接本地服务…','预置交互演示 · 不调用大模型')
 html=html.replace('本地收录 · 香水与耳机导购','单品演示 · WH-CH720N').replace('把真实笔记<br>交给点点。','从四个入口<br>了解同一款。').replace('导入你的小红书笔记，','点击首页演示笔记，').replace('在右侧体验图文总结与商品识别。','在右侧体验总结与商品关联。')
 html=html.replace('<button data-action="search">⌕ 内容搜索</button>','<button data-action="search">⌕ 内容搜索</button><button data-action="market">♧ 市集 AI 购物</button>').replace('点击首页演示笔记，','点点对话、原生搜索、首页笔记，').replace('在右侧体验总结与商品关联。','以及「市集 → 右上角 ai购物」，四个入口都可以体验。')
 html=html.replace('<body>','<body><div style="position:fixed;top:0;left:0;right:0;z-index:999;background:#fff5d7;color:#594318;text-align:center;padding:6px;font-size:12px">个人复盘项目 · 单商品预置交互小样，非实时 AI；耳机图来自索尼官方，价格为历史快照</div>')
 html=html.replace('src="./web/xhs/app.js?v=market-ai-v1"','src="./offline.mjs"')
 html=html.replace('<a href="./web/index.html">打开工作流调试页 ↗</a>','')
 # The static demo exposes only the four product entrances.
 html=html.replace('<div id="real-note-demo"></div>','<p>本小样使用四篇本地演示笔记。真实笔记接入请使用完整项目。</p>')
 (out/'index.html').write_text(html)
 for file in (out/'web/xhs').glob('*'):
  if file.suffix not in ('.js','.mjs','.css'):continue
  s=file.read_text().replace('/web/','./web/').replace('1500元内，清新通勤香水 ↗','1000元内，通勤耳机 ↗').replace('预算1500元，想买清新的通勤香水','预算1000元，想买通勤耳机').replace('尼罗河花园是什么香调？','WH-CH720N续航多久？').replace('想选香水，还没想好预算 ↗','先了解这款耳机 ↗').replace('想买一瓶通勤香水，喜欢清新的','想了解WH-CH720N').replace('选香水、挑耳机','了解WH-CH720N').replace('香水与耳机 · 支持本地图文示例','单品预置演示 · 支持本地笔记示例').replace('内容由 AI 生成','内容为预置演示').replace('模拟模式','预置演示')
  if file.name=='views.js':
   s=s.replace('function cover(n,large=false){',"function cover(n,large=false){if(n.local_example&&n.images?.[0]?.src?.startsWith('./web/examples/sony-wh-ch720n-'))return `<div class=\"feed-real-photo\"><img src=\"${esc(n.images[0].src)}\" alt=\"索尼官方 WH-CH720N 产品图\" loading=\"lazy\"></div>`;")
   s=s.replace('sony-headband.png','sony-wh-ch720n-official.png').replace('品类示意','官方产品图')
   s=s.replace(r'\.png$',r'\.(?:png|jpg)$')
   s=s.replace(r'^\/web\/examples\/',r'^\.\/web\/examples\/').replace('查看原帖','查看官方资料').replace('原作者：','文案：').replace('原帖：','依据：').replace('自建资料卡','演示配图').replace('总结时一起分析','预置文字总结，不执行识图')
  if file.name=='app.js':
   s=s.replace("import {homeNotes as originalNotes} from '../reference/data.js';",'const originalNotes=[];')
   s=s.replace("const STORAGE='diandian-xhs-v2-real-catalog'","const STORAGE='diandian-static-demo-v1'")
   s=s.replace('notes=[fragrance[0],life[0],fragrance[1],life[1],fragrance[2],life[2],...fragrance.slice(3),...life.slice(3)];','notes=fragrance;')
   s=s.replace("document.querySelector('#mode').textContent=mode==='mock'?'模拟模式 · 不调用API':'Qwen3.5-Flash · 真实模式';","document.querySelector('#mode').textContent='预置交互演示 · 不调用模型';")
  if file.name=='styles.css':s+='\n.feed-real-photo{height:auto;aspect-ratio:4/3;background:#fff}.feed-real-photo img{width:100%;height:100%;object-fit:contain}.note-picture-track img{object-fit:contain}.feed-real-photo img[src$=".jpg"]{object-fit:cover;object-position:left center}\n'
  file.write_text(s)
 shutil.copyfile(ROOT/'scripts/demo-offline.mjs',out/'offline.mjs')
 (out/'.nojekyll').touch()
 return out
if __name__=='__main__':print(build())
