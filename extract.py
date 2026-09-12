import os
import re

import ai
from categorize import classify
from models import (
    ExtractedProduct,
    ImageCandidate,
    PageBundle,
    Price,
    Product,
    Variant,
    VariantOption,
)
from preprocess import build_bundle, render_bundle

DEFAULT_MODEL = os.environ.get("EXTRACTION_MODEL", "google/gemini-2.5-flash-lite")

SYSTEM_PROMPT = """You extract structured product data from a compacted representation of a single
retail product detail page. The representation contains page metadata, JSON-LD, pruned embedded
page data, the visible page text, and numbered lists of image and video candidates.

Extract only the one primary product that the page sells. Ignore recommended, related, recently
viewed, "complete the look", and cross-sell products entirely.

Field guidance:
- name: the product title exactly as the page's main heading shows it, including the brand if the
  heading includes it. Leave out the retailer's site name and slogans.
- brand: the manufacturer or label. Infer from the page if it is not stated explicitly.
- description: the product description in the page's own words, as plain text without HTML.
  Include every descriptive paragraph the page shows. Do not paraphrase, summarise, or embellish.
- key_features: concise bullet points covering materials, specifications, dimensions, care,
  what is included, and notable benefits. One fact per bullet, in the page's own wording.
- price and currency: the current selling price shown for the displayed configuration, and the
  ISO 4217 currency code. If a higher original price is shown crossed out or as a "was" price,
  put it in compare_at_price; otherwise compare_at_price is null.
- colors: every colour option the page offers for this product, using the page's own colour names.
  Include sibling colourways that are presented as options even if they link to their own pages.
  If the page offers no colour choice and names no colour, leave the list empty; never infer one.
- image_ids: the product gallery as displayed for the currently selected configuration, in
  display order. A gallery is normally a handful of images; if you are selecting dozens, you are
  including other configurations' images, which belong on their variants instead. Use the candidate
  context (colour names, style codes, JSON paths) to tell configurations apart. Exclude logos, icons,
  promotional banners, swatch chips, size charts, and pictures of other products. Every candidate
  already points at its best available resolution.
- video_id: the numeric id of the primary product video from the VIDEO CANDIDATES list, if that
  list contains a video of this product; otherwise null.
- variants: every purchasable configuration the page data actually lists. A variant is one
  discrete selection such as a colour, a size, or a colour and size combination. Give each variant
  the options that define it, naming each option the way the page does ("Color", "Size", "Length",
  "Fit", "Material", and so on) and using the page's own values. Only use SKU identifiers if
  present, its own price only if it differs from the product price, availability if known, and
  the ids of images specific to that variant. Do not invent combinations the page does not list.
- category_hints: breadcrumb entries, product type labels, or similar taxonomy clues from the page,
  most general first.

Be faithful to the page. Never fabricate values that the page does not support."""


async def extract_product(html: str, source_url: str | None = None, model: str = DEFAULT_MODEL) -> Product:
    bundle = build_bundle(html, source_url)
    extracted = await ai.responses(
        model,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": render_bundle(bundle)},
        ],
        text_format=ExtractedProduct,
    )
    category = await classify(category_summary(extracted), model)
    return assemble(extracted, bundle, category)


def category_summary(extracted: ExtractedProduct) -> str:
    return "\n".join(
        [
            f"Name: {extracted.name}",
            f"Brand: {extracted.brand}",
            f"Page category hints: {' > '.join(extracted.category_hints) or 'none'}",
            f"Description: {extracted.description[:400]}",
            f"Key features: {'; '.join(extracted.key_features[:6])}",
        ]
    )


def assemble(extracted: ExtractedProduct, bundle: PageBundle, category) -> Product:
    by_id = {img.id: img for img in bundle.images}
    currency = extracted.currency.strip().upper()[:3] or "USD"
    base_price = (extracted.price, extracted.compare_at_price)
    variants = [
        Variant(
            sku=clean_optional(v.sku),
            title=" / ".join(o.value for o in v.options) or None,
            options=[VariantOption(name=o.name.strip(), value=o.value.strip()) for o in v.options if o.value.strip()],
            price=Price(price=v.price, currency=currency, compare_at_price=v.compare_at_price) if v.price is not None and not same_price(v.price, v.compare_at_price, base_price) else None,
            available=v.available,
            image_urls=resolve_images(v.image_ids, by_id),
        )
        for v in extracted.variants
    ]
    return Product(
        name=clean_text(extracted.name),
        price=Price(price=extracted.price, currency=currency, compare_at_price=extracted.compare_at_price),
        description=clean_text(extracted.description),
        key_features=[clean_text(f) for f in extracted.key_features if clean_text(f)],
        image_urls=resolve_images(extracted.image_ids, by_id),
        video_url=resolve_video(extracted.video_id, bundle.videos),
        category=category,
        brand=clean_text(extracted.brand),
        colors=[clean_text(c) for c in extracted.colors if clean_text(c)],
        variants=variants,
    )


def same_price(price: float, compare_at: float | None, base: tuple[float, float | None]) -> bool:
    return price == base[0] and compare_at in (None, base[1])


def resolve_video(video_id: str | None, videos: list[str]) -> str | None:
    digits = re.sub(r"\D", "", video_id or "")
    if not digits or int(digits) >= len(videos):
        return None
    return videos[int(digits)]


def resolve_images(ids: list[int], by_id: dict[int, ImageCandidate]) -> list[str]:
    urls: list[str] = []
    for image_id in ids:
        candidate = by_id.get(image_id)
        if candidate and candidate.url not in urls:
            urls.append(candidate.url)
    return urls


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def clean_optional(text: str | None) -> str | None:
    cleaned = clean_text(text) if text else ""
    return cleaned or None
