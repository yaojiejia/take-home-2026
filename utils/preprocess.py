import json

from selectolax.parser import HTMLParser

from models import PageBundle
from utils.html import extract_embedded_json, extract_json_ld, extract_meta, extract_rsc, extract_visible_text, page_identifiers, tokenize
from utils.images import abbreviate_url, collect_images, collect_videos
from utils.json_prune import embedded_budget, prune_blobs, prune_json_ld

TOTAL_BUNDLE_CHARS = 72_000
MIN_DOM_TEXT_CHARS = 500


# Two stages: everything except embedded JSON first, then the JSON gets whatever budget is left.
def build_bundle(html: str, source_url: str | None = None) -> PageBundle:
    tree = HTMLParser(html)
    meta = extract_meta(tree)
    base_url = source_url or meta.get("og:url") or meta.get("canonical") or ""
    json_ld = extract_json_ld(tree)
    blobs = extract_embedded_json(tree)
    rsc_data, rsc_visible = extract_rsc(tree)
    if rsc_data:
        blobs.append(("__next_f", rsc_data))
    visible_text = extract_visible_text(tree)
    if len(visible_text) < MIN_DOM_TEXT_CHARS and rsc_visible:
        visible_text = rsc_visible
    title_tokens = tokenize(meta.get("h1") or meta.get("og:title") or meta.get("title") or "")
    identifiers = page_identifiers(meta)
    images = collect_images(tree, html, meta, json_ld, blobs, base_url)
    videos = collect_videos(tree, html, base_url)
    bundle = PageBundle(
        source_url=base_url or None,
        meta=meta,
        json_ld=prune_json_ld(json_ld, title_tokens, identifiers),
        embedded_json={},
        visible_text=visible_text,
        images=images,
        videos=videos,
    )
    budget = embedded_budget(len(render_bundle(bundle)), TOTAL_BUNDLE_CHARS)
    bundle.embedded_json = prune_blobs(blobs, title_tokens, identifiers, budget)
    return bundle


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
