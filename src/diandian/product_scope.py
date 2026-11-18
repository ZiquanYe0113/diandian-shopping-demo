"""Resolve explicit catalog identities without asking a model to invent scope IDs.

``None`` means no browse constraint; ``[]`` is an explicit identity with no
catalog match. Neither value changes a user's budget or the conversational route.
"""
import re
import unicodedata


def _compact(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value).casefold())


def _positive_occurrences(text, identity, word_starts=(), *, negative=False, brands=(), categories=()):
    for match in re.finditer(re.escape(identity), text):
        start, end = match.span()
        if start and start not in word_starts and identity[0].isascii() and identity[0].isalnum() and text[start-1].isascii() and text[start-1].isalpha():
            continue
        if end not in word_starts and identity[-1].isascii() and identity[-1].isalpha() and end < len(text) and text[end].isascii() and text[end].isalpha():
            continue
        # A model number is atomic: Pro 3 cannot match Pro 30 or Pro 3X.
        if identity[-1].isascii() and identity[-1].isdigit() and end < len(text) and text[end].isascii() and text[end].isalnum():
            continue
        clause = re.split(r'[，,。；;！？!?]|而是|但是|不过', text[:start])[-1]
        # Negation must govern this identity directly. A rejected feature such
        # as 不用降噪的 is not a rejected brand. Catalog brand prefixes may sit
        # between the negation and its model (不要苹果AirPods Pro 3).
        for brand in sorted(brands, key=len, reverse=True):
            if clause.endswith(brand):
                clause = clause[:-len(brand)]
                break
        before = re.search(r'(?:不要|不想要|不考虑|不喜欢|排除|除了|别推荐|不买|不选|不用|避开|拒绝)(?:推荐|购买|买|选|的)?$', clause)
        if clause.endswith('取消排除') and not re.search(r'(?:不要|别|不想)(?:再)?取消排除$', clause):
            before = None
        category_suffix = '|'.join(re.escape(c) for c in sorted(categories, key=len, reverse=True))
        after = re.match(r'(?:的?(?:' + (category_suffix or r'(?!)') + r'))?(?:不考虑|不买|不要|不选|不喜欢)(?:了)?(?:$|[，,。；;！？!?]|而是|但是|不过)', text[end:])
        is_negative = bool(before or after)
        if is_negative != negative:
            continue
        yield start, end



def _specific_mentions(mentions):
    """Suppress a broad identity only where a more specific identity names it."""
    specific = [m for m in mentions if not any(
        n[0] <= m[0] and n[1] >= m[1] and (n[1]-n[0] > m[1]-m[0] or (n[2]=='model' and m[2]!='model'))
        for n in mentions
    )]
    return [m for m in specific if not (m[2] == 'brand' and any(n[2] != 'brand' and set(m[3]) & set(n[3]) for n in specific))]


def _mentioned_ids(mentions, text):
    selected = set()
    for start, end, kind, ids in mentions:
        # An unconsumed numeric suffix is an unsupported model, never a family.
        if kind == 'brand' and re.match(r'[a-z][a-z-]*\d', text[end:]):
            continue
        if kind == 'family' and re.match(r'\d', text[end:]):
            continue
        selected.update(ids)
    return selected



def _restored_model_ids(mentions, text, brands):
    """Only a fresh request to view/select an exact model overrides exclusions."""
    restored = set()
    for start, end, kind, ids in mentions:
        if kind != 'model':
            continue
        prefix = re.split(r'[，,。；;！？!?]|而是|但是|不过', text[:start])[-1]
        for brand in sorted(brands, key=len, reverse=True):
            if prefix.endswith(brand):
                prefix = prefix[:-len(brand)]
                break
        intent = re.search(r'(?:当前想看|还是看看|还是看|重新考虑|重新看看|取消排除|恢复推荐|想看看|想看|看看|就选|选择|要买|想买)(?:一下)?$', prefix)
        if intent and not re.search(r'(?:不要|别|不想|不再)(?:再)?$', prefix[:intent.start()]):
            restored.update(ids)
    return restored


