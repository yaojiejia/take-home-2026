import json
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser, Node

from models import ImageCandidate, PageBundle

SIGNAL_KEY_PARTS = (
    "price", "sku", "color", "colour", "size", "variant", "image", "name", "title",
    "description", "brand", "availab", "currency", "swatch", "gallery", "video",
    "feature", "material", "dimension", "weight", "option", "stock", "sale",
    "discount", "product", "category", "bullet", "spec", "attribute", "offer",
    "url", "src", "img", "media", "asset", "photo", "picture",
)
HEX_ID_RE = re.compile(r"(?<![a-z0-9])(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{12,})(?![a-z0-9])", re.I)
NOISE_KEY_PARTS = (
    "translation", "i18n", "analytics", "tracking", "experiment", "cookie",
    "consent", "navigation", "footer", "menu", "recommend", "related", "similar",
    "upsell", "crosssell", "carousel", "recently", "flags", "featureflag",
    "question", "review",
)
SIZE_SUFFIX_RE = re.compile(r"([-_@](\d{1,4}x\d{0,4}|\d{3,4}w?|\d+x|mini|thumb|thumbnail|small|medium|large|full|max|square|zoom|orig|original|xs|sm|md|lg|xl|xxl))+$", re.I)
META_IMAGE_KEYS = ("og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src")
LABEL_KEY_RE = re.compile(r"colou?r|name|title|sku|style|code|label|variant|size|alt|option", re.I)
CHROME_CLASS_RE = re.compile(r"nav|menu|footer|flyout|dropdown|breadcrumb|cookie|modal|popup|newsletter|signup", re.I)
LONG_TEXT_KEY_PARTS = ("description", "feature", "bullet", "spec", "detail", "note")
IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|webp|avif|jfif)(\?|$)", re.I)
IMAGE_URL_RE = re.compile(r"(?:https?:)?//[^\s\"'<>\\)]+?\.(?:jpe?g|png|webp|avif)(?:\?[^\s\"'<>\\)]*)?", re.I)
VIDEO_URL_RE = re.compile(r"(?:https?:)?//[^\s\"'<>\\)]+?\.(?:mp4|webm|m3u8|mov)(?:\?[^\s\"'<>\\)]*)?", re.I)
SRCSET_LIKE_RE = re.compile(r",\s*(https?:)?/")
WINDOW_ASSIGN_RE = re.compile(r"window\.([A-Za-z_$][\w$]*)\s*=\s*(?=[\[{])")
IMAGE_NOISE_WORDS = ("logo", "icon", "sprite", "flag", "badge", "payment", "placeholder", "pixel", "loading", "spinner", "avatar", "favicon")
RESIZE_QUERY_KEYS = {
    "w", "h", "width", "height", "q", "quality", "fit", "format", "fmt", "auto",
    "sw", "sh", "sm", "resize", "size", "dpr", "imwidth", "imheight", "scale",
    "crop", "wid", "hei", "qlt", "op_sharpen", "resmode", "impolicy", "imdensity",
}
MAX_LIST_ITEMS = 120
MAX_STRING_CHARS = 400
MAX_LONG_TEXT_CHARS = 4000
JSON_BUDGET_CHARS = 48_000
MIN_DROPPABLE_CHARS = 1_500
TEXT_BUDGET_CHARS = 12_000
MAX_IMAGE_CANDIDATES = 200
MAX_VIDEO_CANDIDATES = 10


def build_bundle(html: str, source_url: str | None = None) -> PageBundle:
    tree = HTMLParser(html)
    meta = extract_meta(tree)
    base_url = source_url or meta.get("og:url") or meta.get("canonical") or ""
    json_ld = extract_json_ld(tree)
    blobs = extract_embedded_json(tree, html)
    title_tokens = tokenize(meta.get("h1") or meta.get("og:title") or meta.get("title") or "")
    pruned = prune_blobs(blobs, title_tokens)
    images = collect_images(tree, html, meta, json_ld, blobs, base_url)
    videos = collect_videos(tree, html, base_url)
    text = extract_visible_text(tree)
    return PageBundle(
        source_url=base_url or None,
        meta=meta,
        json_ld=json_ld,
        embedded_json=pruned,
        visible_text=text,
        images=images,
        videos=videos,
    )


