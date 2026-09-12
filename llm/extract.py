import logging
import re
from urllib.parse import urlparse

from pydantic import ValidationError

from llm import ai
from llm.categorize import TOP_LEVEL, classify
from llm.prompts import extraction_prompt
from llm.settings import DEFAULT_MODEL, request_options
from models import (
    Category,
    ExtractedColorway,
    ExtractedProduct,
    ExtractedVariant,
    ImageCandidate,
    PageBundle,
    Price,
    Product,
    Variant,
    VariantOption,
)
from utils.html import page_identifiers
from utils.preprocess import build_bundle, render_bundle

logger = logging.getLogger(__name__)
PARSE_ATTEMPTS = 2

EXTRACTION_PROMPT = extraction_prompt(TOP_LEVEL)


async def extract_product(html: str, source_url: str | None = None, model: str = DEFAULT_MODEL) -> tuple[Product, PageBundle]:
    bundle = build_bundle(html, source_url)
    if bundle.source_url and urlparse(bundle.source_url).path.strip("/") == "":
        raise ValueError(f"Not a product page: the canonical URL is the site root ({bundle.source_url})")
    rendered = render_bundle(bundle)
    page_numbers = price_like_numbers(rendered)
    messages = [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {"role": "user", "content": rendered},
    ]
    extracted = await parse_with_retry(model, messages)
    if not price_is_grounded(extracted.price, page_numbers):
        messages.append({"role": "user", "content": price_correction(extracted.price)})
        extracted = await parse_with_retry(model, messages)
    if not price_is_grounded(extracted.price, page_numbers):
        raise ValueError(f"No price grounded in the page (model answered {extracted.price})")
    drop_ungrounded_sizes(extracted, rendered.lower())
    category = await classify(category_summary(extracted), extracted.taxonomy_root, model)
    return assemble(extracted, bundle, category), bundle


async def parse_with_retry(model: str, messages: list) -> ExtractedProduct:
    for attempt in range(PARSE_ATTEMPTS):
        try:
            return await ai.responses(model, messages, text_format=ExtractedProduct, **request_options(model))
        except ValidationError as error:
            logger.warning("Model output did not parse (attempt %d): %s", attempt + 1, str(error).splitlines()[1][:120])
    raise ValueError("Model output did not parse as ExtractedProduct")


SIZE_OPTION_RE = re.compile(r"size|length|width|capacity|volume|weight", re.I)
SIZE_WINDOW = 4000


def drop_ungrounded_sizes(extracted: ExtractedProduct, page_text: str) -> None:
    seen: set[tuple] = set()
    kept: list[ExtractedVariant] = []
    for variant in extracted.variants:
        sku = (variant.sku or "").strip().lower()
        if sku and sku in page_text:
            variant.options = [o for o in variant.options if not SIZE_OPTION_RE.search(o.name) or near_sku(sku, o.value, page_text)]
        key = (sku, tuple((o.name.lower(), o.value.lower()) for o in variant.options))
        if key not in seen:
            seen.add(key)
            kept.append(variant)
    extracted.variants = kept


def near_sku(sku: str, value: str, page_text: str) -> bool:
    needle = re.compile(r"(?<![a-z0-9])" + re.escape(value.strip().lower()) + r"(?![a-z0-9])")
    start = page_text.find(sku)
    while start != -1:
        window = page_text[max(0, start - SIZE_WINDOW): start + len(sku) + SIZE_WINDOW]
        if needle.search(window):
            return True
        start = page_text.find(sku, start + 1)
    return False


PRICE_PATTERNS = (
    re.compile(r"[$£€¥₹]\s?(\d[\d,]*(?:\.\d+)?)"),
    re.compile(r"(\d[\d,]*(?:\.\d+)?)\s?(?:USD|GBP|EUR|CAD|AUD|JPY|INR|CHF|SEK|NOK|DKK)\b"),
    re.compile(r"\"[^\"]*(?:price|amount|cost)[^\"]*\"\s*:\s*\"?(\d[\d,]*(?:\.\d+)?)", re.I),
)


def price_like_numbers(text: str) -> set[float]:
    found: set[float] = set()
    for pattern in PRICE_PATTERNS:
        for match in pattern.findall(text):
            try:
                found.add(float(match.replace(",", "")))
            except ValueError:
                continue
    return found


def price_is_grounded(price: float | None, page_numbers: set[float]) -> bool:
    if price is None:
        return False
    return any(abs(price - n) < 0.005 for n in page_numbers) or round(price * 100) in page_numbers


