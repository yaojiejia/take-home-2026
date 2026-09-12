import json

from utils.html import tokenize

SIGNAL_KEY_PARTS = (
    "price", "sku", "color", "colour", "size", "variant", "image", "name", "title",
    "description", "brand", "availab", "currency", "swatch", "gallery", "video",
    "feature", "material", "dimension", "weight", "option", "stock", "sale",
    "discount", "product", "category", "bullet", "spec", "attribute", "offer",
    "url", "src", "img", "media", "asset", "photo", "picture",
)
NOISE_KEY_PARTS = (
    "translation", "i18n", "analytics", "tracking", "experiment", "cookie",
    "consent", "navigation", "footer", "menu", "recommend", "related", "similar",
    "upsell", "crosssell", "carousel", "recently", "flags", "featureflag",
    "question", "review",
)
LONG_TEXT_KEY_PARTS = ("description", "feature", "bullet", "spec", "detail", "note")
MAX_LIST_ITEMS = 120
MAX_STRING_CHARS = 400
MAX_LONG_TEXT_CHARS = 4000
MAX_JSON_BUDGET_CHARS = 48_000
MIN_JSON_BUDGET_CHARS = 20_000
JSON_LD_BUDGET_CHARS = 30_000
MIN_DROPPABLE_CHARS = 1_500
MAX_SHRINK_PASSES = 60
OVERSHOOT_FACTOR = 1.5
MAX_IDENTIFIER_HOLDERS = 20


def prune_blobs(blobs: list[tuple[str, object]], title_tokens: set[str], identifiers: set[str], budget: int = MAX_JSON_BUDGET_CHARS) -> dict[str, object]:
    pruned: dict[str, object] = {}
    for label, blob in blobs:
        kept = prune_node(blob, "", title_tokens)
        if kept is not None:
            pruned[unique_label(label, pruned)] = kept
    return shrink_to_budget(pruned, title_tokens, identifiers, budget)


def embedded_budget(fixed_chars: int, total_chars: int) -> int:
    return max(MIN_JSON_BUDGET_CHARS, min(MAX_JSON_BUDGET_CHARS, total_chars - fixed_chars))


def prune_json_ld(items: list[dict], title_tokens: set[str], identifiers: set[str]) -> list[dict]:
    kept = prune_node(items, "json-ld", title_tokens) or []
    return shrink_to_budget({"json-ld": kept}, title_tokens, identifiers, JSON_LD_BUDGET_CHARS).get("json-ld", [])


def prune_node(node: object, key: str, title_tokens: set[str]) -> object | None:
    if isinstance(node, dict):
        if is_noise_key(key):
            return None
        out: dict[str, object] = {}
        for child_key, child in node.items():
            if is_noise_key(child_key):
                continue
            kept = prune_node(child, child_key, title_tokens)
            if kept is not None:
                out[child_key] = kept
        if not out:
            return None
        if node_score(out, key, title_tokens) < 1 and not is_signal_key(key):
            return None
        return out
    if isinstance(node, list):
        items = [prune_node(child, key, title_tokens) for child in node[:MAX_LIST_ITEMS]]
        items = [x for x in items if x is not None]
        return items or None
    if isinstance(node, str):
        if not node.strip() or node.startswith("data:"):
            return None
        limit = MAX_LONG_TEXT_CHARS if is_long_text_key(key) else MAX_STRING_CHARS
        return node if len(node) <= limit else node[:limit] + "…"
    if isinstance(node, bool) or node is None:
        return node if is_signal_key(key) else None
    return node


def node_score(node: object, key: str, title_tokens: set[str]) -> int:
    score = 1 if is_signal_key(key) else 0
    if isinstance(node, dict):
        for child_key, child in node.items():
            score += node_score(child, child_key, title_tokens)
    elif isinstance(node, list):
        for child in node:
            score += node_score(child, key, title_tokens)
    elif isinstance(node, str) and mentions_title(node, title_tokens):
        score += 3
    return score


