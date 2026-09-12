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
JSON_BUDGET_CHARS = 48_000
MIN_DROPPABLE_CHARS = 1_500


def prune_blobs(blobs: list[tuple[str, object]], title_tokens: set[str]) -> dict[str, object]:
    pruned: dict[str, object] = {}
    for label, blob in blobs:
        kept = prune_node(blob, "", title_tokens)
        if kept is not None:
            pruned[unique_label(label, pruned)] = kept
    return shrink_to_budget(pruned, title_tokens)


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


def shrink_to_budget(root: dict, title_tokens: set[str]) -> dict:
    while True:
        candidates: list[tuple[float, int, list]] = []
        size, _ = measure(root, "", [], title_tokens, candidates)
        if size <= JSON_BUDGET_CHARS or not candidates:
            return root
        chosen: list[list] = []
        for _, negative_size, path in sorted(candidates):
            if any(path[: len(kept)] == kept for kept in chosen):
                continue
            chosen.append(path)
            size += negative_size
            if size <= JSON_BUDGET_CHARS:
                break
        for path in sorted(chosen, key=lambda p: [str(k) for k in p], reverse=True):
            delete_path(root, path)


def measure(node: object, key: str, path: list, title_tokens: set[str], out: list) -> tuple[int, int]:
    score = 1 if is_signal_key(key) else 0
    if isinstance(node, dict):
        size = 2
        for child_key, child in node.items():
            child_size, child_score = measure(child, child_key, path + [child_key], title_tokens, out)
            size += child_size + len(child_key) + 4
            score += child_score
    elif isinstance(node, list):
        size = 2
        for index, child in enumerate(node):
            child_size, child_score = measure(child, key, path + [index], title_tokens, out)
            size += child_size + 1
            score += child_score
    else:
        size = len(json.dumps(node, ensure_ascii=False))
        if isinstance(node, str) and mentions_title(node, title_tokens):
            score += 3
    if path and isinstance(node, (dict, list)) and size >= MIN_DROPPABLE_CHARS:
        out.append((score / size, -size, path))
    return size, score


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
