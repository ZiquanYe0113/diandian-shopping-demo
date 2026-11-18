"""Readable no-result explanations and explicitly conditional catalog options."""
from copy import deepcopy

from .preferences import order_candidates
from .shopping_logic import price, spec


def _optional_warnings(product, matches):
    warnings = []
    for match in matches:
        if match['strict'] or match['status'] == 'supported':
            continue
        sources = match['conflict']
        message = (f'“{match["preference"]}”偏好存在冲突，需要你确认能否接受。'
                   if match['status'] == 'conflict'
                   else f'“{match["preference"]}”偏好资料不足，无法确认。')
        if match['status'] == 'unknown' and match['attribute'] == '香调' and product.get('scent_family'):
            sources = [{'type': 'catalog', 'product_id': product['product_id'],
                'field': 'scent_family', 'quote': product['scent_family'],
                'source_url': product.get('source_url', '')}]
            message += f'收录香调为“{product["scent_family"]}”，不能据此认定满足该偏好。'
        elif sources:
            message += '相关资料：' + '；'.join(f'“{s["quote"]}”' for s in sources[:2])
        warnings.append({'preference': match['preference'], 'status': match['status'],
            'message': message, 'sources': sources})
    return warnings


def no_result_response(catalog, requirements, rejected):
    """Return (answer, alternatives) without changing the persisted requirements.

    Alternatives are product dictionaries augmented with ``condition``, ``reason``
    and structured ``mismatches``. Only the upper budget limit may be relaxed;
    verified facts, scope, lower budget bound and all other hard rules still apply.
    """
    by_id = {p['product_id']: p for p in catalog.products}
    lines = ['当前收录资料中，暂时没有符合你已知条件的可推荐商品。']
    if any(r['reason'] == '已推荐，按要求换一批' for r in rejected):
        lines.append('已排除之前推荐过的款式，暂时没有新的匹配候选。')
    explained = set()
    for item in rejected:
        product = by_id.get(item['product_id'])
        if not product or product['product_id'] in explained:
            continue
        explained.add(product['product_id'])
        reason = item['reason']
        if reason == '超出实际规格预算':
            reason = (f'当前{spec(product)}参考价{price(product)}，'
                      f'超出你的预算上限¥{requirements["budget_max"]:g}')
        elif reason == '商品事实待核验，暂停推荐':
            reason = '商品版本或价格资料尚待核验，暂不能据此推荐'
        lines.append(f'{product["product_name"]}：{reason}。')
        if len(explained) >= 4:
            break

    alternatives = []
    ceiling = requirements.get('budget_max')
    if ceiling is not None:
        relaxed = deepcopy(requirements)
        relaxed['budget_max'] = None
        category = {'女士香水': '香水', 'perfume': '香水', 'headphones': '耳机'}.get(
            requirements.get('category'), requirements.get('category'))
        candidates = [p for p in catalog.search(requirements)
                      if p.get('category') == category
                      and p.get('verified_for_recommendation') is True
                      and p.get('reference_price_cny') is not None
                      and p['reference_price_cny'] > ceiling]
        candidates, _ = catalog.filter(candidates, relaxed)
        evidence = catalog.evidence([p['product_id'] for p in candidates])
        # The stable preference ranking preserves price order inside each match
        # group, so a cheaper conflict cannot displace a supported preference.
        candidates.sort(key=lambda p: p['reference_price_cny'])
        candidates, _, checks = order_candidates(candidates, relaxed, evidence, catalog.products)
        for product in candidates[:2]:
            amount = product['reference_price_cny']
            warnings = _optional_warnings(product, checks[product['product_id']]['matches'])
            reason = (f'当前{spec(product)}参考价{price(product)}，超出原预算上限¥{ceiling:g} '
                      f'（多¥{amount-ceiling:g}），不符合当前预算。')
            if warnings:
                reason += '\n' + '\n'.join(w['message'] for w in warnings)
            alternatives.append({**product,
                'condition': f'仅在你愿意将预算上限提高到至少¥{amount:g}时考虑'+('，并需确认能否接受下述偏好不足' if warnings else ''),
                'reason': reason,
                'optional_preference_warnings': warnings,
                'mismatches': [{'field': 'budget_max', 'required': ceiling,
                                'actual': amount, 'difference': amount-ceiling}],
            })
    if alternatives:
        lines.append('如果你愿意提高预算，可以看看下方的有条件替代选择；它们超出当前预算，原条件仍保留。')
    else:
        lines.append('暂时没有能确认满足其他硬性条件的替代款；可以继续补充或修改条件。')
    return '\n'.join(lines), alternatives