def shrink_to_budget(root: dict, title_tokens: set[str], identifiers: set[str], budget: int) -> dict:
    for _ in range(MAX_SHRINK_PASSES):
        candidates: list[tuple[float, int, list, int]] = []
        marks: dict[int, tuple[set[str], set[str]]] = {}
        deepest: dict[int, int] = {}
        mark_identifiers(root, identifiers, marks)
        identifiers = rare_identifiers(identifiers, marks)
        size, _, _ = measure(root, "", [], title_tokens, candidates, marks, identifiers, deepest)
        excess = size - budget
        eligible = [c for c in candidates if trimmable(node_at(root, c[2]), c[3], deepest)]
        if excess <= 0 or not eligible:
            break
        lowest = min(c[3] for c in eligible)
        expendable = lowest < max(c[3] for c in candidates)
        tier = [c for c in eligible if c[3] == lowest]
        ordered = sorted(tier, key=lambda c: c[1]) if expendable else sorted(tier, key=lambda c: (c[0], -c[1]))
        chosen: list[tuple[list, int]] = []
        for _, negative_size, path, _ in ordered:
            subtree_size = -negative_size
            if overlaps(path, [c[0] for c in chosen]):
                continue
            if not expendable and subtree_size > excess * OVERSHOOT_FACTOR and not isinstance(node_at(root, path), list):
                continue
            chosen.append((path, min(subtree_size, excess)))
            excess -= min(subtree_size, excess)
            if excess <= 0:
                break
        if not chosen:
            chosen = [(max(tier, key=lambda c: c[1])[2], excess)]
        for path, needed in sorted(chosen, key=lambda c: deletion_order(c[0]), reverse=True):
            node = node_at(root, path)
            if isinstance(node, list):
                truncate_list(node, needed, lowest, deepest)
            elif expendable:
                summarize_dict(root, path)
            else:
                delete_path(root, path)
    return root


def trimmable(node: object, level: int, deepest: dict[int, int]) -> bool:
    if isinstance(node, list):
        return len(node) >= 2 and any(deepest.get(id(item), level) <= level for item in node)
    return deepest.get(id(node), level) <= level


def truncate_list(node: list, needed: int, level: int, deepest: dict[int, int]) -> None:
    order = sorted(range(len(node)), key=lambda i: (deepest.get(id(node[i]), level), -i))
    removed = 0
    remaining = len(node)
    for index in order:
        if remaining < 2 or removed >= needed or deepest.get(id(node[index]), level) > level:
            break
        item_size, _, _ = measure(node[index], "", [], set(), [], {}, set(), {})
        node[index] = None
        removed += item_size + 1
        remaining -= 1
    node[:] = [item for item in node if item is not None]


def summarize_dict(root: dict, path: list) -> None:
    node = node_at(root, path)
    nested = [key for key, value in node.items() if isinstance(value, (dict, list))]
    if not nested:
        delete_path(root, path)
        return
    for key in nested:
        del node[key]


def node_at(root: dict, path: list) -> object:
    node: object = root
    for key in path:
        node = node[key]
    return node


def deletion_order(path: list) -> list[tuple[int, object]]:
    return [(1, key) if isinstance(key, int) else (0, key) for key in path]


def overlaps(path: list, chosen: list[list]) -> bool:
    return any(path[: len(kept)] == kept or kept[: len(path)] == path for kept in chosen)


def mark_identifiers(node: object, identifiers: set[str], marks: dict[int, tuple[set[str], set[str]]]) -> set[str]:
    own: set[str] = set()
    found: set[str] = set()
    if isinstance(node, dict):
        text = " ".join(str(v).lower() for v in node.values() if isinstance(v, (str, int)))
        own = {identifier for identifier in identifiers if identifier in text}
        found |= own
        for child in node.values():
            found |= mark_identifiers(child, identifiers, marks)
    elif isinstance(node, list):
        for child in node:
            found |= mark_identifiers(child, identifiers, marks)
    if isinstance(node, (dict, list)):
        marks[id(node)] = (own, found)
    return found


