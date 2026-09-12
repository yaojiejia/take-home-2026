import json
import re

from selectolax.parser import HTMLParser

WINDOW_ASSIGN_RE = re.compile(r"window\.([A-Za-z_$][\w$]*)\s*=\s*(?=[\[{])")
TEXT_BUDGET_CHARS = 12_000
MIN_BLOB_CHARS = 200


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


def page_identifiers(meta: dict[str, str]) -> set[str]:
    identifiers: set[str] = set()
    for key in ("og:url", "canonical"):
        path = meta.get(key, "").split("?")[0].split("#")[0]
        segments = [seg for seg in path.split("/")[3:] if looks_like_identifier(seg)]
        identifiers.update(seg.lower() for seg in segments[-2:])
    return identifiers


def looks_like_identifier(segment: str) -> bool:
    return len(segment) >= 3 and (any(ch.isdigit() for ch in segment) or ("-" in segment and len(segment) >= 8))


def extract_json_ld(tree: HTMLParser) -> list[dict]:
    found: list[dict] = []
    for node in tree.css('script[type="application/ld+json"]'):
        parsed = try_parse_json(node.text() or "")
        if parsed is None:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                found.extend(x for x in item["@graph"] if isinstance(x, dict))
            elif isinstance(item, dict):
                found.append(item)
    return found


def extract_embedded_json(tree: HTMLParser) -> list[tuple[str, object]]:
    blobs: list[tuple[str, object]] = []
    seen: set[int] = set()
    for node in tree.css("script"):
        if node.attributes.get("src"):
            continue
        script_type = (node.attributes.get("type") or "").lower()
        if script_type == "application/ld+json":
            continue
        text = (node.text() or "").strip()
        if len(text) < MIN_BLOB_CHARS:
            continue
        label = node.attributes.get("id") or script_type or "inline"
        if text[0] in "{[":
            parsed = try_parse_json(text)
            if parsed is not None and fingerprint(parsed) not in seen:
                seen.add(fingerprint(parsed))
                blobs.append((label, parsed))
            continue
        for match in WINDOW_ASSIGN_RE.finditer(text):
            parsed = try_raw_decode(text, match.end())
            if isinstance(parsed, (dict, list)) and len(json.dumps(parsed)) >= MIN_BLOB_CHARS:
                blobs.append((match.group(1), parsed))
    return blobs


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


def fingerprint(parsed: object) -> int:
    return hash(json.dumps(parsed, sort_keys=True)[:5000])


def tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def clean_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