def extract_meta(tree: HTMLParser) -> dict[str, str]:
    meta: dict[str, str] = {}
    title = tree.css_first("title")
    if title:
        meta["title"] = clean_space(title.text())
    h1 = tree.css_first("h1")
    if h1:
        meta["h1"] = clean_space(h1.text())
    canonical = tree.css_first('link[rel="canonical"]')
    if canonical and canonical.attributes.get("href"):
        meta["canonical"] = canonical.attributes["href"]
    for node in tree.css("meta"):
        key = node.attributes.get("property") or node.attributes.get("name") or node.attributes.get("itemprop")
        value = node.attributes.get("content")
        if not key or not value:
            continue
        key = key.lower()
        if key.startswith(("og:", "twitter:", "product:")) or key in ("description", "keywords", "author"):
            meta.setdefault(key, clean_space(value)[:1000])
    return meta


def extract_json_ld(tree: HTMLParser) -> list[dict]:
    found: list[dict] = []
    for node in tree.css('script[type="application/ld+json"]'):
        parsed = try_parse_json(node.text() or "")
        if parsed is None:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if isinstance(item, dict) and "@graph" in item and isinstance(item["@graph"], list):
                found.extend(x for x in item["@graph"] if isinstance(x, dict))
            elif isinstance(item, dict):
                found.append(item)
    return found


def extract_embedded_json(tree: HTMLParser, html: str) -> list[tuple[str, object]]:
    blobs: list[tuple[str, object]] = []
    seen: set[int] = set()
    for node in tree.css("script"):
        if node.attributes.get("src"):
            continue
        script_type = (node.attributes.get("type") or "").lower()
        if script_type == "application/ld+json":
            continue
        text = (node.text() or "").strip()
        if len(text) < 200:
            continue
        label = node.attributes.get("id") or script_type or "inline"
        if text[0] in "{[":
            parsed = try_parse_json(text)
            if parsed is not None and id_key(parsed) not in seen:
                seen.add(id_key(parsed))
                blobs.append((label, parsed))
            continue
        for match in WINDOW_ASSIGN_RE.finditer(text):
            parsed = try_raw_decode(text, match.end())
            if parsed is not None and isinstance(parsed, (dict, list)) and len(json.dumps(parsed)) >= 200:
                blobs.append((match.group(1), parsed))
    return blobs


def prune_blobs(blobs: list[tuple[str, object]], title_tokens: set[str]) -> dict[str, object]:
    pruned: dict[str, object] = {}
    for label, blob in blobs:
        kept = prune_node(blob, "", title_tokens, 1)
        if kept is not None:
            pruned[unique_label(label, pruned)] = kept
    return shrink_to_budget(pruned, title_tokens)


def shrink_to_budget(root: dict, title_tokens: set[str]) -> dict:
    while True:
        candidates: list[tuple[float, int, list]] = []
        size, _ = measure(root, "", [], title_tokens, candidates)
        if size <= JSON_BUDGET_CHARS or not candidates:
            return root
        _, _, path = min(candidates)
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
        if isinstance(node, str) and title_tokens and len(tokenize(node) & title_tokens) >= max(2, len(title_tokens) // 2):
            score += 3
    if path and isinstance(node, (dict, list)) and size >= MIN_DROPPABLE_CHARS:
        out.append((score / size, -size, path))
    return size, score


def delete_path(node: object, path: list) -> None:
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]


