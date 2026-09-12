import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser, Node

from models import ImageCandidate
from utils.html import clean_space
from utils.json_prune import is_noise_key

IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|webp|avif|jfif)(\?|$)", re.I)
IMAGE_URL_RE = re.compile(r"(?:https?:)?//[^\s\"'<>\\)]+?\.(?:jpe?g|png|webp|avif)(?:\?[^\s\"'<>\\)]*)?", re.I)
VIDEO_URL_RE = re.compile(r"(?:https?:)?//[^\s\"'<>\\)]+?\.(?:mp4|webm|m3u8|mov)(?:\?[^\s\"'<>\\)]*)?", re.I)
SRCSET_LIKE_RE = re.compile(r",\s*(https?:)?/")
HEX_ID_RE = re.compile(r"(?<![a-z0-9])(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{12,})(?![a-z0-9])", re.I)
SIZE_SUFFIX_RE = re.compile(r"([-_@](\d{1,4}x\d{0,4}|\d{3,4}w?|\d+x|mini|thumb|thumbnail|small|medium|large|full|max|square|zoom|orig|original|xs|sm|md|lg|xl|xxl))+$", re.I)
SIZE_DIR_RE = re.compile(r"^(\d{2,4}x\d{2,4}|\d{2,4}|[wh]_?\d{2,4}|(thumb|thumbnail|small|medium|large|full|max|zoom|orig|original|mini|xs|sm|md|lg|xl|xxl)s?)$", re.I)
LARGE_WORDS_RE = re.compile(r"(?<![a-z])(orig|original|max|zoom|full|large|xl|xxl|big|hires|hi-res)(?![a-z])")
SMALL_WORDS_RE = re.compile(r"(?<![a-z])(mini|thumb|thumbnail|small|square|tiny|icon|xs|sm)(?![a-z])")
LABEL_KEY_RE = re.compile(r"colou?r|name|title|sku|style|code|label|variant|size|alt|option", re.I)
CHROME_TOKENS = {
    "nav", "navbar", "navigation", "subnav", "menu", "megamenu", "submenu", "footer",
    "flyout", "dropdown", "breadcrumb", "breadcrumbs", "cookie", "newsletter", "signup",
}
META_IMAGE_KEYS = ("og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src")
IMAGE_ATTRS = ("src", "data-src", "srcset", "data-srcset", "data-original", "data-lazy", "data-zoom-image", "data-large", "data-image")
URL_NOISE_TOKENS = {"logo", "logos", "icon", "icons", "sprite", "sprites", "flag", "flags", "badge", "badges", "payment", "placeholder", "pixel", "loading", "loader", "spinner", "avatar", "favicon"}
ALT_NOISE_TOKENS = {"logo", "icon", "sprite", "placeholder", "spinner", "favicon"}
IMAGE_PATH_HINTS = ("/image", "/img/", "/images/", "/media/", "/files/", "/products/")
NON_IMAGE_SUFFIXES = (".js", ".css", ".html", ".json", ".svg", ".gif")
RESIZE_QUERY_KEYS = {
    "w", "h", "width", "height", "q", "quality", "fit", "format", "fmt", "auto",
    "sw", "sh", "sm", "resize", "size", "dpr", "imwidth", "imheight", "scale",
    "crop", "wid", "hei", "qlt", "op_sharpen", "resmode", "impolicy", "imdensity",
}
SOURCE_RANK = {"meta": 0, "json-ld": 1, "img": 2, "embedded": 3, "page": 4}
MAX_IMAGE_CANDIDATES = 200
MAX_VIDEO_CANDIDATES = 10
MIN_IMAGE_PIXELS = 64


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
        variants = item.get("hasVariant") if isinstance(item.get("hasVariant"), list) else []
        for variant in variants:
            for url in walk_strings(variant.get("image") if isinstance(variant, dict) else None):
                raw.append((url, "json-ld", "variant"))
    for node in tree.css("img, source"):
        alt = clean_space(node.attributes.get("alt") or "")
        if is_tiny(node) or inside_site_chrome(node):
            continue
        for attr, value in node.attributes.items():
            if not value or attr not in IMAGE_ATTRS:
                continue
            urls = parse_srcset(value) if "srcset" in attr or SRCSET_LIKE_RE.search(value) else [value]
            raw.extend((url, "img", alt) for url in urls)
    for label, blob in blobs:
        raw.extend((url, "embedded", context) for url, context in walk_image_refs(blob, label))
    raw.extend((match, "page", "") for match in IMAGE_URL_RE.findall(html))
    return dedupe_and_rank(raw, base_url)


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


