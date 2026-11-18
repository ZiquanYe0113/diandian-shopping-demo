"""Generate original fact cards from verified data. No brand photography or fonts bundled."""
import json,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]

def build():
    folder=ROOT/'web/examples';folder.mkdir(exist_ok=True)
    cards=[('airpods-5','AIRPODS 5 / USB-C CASE',['ANC: supported','Single charge / ANC ON: up to 4 h','Single charge / noise control OFF: up to 6 h','With case / ANC ON: up to 20 h','China official price snapshot: CNY 999'],
      {'note_id':'local:airpods-5','title':'AirPods 5：单次续航和含盒续航怎么区分？','product_ids':['H001'],'source_url':'https://www.apple.com.cn/airpods-5/specs/','text':'自建资料卡，整理官方参数，不是用户试用笔记。\nAirPods5 USB-C充电盒款支持主动降噪；开降噪单次最长4小时，关闭噪声控制最长6小时，开降噪搭配充电盒总计最长20小时。\n官网中国价格快照为999元（2026-10-15）。续航为官方测试最长值，不保证每个人的实际时长。'}),
     ('sony-headband','SONY / HEADBAND COMPARISON',['WH-CH520: on-ear / 147 g / no ANC','WH-CH520: approx. 50 h music playback','WH-CH720N: over-ear / 192 g / ANC','WH-CH720N: approx. 35 h ANC ON','WH-CH720N: approx. 50 h ANC OFF','China price: not verified'],
      {'note_id':'local:sony-headband','title':'CH520 与 CH720N：贴耳、包耳和降噪的差别','product_ids':['H004','H005'],'source_url':'https://www.sonystyle.com.cn/products/headphone/wh_ch520/wh_ch520_feature.html','text':'自建资料卡，依据索尼中国对比表整理，不是实测体验。\nWH-CH520为贴耳式，约147g，不支持聆听主动降噪，持续音乐播放约50小时。\nWH-CH720N为包耳式，约192g，支持主动降噪；开启降噪约35小时，关闭降噪约50小时。\n官网参数不能证明主观舒适度或音质；当前未核实中国售价。'}),
     ('perfume-gardens','HERMES / TWO GARDENS',['Un Jardin sur le Nil / EDT / 50 ml','Notes: green mango, lotus, sycamore','Le Jardin de Monsieur Li / EDT / 50 ml','Notes: jasmine, kumquat, bergamot','China price snapshot: CNY 1030 each'],
      {'note_id':'local:perfume-gardens','title':'两款花园香水的官方资料对照','product_ids':['P001','P002'],'source_url':'https://www.hermes.cn/cn/zh/product/爱马仕尼罗河花园淡香水-V20397/','text':'自建资料卡，整理爱马仕官网信息，不是用户试香笔记。\n尼罗河花园 EDT 50ml，官方描述绿意与木质气息，主要原料青芒果、莲花、梧桐木。\n李先生花园 EDT 50ml，官方描述草本与花香，主要原料茉莉、金橘、佛手柑。\n2026-10-15核验两款50ml中国官网标价均为1030元；气味描述不等于不甜保证或个人留香实测。'})]
    notes=[]
    for name,title,lines,note in cards:
        im=Image.new('RGB',(1000,1050),'#f5f2ec');d=ImageDraw.Draw(im)
        font=ImageFont.load_default(size=30);heading=ImageFont.load_default(size=40)
        d.rounded_rectangle((38,38,962,1012),radius=30,fill='white')
        d.text((75,90),'DIANDIAN / OFFICIAL FACTS',font=font,fill='#e93455')
        d.text((75,180),title,font=heading,fill='#222222')
        for i,line in enumerate(lines):d.text((75,290+i*85),line,font=font,fill='#343434')
        d.text((75,900),'Own fact card / not a product photograph',font=font,fill='#777777')
        d.text((75,950),'Checked: 2026-10-15 / see linked sources',font=font,fill='#777777')
        path=folder/(name+'.png');im.save(path)
        note.update(local_example=True,author='点点 · 自建资料卡',images=[{'index':1,'src':'/web/examples/'+name+'.png'}],image_total=1,image_revision=hashlib.sha256(path.read_bytes()).hexdigest()[:16])
        notes.append(note)
    (ROOT/'data/local-examples.json').write_text(json.dumps({'notes':notes},ensure_ascii=False,indent=2))
if __name__=='__main__':build()
