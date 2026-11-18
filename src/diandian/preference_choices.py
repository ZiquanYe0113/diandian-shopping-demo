"""Bounded choice recovery, not a second natural-language understanding model.

Every token must belong to a registered dimension and the entire answer must
match the shared edit grammar. Open-ended requests remain model-owned.
"""
import re

def same_typed_choice(constraint,edit,facts,category):
    """Match registered semantic aliases, without inferring free-text qualities."""
    dimension=' '.join(constraint['attribute'].casefold().split())
    token=' '.join(constraint['value'].casefold().split())
    for fact in facts:
        if fact['category']!=category or fact['choice_attribute']!=edit['attribute']:continue
        if dimension not in fact['dimensions'] and dimension!=fact['choice_attribute'].casefold():continue
        values=dict(fact['values'])
        if dimension in fact['scoped_dimensions']:values.update(fact['scoped_values'])
        if token not in values:continue
        if fact['type'] is bool:return True
        if values[token]==edit['value']:return True
    return False


def choice_dimensions(scent_terms, typed_facts):
    dimensions = [{'category': '香水', 'attribute': '香调',
                   'aliases': {alias: value for value, aliases in scent_terms.items() for alias in aliases}}]
    for fact in typed_facts:
        aliases = {alias: fact.get('canonical_value', value)
                   for alias, value in fact['values'].items() if value is not False}
        dimensions.append({'category': fact['category'],
                           'attribute': fact['choice_attribute'],
                           'aliases': aliases})
    return dimensions


def explicit_choice_edits(message, category, dimensions):
    """Return edits and replaced dimensions, or no result for incomplete syntax."""
    registry = {alias.casefold(): (d['attribute'], value)
                for d in dimensions if d['category'] == category
                for alias, value in d['aliases'].items()}
    if not registry or len(message) > 160:
        return [], set()
    text = message.strip().rstrip('。！!，,').strip()
    clauses = re.split(r'\s*(?:、|，|,|以及|和|并且)\s*', text)
    edits = []; replaced = set()
    for clause in clauses:
        if clause in ('其他保持','其他不变','其余不变'):
            continue
        match = re.fullmatch(
            r'(?:我)?\s*(?P<op>改成|改为|换成|取消|去掉|不要|避免|不喜欢|喜欢|偏好|想要|要)?\s*'
            r'(?P<value>.*?)\s*(?:吧|的)?', clause, re.IGNORECASE)
        if not match:
            return [], set()
        token = ' '.join(match['value'].casefold().split())
        if match['op'] in ('取消','去掉'):
            token=re.sub(r'(?:要求|条件|偏好|限制)$','',token).strip()
        if token not in registry:
            return [], set()
        attribute, value = registry[token]
        op = match['op']
        # An omitted operation after a negative/removal clause has ambiguous
        # scope; leave the entire answer to semantic interpretation.
        if op is None and any(e['polarity']=='avoid' or e['operation']=='remove' for e in edits):
            return [], set()
        if op in ('改成', '改为', '换成'):
            replaced.add(attribute)
        edits.append(dict(attribute=attribute, value=value,
                          polarity='avoid' if op in ('不要', '避免', '不喜欢') else 'prefer',
                          strength='soft', quote=message.strip(),
                          operation='remove' if op in ('取消', '去掉') else 'upsert'))
    return edits, replaced