def dedupe_and_rank(raw: list[tuple[str, str, str]], base_url: str) -> list[ImageCandidate]:
    groups: dict[str, dict] = {}
    for url, source, context in raw:
        url = normalize_url(url, base_url)
        if not url or not is_plausible_image(url, context):
            continue
        key = group_key(url)
        group = groups.setdefault(key, {"urls": set(), "source": source, "context": context, "order": len(groups)})
        group["urls"].add(url)
        if SOURCE_RANK[source] < SOURCE_RANK[group["source"]]:
            group["source"], group["context"] = source, context
        elif not group["context"] and context:
            group["context"] = context
    upgrades = learn_prefix_upgrades(groups)
    ranked = []
    for group in groups.values():
        urls = list(group["urls"])
        urls += [upgraded for url in urls if (upgraded := apply_prefix_upgrade(url, upgrades))]
        ranked.append((SOURCE_RANK[group["source"]], group["order"], pick_largest(urls), group["source"], group["context"]))
    ranked.sort()
    return [
        ImageCandidate(id=i, url=url, source=source, context=context[:120])
        for i, (_, _, url, source, context) in enumerate(ranked[:MAX_IMAGE_CANDIDATES])
    ]


def group_key(url: str) -> str:
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    if not segments:
        return parts.netloc
    filename = SIZE_SUFFIX_RE.sub("", segments[-1].rsplit(".", 1)[0])
    parent = segments[-2] if len(segments) > 1 and not SIZE_DIR_RE.match(segments[-2]) else ""
    return "/".join(x for x in (parts.netloc, parent, filename) if x)


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
        winner, _ = split_prefix(pick_largest(urls))
        for url in urls:
            prefix, _ = split_prefix(url)
            if prefix == winner or size_hint(prefix) >= size_hint(winner):
                continue
            if prefix not in upgrades or size_hint(winner) > size_hint(upgrades[prefix]):
                upgrades[prefix] = winner
    return upgrades


def apply_prefix_upgrade(url: str, upgrades: dict[str, str]) -> str | None:
    prefix, tail = split_prefix(url)
    winner = upgrades.get(prefix)
    if winner is None:
        return None
    return f"{urlsplit(url).scheme}://{winner}/{tail}"


def pick_largest(urls: list[str]) -> str:
    return max(urls, key=lambda url: (size_hint(size_bearing_path(urlsplit(url).path)), -len(url)))


def size_hint(path: str) -> tuple[int, int, int]:
    path = path.lower()
    dims = re.findall(r"(?<![a-z0-9])(\d{2,4})x(\d{2,4})(?![a-z0-9])", path)
    area = max((int(w) * int(h) for w, h in dims), default=0)
    numbers = [int(n) for n in re.findall(r"(?<![a-z0-9])(\d{2,4})(?![a-z0-9])", HEX_ID_RE.sub("", path))]
    words = 1 if LARGE_WORDS_RE.search(path) else -1 if SMALL_WORDS_RE.search(path) else 0
    return (words, area, max(numbers, default=0))


def size_bearing_path(path: str) -> str:
    segments = path.split("/")
    filename = segments[-1].rsplit(".", 1)[0]
    stem = SIZE_SUFFIX_RE.sub("", filename)
    return HEX_ID_RE.sub("", "/".join(segments[:-1]) + "/" + filename[len(stem):])


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
    if URL_NOISE_TOKENS & tokens(urlsplit(url).path) or ALT_NOISE_TOKENS & tokens(context):
        return False
    return bool(IMAGE_EXT_RE.search(url) or looks_like_image_path(url))


def tokens(text: str) -> set[str]:
    return set(re.split(r"[^a-z0-9]+", text.lower()))


def looks_like_image_path(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in IMAGE_PATH_HINTS) and not lowered.endswith(NON_IMAGE_SUFFIXES)


def inside_site_chrome(node: Node) -> bool:
    current = node.parent
    while current is not None and current.tag != "body":
        if current.tag in ("nav", "footer"):
            return True
        label = " ".join(current.attributes.get(attr) or "" for attr in ("id", "class", "role"))
        if CHROME_TOKENS & set(re.split(r"[^a-z0-9]+", label.lower())):
            return True
        current = current.parent
    return False


def is_tiny(node: Node) -> bool:
    for attr in ("width", "height"):
        value = node.attributes.get(attr)
        if value and value.isdigit() and int(value) < MIN_IMAGE_PIXELS:
            return True
    return False


def parse_srcset(value: str) -> list[str]:
    urls = []
    for part in value.split(","):
        piece = part.strip().split()
        if piece:
            urls.append(piece[0])
    return urls


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


def abbreviate_url(url: str, limit: int = 110) -> str:
    if len(url) <= limit:
        return url
    parts = urlsplit(url)
    tail = "/".join(parts.path.split("/")[-2:])
    return f"{parts.netloc}/…/{tail}"[:limit]