def prune_node(node: object, key: str, title_tokens: set[str], threshold: int) -> object | None:
    if isinstance(node, dict):
        if is_noise_key(key):
            return None
        out: dict[str, object] = {}
        for child_key, child in node.items():
            if is_noise_key(child_key):
                continue
            kept = prune_node(child, child_key, title_tokens, threshold)
            if kept is not None:
                out[child_key] = kept
        if not out:
            return None
        if node_score(out, key, title_tokens) < threshold and not is_signal_key(key):
            return None
        return out
    if isinstance(node, list):
        items = [prune_node(child, key, title_tokens, threshold) for child in node[:MAX_LIST_ITEMS]]
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
    elif isinstance(node, str) and title_tokens:
        words = tokenize(node)
        if len(words & title_tokens) >= max(2, len(title_tokens) // 2):
            score += 3
    return score


def collect_images(
    tree: HTMLParser,
    html: str,
    meta: dict[str, str],
    json_ld: list[dict],
    blobs: list[tuple[str, object]],
    base_url: str,
) -> list[ImageCandidate]:
    raw: list[tuple[str, str, str]] = []
    for key in META_IMAGE_KEYS:
        if meta.get(key):
            raw.append((meta[key], "meta", key))
    for item in json_ld:
        for url in walk_strings(item.get("image")):
            raw.append((url, "json-ld", item.get("@type", "")))
        for variant in item.get("hasVariant", []) if isinstance(item.get("hasVariant"), list) else []:
            for url in walk_strings(variant.get("image") if isinstance(variant, dict) else None):
                raw.append((url, "json-ld", "variant"))
    for node in tree.css("img, source"):
        alt = clean_space(node.attributes.get("alt") or "")
        if is_tiny(node) or inside_site_chrome(node):
            continue
        for attr, value in node.attributes.items():
            if not value or attr not in ("src", "data-src", "srcset", "data-srcset", "data-original", "data-lazy", "data-zoom-image", "data-large", "data-image"):
                continue
            for url in parse_srcset(value) if "srcset" in attr or SRCSET_LIKE_RE.search(value) else [value]:
                raw.append((url, "img", alt))
    for label, blob in blobs:
        for url, context in walk_image_refs(blob, label):
            raw.append((url, "embedded", context))
    for match in IMAGE_URL_RE.findall(html):
        raw.append((match, "page", ""))
    return dedupe_and_rank_images(raw, base_url)


def dedupe_and_rank_images(raw: list[tuple[str, str, str]], base_url: str) -> list[ImageCandidate]:
    source_rank = {"meta": 0, "json-ld": 1, "img": 2, "embedded": 3, "page": 4}
    groups: dict[str, dict] = {}
    for url, source, context in raw:
        url = normalize_url(url, base_url)
        if not url or not is_plausible_image(url, context):
            continue
        key = image_group_key(url)
        group = groups.setdefault(key, {"urls": {}, "source": source, "context": context, "order": len(groups)})
        group["urls"][url] = group["urls"].get(url, 0) + 1
        if source_rank[source] < source_rank[group["source"]]:
            group["source"], group["context"] = source, context
        elif not group["context"] and context:
            group["context"] = context
    upgrades = learn_prefix_upgrades(groups)
    candidates = []
    for group in groups.values():
        urls = list(group["urls"]) + [upgraded for url in group["urls"] if (upgraded := apply_prefix_upgrade(url, upgrades))]
        best = pick_largest_variant(urls)
        candidates.append((source_rank[group["source"]], group["order"], best, group["source"], group["context"]))
    candidates.sort()
    return [
        ImageCandidate(id=i, url=url, source=source, context=context[:120])
        for i, (_, _, url, source, context) in enumerate(candidates[:MAX_IMAGE_CANDIDATES])
    ]


def split_prefix(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    segments = parts.path.split("/")
    tail_length = 2 if len(segments) > 2 and re.search(r"\d", segments[-2]) else 1
    return parts.netloc + "/".join(segments[:-tail_length]), "/".join(segments[-tail_length:])


def learn_prefix_upgrades(groups: dict[str, dict]) -> dict[str, str]:
    upgrades: dict[str, str] = {}
    for group in groups.values():
        urls = list(group["urls"])
        if len(urls) < 2:
            continue
        winner_prefix, _ = split_prefix(pick_largest_variant(urls))
        for url in urls:
            prefix, _ = split_prefix(url)
            if prefix == winner_prefix or size_hint(prefix) >= size_hint(winner_prefix):
                continue
            if prefix not in upgrades or size_hint(winner_prefix) > size_hint(upgrades[prefix]):
                upgrades[prefix] = winner_prefix
    return upgrades


def apply_prefix_upgrade(url: str, upgrades: dict[str, str]) -> str | None:
    prefix, tail = split_prefix(url)
    winner = upgrades.get(prefix)
    if winner is None:
        return None
    return f"{urlsplit(url).scheme}://{winner}/{tail}"


def image_group_key(url: str) -> str:
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    if not segments:
        return parts.netloc
    filename = SIZE_SUFFIX_RE.sub("", segments[-1].rsplit(".", 1)[0])
    parent = segments[-2] if len(segments) > 1 and re.search(r"\d", segments[-2]) else ""
    return "/".join(x for x in (parts.netloc, parent, filename) if x)


def pick_largest_variant(urls: list[str]) -> str:
    return max(urls, key=lambda url: (size_hint(size_bearing_path(urlsplit(url).path.lower())), -len(url)))


def size_hint(path: str) -> tuple[int, int, int]:
    path = path.lower()
    dims = re.findall(r"(?<![a-z0-9])(\d{2,4})x(\d{2,4})(?![a-z0-9])", path)
    area = max((int(w) * int(h) for w, h in dims), default=0)
    numbers = [int(n) for n in re.findall(r"(?<![a-z0-9])(\d{2,4})(?![a-z0-9])", HEX_ID_RE.sub("", path))]
    words = 0
    if re.search(r"(?<![a-z])(orig|original|max|zoom|full|large|xl|xxl|big|hires|hi-res)(?![a-z])", path):
        words = 1
    if re.search(r"(?<![a-z])(mini|thumb|thumbnail|small|square|tiny|icon|xs|sm)(?![a-z])", path):
        words = -1
    return (words, area, max(numbers, default=0))


def size_bearing_path(path: str) -> str:
    segments = path.split("/")
    filename = segments[-1].rsplit(".", 1)[0]
    stem = SIZE_SUFFIX_RE.sub("", filename)
    suffix = filename[len(stem):]
    return HEX_ID_RE.sub("", "/".join(segments[:-1]) + "/" + suffix)


def normalize_url(url: str, base_url: str) -> str | None:
    url = url.strip().replace("&amp;", "&")
    if SRCSET_LIKE_RE.search(url):
        url = parse_srcset(url)[0]
    if not url or url.startswith("data:") or re.search(r"\s", url):
        return None
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith("http"):
        if not base_url:
            return None
        url = urljoin(base_url, url)
    parts = urlsplit(url)
    if not parts.netloc:
        return None
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in RESIZE_QUERY_KEYS]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def is_plausible_image(url: str, context: str) -> bool:
    lowered = (url + " " + context).lower()
    if any(word in lowered for word in IMAGE_NOISE_WORDS):
        return False
    return bool(IMAGE_EXT_RE.search(url) or looks_like_image_path(url))


def looks_like_image_path(url: str) -> bool:
    lowered = url.lower()
    return ("/image" in lowered or "/img/" in lowered or "/images/" in lowered or "/media/" in lowered or "/files/" in lowered or "/products/" in lowered) and not lowered.endswith((".js", ".css", ".html", ".json", ".svg", ".gif"))


def inside_site_chrome(node: Node) -> bool:
    current = node.parent
    while current is not None and current.tag != "body":
        if current.tag in ("nav", "footer"):
            return True
        label = (current.attributes.get("id") or "") + " " + (current.attributes.get("class") or "") + " " + (current.attributes.get("role") or "")
        if CHROME_CLASS_RE.search(label):
            return True
        current = current.parent
    return False


def is_tiny(node: Node) -> bool:
    for attr in ("width", "height"):
        value = node.attributes.get(attr)
        if value and value.isdigit() and int(value) < 64:
            return True
    return False


def parse_srcset(value: str) -> list[str]:
    urls = []
    for part in value.split(","):
        piece = part.strip().split()
        if piece:
            urls.append(piece[0])
    return urls


def collect_videos(tree: HTMLParser, html: str, base_url: str) -> list[str]:
    found: list[str] = []
    for node in tree.css("video, video source"):
        for attr in ("src", "data-src"):
            if node.attributes.get(attr):
                found.append(node.attributes[attr])
    found.extend(VIDEO_URL_RE.findall(html))
    unique: list[str] = []
    for url in found:
        normalized = normalize_url(url, base_url)
        if normalized and normalized not in unique:
            unique.append(normalized)
    return unique[:MAX_VIDEO_CANDIDATES]


def extract_visible_text(tree: HTMLParser) -> str:
    body = tree.body
    if body is None:
        return ""
    for node in body.css("script, style, noscript, svg, template, iframe, nav, footer, [role=navigation], [aria-hidden=true]"):
        node.decompose()
    lines: list[str] = []
    for raw_line in body.text(separator="\n", deep=True).split("\n"):
        line = clean_space(raw_line)
        if line and line not in lines[-5:]:
            lines.append(line)
    return "\n".join(lines)[:TEXT_BUDGET_CHARS]


def walk_image_refs(node: object, path: str, labels: list[str] | None = None):
    labels = labels or []
    if isinstance(node, dict):
        own = describe_dict(node)
        next_labels = (labels + [own])[-2:] if own else labels
        for key, value in node.items():
            if not is_noise_key(key):
                yield from walk_image_refs(value, f"{path}.{key}", next_labels)
    elif isinstance(node, list):
        for value in node:
            yield from walk_image_refs(value, path + "[]", labels)
    elif isinstance(node, str) and (IMAGE_EXT_RE.search(node) or looks_like_image_path(node)):
        yield node, f"{shorten_path(path)} :: {' > '.join(labels)}"[:160]


def describe_dict(node: dict) -> str:
    def is_short(value: object) -> bool:
        return isinstance(value, str) and 1 < len(value) <= 60 and "://" not in value and not value.startswith("/")

    preferred = [v for k, v in node.items() if is_short(v) and LABEL_KEY_RE.search(k)]
    return " | ".join(preferred[:2])


def shorten_path(path: str) -> str:
    parts = [p for p in path.split(".") if p and p not in ("props", "pageProps", "data")]
    return ".".join(parts[-4:])


def walk_strings(node: object):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from walk_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_strings(value)


def try_parse_json(text: str) -> object | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def try_raw_decode(text: str, start: int) -> object | None:
    try:
        parsed, _ = json.JSONDecoder().raw_decode(text, start)
        return parsed
    except (json.JSONDecodeError, ValueError):
        return None


def id_key(parsed: object) -> int:
    return hash(json.dumps(parsed, sort_keys=True)[:5000])


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


def tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def clean_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def abbreviate_url(url: str, limit: int = 110) -> str:
    if len(url) <= limit:
        return url
    parts = urlsplit(url)
    tail = "/".join(parts.path.split("/")[-2:])
    return f"{parts.netloc}/…/{tail}"[:limit]


def render_bundle(bundle: PageBundle) -> str:
    sections = []
    sections.append("## PAGE METADATA\n" + "\n".join(f"{k}: {v}" for k, v in bundle.meta.items()))
    if bundle.json_ld:
        sections.append("## JSON-LD\n" + json.dumps(bundle.json_ld, separators=(",", ":"), ensure_ascii=False))
    if bundle.embedded_json:
        sections.append("## EMBEDDED PAGE DATA (pruned)\n" + json.dumps(bundle.embedded_json, separators=(",", ":"), ensure_ascii=False))
    sections.append("## VISIBLE TEXT\n" + bundle.visible_text)
    sections.append("## IMAGE CANDIDATES\n" + "\n".join(
        f"[{img.id}] {abbreviate_url(img.url)} | source={img.source}" + (f" | {img.context}" if img.context else "")
        for img in bundle.images
    ))
    sections.append("## VIDEO CANDIDATES\n" + ("\n".join(f"[{i}] {url}" for i, url in enumerate(bundle.videos)) or "(none)"))
    return "\n\n".join(sections)