def resolve_browse_scope(message, products, previous=None, *, semantic_context=None):
    """Return authoritative requirements updates for a brand/family/model request.

    Brand names, aliases, model identities and Latin family prefixes are derived
    from catalog records. More specific identities replace their containing brand
    or family occurrence. Unrecognized numeric family variants resolve to an empty
    scope, so an unknown model never becomes a different catalog model.

    ``semantic_context`` optionally supplies a current-turn ``category`` and a
    ``scope_text`` copied verbatim from the user message. A supplied category is
    authoritative, including categories absent from the catalog. A valid quote
    narrows positive identity matches while negation remains attached to its
    original clause. Neither field supplies product IDs or weakens membership.
    Invalid or absent quotes preserve the backward-compatible literal resolver.
    ``exclusion_quotes`` optionally supplies authoritative current negative
    evidence: an empty list commits no new exclusion; a valid list retains only
    negative identities contained in its literal quotes. Absent/invalid evidence
    uses the legacy literal negation rules. Existing exclusions persist.
    """
    previous = previous or {}
    text = _compact(message)
    normalized = unicodedata.normalize('NFKC', message).casefold()
    word_starts = {len(_compact(normalized[:m.start()])) for m in re.finditer(r'\S+', normalized)}
    # Semantics belongs to the caller/model. Only categories actually in the
    # catalog are inferred locally; there is no list of unsupported nouns.
    semantic_context = semantic_context or {}
    category_names = {p.get('category') for p in products if p.get('category')}
    category_aliases = {_compact(c): c for c in category_names}
    for alias, category in [('perfume', '香水'), ('headphone', '耳机'), ('headphones', '耳机')]:
        if category in category_names:
            category_aliases[alias] = category
    explicit_category = semantic_context.get('category')
    if not explicit_category:
        category_hits = [(m.start(), category) for alias, category in category_aliases.items()
                         for m in re.finditer(re.escape(alias), text)]
        explicit_category = max(category_hits, default=(0, None))[1]
    target = semantic_context.get('scope_text')
    target = _compact(target) if isinstance(target, str) and target and target in message else ''
    # A semantic target narrows matching only with literal user evidence.
    target_ranges = [(m.start(), m.end()) for m in re.finditer(re.escape(target), text)] if target and target in text else []
    previous_scope = previous.get('browse_product_ids')
    previous_label = previous.get('browse_label', '')
    excluded = set(previous.get('excluded_product_ids', []))
    if explicit_category and previous.get('category') and explicit_category != previous['category']:
        previous_scope = None
        previous_label = ''
        excluded = set()

    identities = {}
    brands = set()
    labels = {}
    def add(identity, product, kind):
        label = identity.strip()
        identity = _compact(identity)
        labels.setdefault(identity, label)
        if len(identity) < 2:
            return
        item = identities.setdefault((identity, kind), [])
        if product['product_id'] not in item:
            item.append(product['product_id'])

    for product in products:
        brand = product.get('brand', '')
        # Catalog brand labels pair native and Latin names (e.g. Apple 苹果).
        aliases = re.findall(r'[\u3400-\u9fff]+|[A-Za-zÀ-ž][A-Za-zÀ-ž\s\'’&.-]*', brand)
        for alias in [brand, *aliases]:
            brands.add(_compact(alias))
            add(alias, product, 'brand')
        for alias in product.get('aliases', '').split(';') + [product.get('product_name', ''), product['product_id']]:
            add(alias, product, 'model')
            # An alias such as AirPods Pro 3 supplies both AirPods Pro and
            # AirPods families. No product names or SKU lists are hard-coded.
            latin = re.match(r'([A-Za-z]+(?:-[A-Za-z]+)*)(?:\s+([A-Za-z]+))?\s*\d', alias)
            if latin:
                words = [w for w in latin.groups() if w]
                for count in range(1, len(words)+1):
                    family = ''.join(words[:count])
                    if _compact(family) not in brands:
                        add(family, product, 'family')

    # A brand-qualified alias must have the same versions as its unqualified
    # model alias, even if only one catalog row happens to list that spelling.
    for (identity, kind), ids in list(identities.items()):
        if kind != 'model':
            continue
        for brand in sorted(brands, key=len, reverse=True):
            if identity.startswith(brand) and identity != brand:
                canonical = identity[len(brand):]
                for product_id in identities.get((canonical, 'model'), []):
                    if product_id not in ids:
                        ids.append(product_id)
                break

    if explicit_category and explicit_category not in category_names:
        return {'browse_product_ids': None, 'browse_label': '', 'category': explicit_category,
                'excluded_product_ids': []}

    by_id = {p['product_id']:p for p in products}
    mentions = []
    negative_mentions = []
    for (identity, kind), ids in identities.items():
        if explicit_category:
            ids = [i for i in ids if by_id[i].get('category') == explicit_category]
        if not ids:
            continue
        for start, end in _positive_occurrences(text, identity, word_starts, negative=True, brands=brands, categories=category_aliases):
            negative_mentions.append((start, end, kind, ids))
        for start, end in _positive_occurrences(text, identity, word_starts, brands=brands, categories=category_aliases):
            mentions.append((start, end, kind, ids))
    # Current semantic exclusion evidence distinguishes historical statements
    # from active rejection without teaching code temporal phrase vocabulary.
    # Invalid evidence conservatively preserves the literal interpretation.
    exclusion_quotes = semantic_context.get('exclusion_quotes')
    if isinstance(exclusion_quotes, list) and all(
        isinstance(quote, str) and quote and quote in message for quote in exclusion_quotes
    ):
        exclusion_ranges = [
            (match.start(), match.end())
            for quote in exclusion_quotes
            for match in re.finditer(re.escape(_compact(quote)), text)
        ]
        negative_mentions = [m for m in negative_mentions if any(
            start <= m[0] and m[1] <= end for start, end in exclusion_ranges
        )]
    # Without semantic/category evidence, a brand followed by arbitrary text
    # cannot establish a shopping category. A standalone brand still can.
    if not explicit_category and not target_ranges:
        mentions = [m for m in mentions if m[2] != 'brand' or
                    re.match(r'^(?:$|[，,。；;！？!?])', text[m[1]:])]
    if target_ranges:
        mentions = [m for m in mentions if any(a <= m[0] and m[1] <= b for a, b in target_ranges)]
    mentions = [m for m in mentions if not any(n[0] <= m[0] and n[1] >= m[1] for n in negative_mentions)]
    specific = _specific_mentions(mentions)
    if target_ranges:
        # A later semantic selection supersedes an earlier equally broad or
        # broader negative scope. A narrow exception before a broad selection
        # remains excluded; order and catalog set membership decide this.
        superseded = set()
        remaining_negatives = []
        for negative in _specific_mentions(negative_mentions):
            ids = set(negative[3])
            restored = set()
            for positive in specific:
                positive_ids = _mentioned_ids([positive], text)
                if negative[1] <= positive[0] and positive_ids and ids >= positive_ids:
                    restored.update(positive_ids)
            superseded.update(restored)
            remaining_negatives.append((*negative[:3], [i for i in negative[3] if i not in restored]))
        negative_mentions = remaining_negatives
        excluded.difference_update(superseded)
    excluded.difference_update(_restored_model_ids(specific, text, brands))
    negative_ids = _mentioned_ids(_specific_mentions(negative_mentions), text)
    excluded.update(negative_ids)
    # Preserve a partially remaining scope; clear a fully rejected prior brand.
    if previous_scope is not None and set(previous_scope) & negative_ids:
        previous_scope = [i for i in previous_scope if i not in excluded]
        if not previous_scope:
            previous_scope = None
            previous_label = ''
    exclusions = {'excluded_product_ids':[p['product_id'] for p in products if p['product_id'] in excluded]}
    if not specific:
        result = {'browse_product_ids':previous_scope, 'browse_label':previous_label, **exclusions}
        if explicit_category:
            result['category'] = explicit_category
        return result

    selected = _mentioned_ids(specific, text) - excluded
    categories = {by_id[i].get('category') for m in specific for i in m[3]}
    result = {'browse_product_ids':[p['product_id'] for p in products if p['product_id'] in selected],
              'browse_label':'、'.join(dict.fromkeys(labels.get(text[m[0]:m[1]], text[m[0]:m[1]]) for m in specific)), **exclusions}
    if explicit_category or len(categories) == 1:
        result['category'] = explicit_category or categories.pop()
    return result
