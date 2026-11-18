import csv,json,re,hashlib
from pathlib import Path
from .note_analysis import matching_products
from .product_facts import normalize,attribute_rejection
ROOT=Path(__file__).resolve().parents[2]

class Catalog:
    def __init__(self):
        self.products=list(csv.DictReader((ROOT/'data/source/products.csv').open(encoding='utf-8-sig')))
        ids=[p['product_id'] for p in self.products]
        if len(set(ids))!=len(ids): raise ValueError('重复商品 ID')
        for p in self.products:
            p['reference_price_cny']=float(p['reference_price_cny']) if p['reference_price_cny'] else None
            p['actual_spec_value']=float(p['actual_spec_value']) if p['actual_spec_value'] else None
        overlays={p['product_id']:p for p in json.loads((ROOT/'data/source/perfume-verification.json').read_text())['products']}
        self.products=[normalize({**p,**overlays[p['product_id']]}) for p in self.products]
        self.products += [normalize(p) for p in json.loads((ROOT/'data/source/headphones.json').read_text())['products']]
        self.notes=[]
        for path in sorted((ROOT/'data/source/notes').glob('*.txt')):
            text=path.read_text(); parts=text.split('---',2)
            meta=dict(re.findall(r'^([a-z_]+):\s*(.*)$',parts[1],re.M))
            ids=re.findall(r'[PH]\d{3}',meta.get('mentioned_product_ids',''))
            if not set(ids)<=set(p['product_id'] for p in self.products): raise ValueError('笔记引用不存在商品')
            self.notes.append({'note_id':meta.get('note_id',path.stem),'title':meta.get('note_title',path.stem),'source_url':meta.get('source_url',''),'product_ids':ids,'text':parts[2].strip()})
        from .curated_notes import notes as curated_notes
        self.notes=curated_notes()+self.notes
    @property
    def revision(self):
        return hashlib.sha256(json.dumps([self.products,self.notes],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
    def search(self, req):
        category={'女士香水':'香水','perfume':'香水','headphones':'耳机'}.get(req.get('category'),req.get('category'))
        if category not in ('香水','耳机'): return []
        products=[p for p in self.products if p.get('category')==category]
        if not req.get('target') and not req.get('target_ids') and req.get('browse_product_ids') is None:products=[p for p in products if p.get('verified_for_recommendation',True)]
        if req.get('browse_product_ids') is not None:
            scope=set(req['browse_product_ids'])
            products=[p for p in products if p['product_id'] in scope]
        target=req.get('target','').lower().strip()
        if req.get('target_ids'):
            if target:
                products=[p for p in products if target in p['product_id'].lower() or any(target in n or (len(n)>2 and n in target) for n in [p['product_name'].lower()]+p['aliases'].lower().split(';'))]
            byid={p['product_id']:p for p in products}
            return [byid[i] for i in req['target_ids'] if i in byid]
        def names(p): return [p['product_name'].lower()]+p['aliases'].lower().split(';')
        if target:
            return [p for p in products if target in p['product_id'].lower() or any(target in n or (len(n)>2 and n in target) for n in names(p))]
        words=req.get('preferences',[])+[req.get('use_case','')]
        return sorted(products,key=lambda p:sum(w.lower() in p['search_text'].lower() for w in words if w),reverse=True)
    def filter(self, products, req):
        good=[]; rejected=[]
        for p in products:
            reason=None; price=p.get('reference_price_cny'); budget=req.get('budget_max')
            if req.get('category') in ('香水','耳机','女士香水','perfume') and p.get('category')!={'女士香水':'香水','perfume':'香水'}.get(req['category'],req['category']): reason='品类不符'
            elif req.get('browse_product_ids') is not None and p['product_id'] not in req['browse_product_ids']: reason='不在明确品牌/系列/型号范围内'
            elif p.get('verified_for_recommendation') is False: reason='商品事实待核验，暂停推荐'
            elif p['product_id'] in req.get('excluded_product_ids',[]): reason='命中用户排除或换一批要求'
            elif budget is not None and (price is None or float(price)>budget): reason='超出实际规格预算' if price is not None else '实际价格未知'
            elif req.get('budget_min') is not None and (price is None or price<req['budget_min']): reason='低于明确预算区间' if price is not None else '实际价格未知'
            elif p.get('availability') in ('缺货','售罄','sold_out'): reason='缺货'
            elif req.get('must_in_stock') and p.get('availability') not in ('有货','in_stock'): reason='库存无法确认（在售不等于实时有货）'
            elif req.get('spec_ml') and (p.get('actual_spec_value')!=req['spec_ml'] or p.get('actual_spec_unit','').lower()!='ml'): reason='规格不符'
            elif req.get('concentration') and req['concentration'].lower()!=p.get('concentration','').lower(): reason='浓度版本不符'
            elif any(x and x.lower() in (p.get('brand','')+' '+p.get('product_name','')).lower() for x in req.get('exclude',[])): reason='命中明确排除项'
            if not reason:reason=attribute_rejection(p,req.get('attribute_filters',[]))
            if reason: rejected.append({'product_id':p['product_id'],'reason':reason})
            else: good.append(p)
        return good,rejected
    def evidence(self, ids):
        # Match each quoted sentence to its version, rather than trusting broad metadata.
        evidence=[]
        for note in self.notes:
            requested=set(ids)&set(note['product_ids'])
            if not requested: continue
            quotes=[]; matched=set()
            for sentence in re.split(r'(?<=[。！？；;\n])',note['text']):
                found={p['product_id'] for p in matching_products(sentence,self.products)} & requested
                if found:
                    quotes.append(sentence.strip()); matched.update(found)
            if matched:
                evidence.append({**note,'product_ids':[i for i in ids if i in matched],'text':'\n'.join(quotes)})
        return evidence
