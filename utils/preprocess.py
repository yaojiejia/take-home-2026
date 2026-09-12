import json

from selectolax.parser import HTMLParser

from models import PageBundle
from utils.html import extract_embedded_json, extract_json_ld, extract_meta, extract_visible_text, tokenize
from utils.images import abbreviate_url, collect_images, collect_videos
from utils.json_prune import prune_blobs, prune_json_ld


def build_bundle(html: str, source_url: str | None = None) -> PageBundle:
    tree = HTMLParser(html)
    meta = extract_meta(tree)
    base_url = source_url or meta.get("og:url") or meta.get("canonical") or ""
    json_ld = extract_json_ld(tree)
    blobs = extract_embedded_json(tree)
    title_tokens = tokenize(meta.get("h1") or meta.get("og:title") or meta.get("title") or "")
    images = collect_images(tree, html, meta, json_ld, blobs, base_url)
    videos = collect_videos(tree, html, base_url)
    return PageBundle(
        source_url=base_url or None,
        meta=meta,
        json_ld=prune_json_ld(json_ld, title_tokens),
        embedded_json=prune_blobs(blobs, title_tokens),
        visible_text=extract_visible_text(tree),
        images=images,
        videos=videos,
    )


def render_bundle(bundle: PageBundle) -> str:
    compact = {"separators": (",", ":"), "ensure_ascii": False}
    sections = ["## PAGE METADATA\n" + "\n".join(f"{k}: {v}" for k, v in bundle.meta.items())]
    if bundle.json_ld:
        sections.append("## JSON-LD\n" + json.dumps(bundle.json_ld, **compact))
    if bundle.embedded_json:
        sections.append("## EMBEDDED PAGE DATA (pruned)\n" + json.dumps(bundle.embedded_json, **compact))
    sections.append("## VISIBLE TEXT\n" + bundle.visible_text)
    sections.append("## IMAGE CANDIDATES\n" + "\n".join(
        f"[{img.id}] {abbreviate_url(img.url)} | source={img.source}" + (f" | {img.context}" if img.context else "")
        for img in bundle.images
    ))
    videos = "\n".join(f"[{i}] {url}" for i, url in enumerate(bundle.videos)) or "(none)"
    sections.append("## VIDEO CANDIDATES\n" + videos)
    return "\n\n".join(sections)
