import json
import re

from selectolax.parser import HTMLParser

WINDOW_ASSIGN_RE = re.compile(r"window\.([A-Za-z_$][\w$]*)\s*=\s*(?=[\[{])")
RSC_PUSH_RE = re.compile(r"__next_f\.push\(\[\d+,\s*(\"(?:[^\"\\]|\\.)*\")\s*\]\)")
RSC_ROW_RE = re.compile(r"([0-9a-fA-F]+):")
RSC_TEXT_RE = re.compile(r"T([0-9a-fA-F]+),")
RSC_REF_RE = re.compile(r"^\$[0-9a-fA-F]+$")
MAX_RSC_REF_DEPTH = 8
RSC_SKIP_KEYS = {"classname", "class", "style", "src", "srcset", "sizes", "href", "id", "key", "rel", "as", "type", "loading", "decoding", "fetchpriority", "width", "height", "viewbox", "d", "fill", "stroke", "xmlns", "target", "role", "tabindex", "name", "value", "for", "action", "method", "dangerouslysetinnerhtml", "__html"}
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


# The last path segments of the canonical URL that look like ids (style codes, numeric ids,
# long slugs). They tell this product's data apart from its siblings' throughout the pipeline.
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


# Inline JSON: <script type=application/json>, __NEXT_DATA__, and window.X = {...} assignments.
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


# Next.js app-router pages ship the page as React Server Component rows inside
# self.__next_f.push calls, often with no text outside scripts at all. Rows are keyed by id
# and point at each other with "$id" strings; referenced rows are inlined once so a product
# object lands where it is used.
def extract_rsc(tree: HTMLParser) -> tuple[dict[str, object], str]:
    chunks: list[str] = []
    for node in tree.css("script"):
        text = node.text() or ""
        if "__next_f.push" not in text:
            continue
        for match in RSC_PUSH_RE.finditer(text):
            decoded = try_parse_json(match.group(1))
            if isinstance(decoded, str):
                chunks.append(decoded)
    if not chunks:
        return {}, ""
    rows = parse_rsc_payload("".join(chunks))
    lines: list[str] = []
    for _, item in rows:
        rsc_text(item, lines, inside_element=False)
    deduped: list[str] = []
    for line in lines:
        if line and line not in deduped[-5:]:
            deduped.append(line)
    data = inline_rsc_references({row_id: item for row_id, item in rows if isinstance(item, (dict, list))})
    return data, "\n".join(deduped)[:TEXT_BUDGET_CHARS]


def inline_rsc_references(rows: dict[str, object]) -> dict[str, object]:
    used: set[str] = set()

    def expand(node: object, depth: int) -> object:
        if isinstance(node, str) and RSC_REF_RE.match(node):
            row_id = node[1:]
            if row_id in rows and row_id not in used and depth < MAX_RSC_REF_DEPTH:
                used.add(row_id)
                return expand(rows[row_id], depth + 1)
            return node
        if isinstance(node, list):
            return [expand(child, depth) for child in node]
        if isinstance(node, dict):
            return {key: expand(child, depth) for key, child in node.items()}
        return node

    expanded = {}
    for row_id, item in rows.items():
        if row_id in used:
            continue
        used.add(row_id)
        expanded[f"r{row_id}"] = expand(item, 0)
    return expanded


def parse_rsc_payload(payload: str) -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = []
    pos = 0
    while pos < len(payload):
        row = RSC_ROW_RE.match(payload, pos)
        if row:
            row_id = row.group(1)
            pos = row.end()
            long_text = RSC_TEXT_RE.match(payload, pos)
            if long_text:
                start = long_text.end()
                length = int(long_text.group(1), 16)
                items.append((row_id, payload[start : start + length]))
                pos = start + length
                continue
            if pos < len(payload) and payload[pos] in "[{":
                try:
                    parsed, end = json.JSONDecoder().raw_decode(payload, pos)
                    items.append((row_id, parsed))
                    pos = end
                except (json.JSONDecodeError, ValueError):
                    pass
        newline = payload.find("\n", pos)
        pos = len(payload) if newline < 0 else newline + 1
    return items


CODE_HINT_RE = re.compile(r"function\s*\(|=>|\bvar\s|\bdocument\.|\bwindow\.|<[a-z]+[\s>]|\{\"")


# Rendered text is only what sits in an element's children. Client-component props carry
# nav trees and copy decks, which read as noise.
def rsc_text(node: object, out: list[str], inside_element: bool) -> None:
    if isinstance(node, str):
        if inside_element and len(node) > 1 and not node.startswith("$") and "://" not in node and not node.startswith("/") and not CODE_HINT_RE.search(node):
            out.append(clean_space(node))
    elif isinstance(node, list):
        if len(node) in (3, 4) and node[0] == "$" and isinstance(node[1], str):
            if node[1] in ("script", "style", "link", "meta", "noscript", "template"):
                return
            props = node[-1] if isinstance(node[-1], dict) else {}
            rsc_text(props.get("children"), out, inside_element=True)
            return
        for child in node:
            rsc_text(child, out, inside_element)
    elif isinstance(node, dict) and inside_element:
        for key, child in node.items():
            if key.lower() not in RSC_SKIP_KEYS:
                rsc_text(child, out, inside_element)


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