def rare_identifiers(identifiers: set[str], marks: dict[int, tuple[set[str], set[str]]]) -> set[str]:
    holders = {identifier: sum(1 for own, _ in marks.values() if identifier in own) for identifier in identifiers}
    return {identifier for identifier, count in holders.items() if 0 < count <= MAX_IDENTIFIER_HOLDERS}


def sibling_protection(children: list, marks: dict[int, tuple[set[str], set[str]]], parent_protection: int, identifiers: set[str]) -> list[int]:
    containers = [c for c in children if isinstance(c, (dict, list))]
    if not containers or not identifiers:
        return [parent_protection] * len(children)
    subtree_sets = [marks.get(id(c), (set(), set()))[1] for c in containers]
    relevant = set(identifiers)
    if len(containers) >= 2:
        relevant = {
            identifier
            for identifier in relevant
            if 0 < sum(1 for found in subtree_sets if identifier in found) < len(containers)
        }
    if len(containers) < 2 and parent_protection > 0:
        return [parent_protection] * len(children)
    own_sets = [marks.get(id(c), (set(), set()))[0] for c in containers]
    promoted = any(own & relevant for own in own_sets)
    demote = promoted and parent_protection <= 0 and len(containers) >= 2
    levels = []
    for child in children:
        if not isinstance(child, (dict, list)):
            levels.append(parent_protection)
            continue
        own, found = marks.get(id(child), (set(), set()))
        if own & relevant:
            levels.append(parent_protection + 1)
        elif demote and not (found & relevant):
            levels.append(parent_protection - 1)
        else:
            levels.append(parent_protection)
    return levels


def measure(
    node: object,
    key: str,
    path: list,
    title_tokens: set[str],
    out: list,
    marks: dict[int, tuple[set[str], set[str]]],
    identifiers: set[str],
    deepest_map: dict[int, int],
    protection: int = 0,
) -> tuple[int, int, int]:
    score = 1 if is_signal_key(key) else 0
    deepest = protection
    if isinstance(node, dict):
        size = 2
        levels = sibling_protection(list(node.values()), marks, protection, identifiers)
        for (child_key, child), level in zip(node.items(), levels):
            child_size, child_score, child_deepest = measure(child, child_key, path + [child_key], title_tokens, out, marks, identifiers, deepest_map, level)
            size += child_size + len(child_key) + 4
            score += child_score
            deepest = max(deepest, child_deepest)
    elif isinstance(node, list):
        size = 2
        levels = sibling_protection(node, marks, protection, identifiers)
        for index, (child, level) in enumerate(zip(node, levels)):
            child_size, child_score, child_deepest = measure(child, key, path + [index], title_tokens, out, marks, identifiers, deepest_map, level)
            size += child_size + 1
            score += child_score
            deepest = max(deepest, child_deepest)
    else:
        size = len(json.dumps(node, ensure_ascii=False))
        if isinstance(node, str) and mentions_title(node, title_tokens):
            score += 3
    if isinstance(node, (dict, list)):
        deepest_map[id(node)] = deepest
        if path and size >= MIN_DROPPABLE_CHARS and (isinstance(node, dict) or len(node) >= 2):
            out.append((score / size, -size, path, protection))
    return size, score, deepest


def delete_path(node: object, path: list) -> None:
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]


def mentions_title(text: str, title_tokens: set[str]) -> bool:
    if not title_tokens:
        return False
    return len(tokenize(text) & title_tokens) >= max(2, len(title_tokens) // 2)


def unique_label(label: str, existing: dict) -> str:
    if label not in existing:
        return label
    suffix = 2
    while f"{label}_{suffix}" in existing:
        suffix += 1
    return f"{label}_{suffix}"


def is_signal_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SIGNAL_KEY_PARTS)


def is_noise_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in NOISE_KEY_PARTS)


def is_long_text_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in LONG_TEXT_KEY_PARTS)