def price_correction(price: float | None) -> str:
    return (
        f"The price you returned ({price}) does not appear anywhere in the page representation. "
        "Re-extract everything, and set price only to a number that appears verbatim in the page, "
        "preferring the VISIBLE TEXT section. If no price is present at all, set price to null."
    )


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


def relabel_colour_axis(variants: list[ExtractedVariant], colors: list[str]) -> None:
    palette = {clean_text(c).lower() for c in colors if clean_text(c)}
    values: dict[str, set[str]] = {}
    for v in variants:
        for o in v.options:
            values.setdefault(o.name.strip(), set()).add(clean_text(o.value).lower())
    if not palette or any(name.lower() in ("color", "colour") for name in values):
        return
    colour_axes = [name for name, seen in values.items() if seen and seen <= palette]
    if len(colour_axes) != 1:
        return
    for v in variants:
        for o in v.options:
            if o.name.strip() == colour_axes[0]:
                o.name = "Color"


def assemble(extracted: ExtractedProduct, bundle: PageBundle, category: Category) -> Product:
    by_id = {img.id: img for img in bundle.images}
    currency = extracted.currency.strip().upper()[:3] or "USD"
    compare_at = real_compare_at(extracted.price, extracted.compare_at_price)
    base_price = (extracted.price, compare_at)
    on_page, linked = split_by_page_identifier(extracted, page_identifiers(bundle.meta))
    relabel_colour_axis(on_page, extracted.colors)
    variants = [
        Variant(
            sku=clean_optional(v.sku),
            title=" / ".join(o.value for o in v.options) or None,
            options=[VariantOption(name=o.name.strip(), value=o.value.strip()) for o in v.options if o.value.strip()],
            price=variant_price(v.price, v.compare_at_price, currency, base_price),
            available=v.available,
            image_urls=resolve_images(v.image_ids, by_id),
        )
        for v in on_page
    ]
    covered = {clean_text(o.value).lower() for v in on_page for o in v.options if o.name.lower() in ("color", "colour")}
    for c in linked:
        color = clean_text(c.color)
        if not color or color.lower() in covered:
            continue
        covered.add(color.lower())
        variants.append(
            Variant(
                sku=clean_optional(c.sku),
                title=color,
                options=[VariantOption(name="Color", value=color)],
                price=variant_price(c.price, c.compare_at_price, currency, base_price),
                available=c.available,
                image_urls=resolve_images(c.image_ids, by_id),
            )
        )
    return Product(
        name=clean_text(extracted.name),
        price=Price(price=extracted.price, currency=currency, compare_at_price=compare_at),
        description=clean_text(extracted.description),
        key_features=[clean_text(f) for f in extracted.key_features if clean_text(f)],
        image_urls=resolve_images(extracted.gallery_image_ids, by_id),
        video_url=resolve_video(extracted.video_id, bundle.videos),
        category=category,
        brand=clean_text(extracted.brand),
        colors=[clean_text(c) for c in extracted.colors if clean_text(c)],
        variants=variants,
    )


def split_by_page_identifier(extracted: ExtractedProduct, identifiers: set[str]) -> tuple[list[ExtractedVariant], list[ExtractedColorway]]:
    def pinned(variant: ExtractedVariant) -> bool:
        return any(identifier in (variant.sku or "").lower() for identifier in identifiers)

    with_sku = [v for v in extracted.variants if v.sku]
    if not identifiers or not any(pinned(v) for v in with_sku) or all(pinned(v) for v in with_sku):
        return extracted.variants, extracted.linked_colorways
    on_page = [v for v in extracted.variants if not v.sku or pinned(v)]
    collapsed: dict[str, ExtractedColorway] = {}
    for v in extracted.variants:
        if v.sku and not pinned(v):
            color = next((o.value for o in v.options if o.name.lower() in ("color", "colour")), v.sku)
            entry = collapsed.setdefault(color, ExtractedColorway(color=color, sku=v.sku, price=v.price, compare_at_price=v.compare_at_price, available=None, image_ids=[]))
            entry.image_ids = entry.image_ids or v.image_ids
    named = {(c.sku or "").lower() for c in extracted.linked_colorways if c.sku}
    extra = [c for c in collapsed.values() if (c.sku or "").lower() not in named]
    return on_page, extracted.linked_colorways + extra


def variant_price(price: float | None, compare_at: float | None, currency: str, base: tuple[float, float | None]) -> Price | None:
    if price is None:
        return None
    compare_at = real_compare_at(price, compare_at)
    if price == base[0] and compare_at in (None, base[1]):
        return None
    return Price(price=price, currency=currency, compare_at_price=compare_at)


def real_compare_at(price: float, compare_at: float | None) -> float | None:
    return compare_at if compare_at is not None and compare_at > price else None


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
