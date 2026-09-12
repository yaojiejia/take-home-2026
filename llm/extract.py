import re

from llm import ai
from llm.categorize import classify
from llm.prompts import EXTRACTION_PROMPT
from llm.settings import DEFAULT_MODEL, request_options
from models import (
    Category,
    ExtractedProduct,
    ImageCandidate,
    PageBundle,
    Price,
    Product,
    Variant,
    VariantOption,
)
from utils.preprocess import build_bundle, render_bundle



async def extract_product(html: str, source_url: str | None = None, model: str = DEFAULT_MODEL) -> tuple[Product, PageBundle]:
    bundle = build_bundle(html, source_url)
    rendered = render_bundle(bundle)
    page_numbers = numbers_in(rendered)
    messages = [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {"role": "user", "content": rendered},
    ]
    extracted = await ai.responses(model, messages, text_format=ExtractedProduct, **request_options(model))
    if not price_is_grounded(extracted.price, page_numbers):
        messages.append({"role": "user", "content": price_correction(extracted.price)})
        extracted = await ai.responses(model, messages, text_format=ExtractedProduct, **request_options(model))
    if not price_is_grounded(extracted.price, page_numbers):
        raise ValueError(f"No price grounded in the page (model answered {extracted.price})")
    category = await classify(category_summary(extracted), model)
    return assemble(extracted, bundle, category), bundle


def numbers_in(text: str) -> set[float]:
    found: set[float] = set()
    for match in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
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


def assemble(extracted: ExtractedProduct, bundle: PageBundle, category: Category) -> Product:
    by_id = {img.id: img for img in bundle.images}
    currency = extracted.currency.strip().upper()[:3] or "USD"
    compare_at = real_compare_at(extracted.price, extracted.compare_at_price)
    base_price = (extracted.price, compare_at)
    variants = [
        Variant(
            sku=clean_optional(v.sku),
            title=" / ".join(o.value for o in v.options) or None,
            options=[VariantOption(name=o.name.strip(), value=o.value.strip()) for o in v.options if o.value.strip()],
            price=variant_price(v.price, v.compare_at_price, currency, base_price),
            available=v.available,
            image_urls=resolve_images(v.image_ids, by_id),
        )
        for v in extracted.variants
    ]
    return Product(
        name=clean_text(extracted.name),
        price=Price(price=extracted.price, currency=currency, compare_at_price=compare_at),
        description=clean_text(extracted.description),
        key_features=[clean_text(f) for f in extracted.key_features if clean_text(f)],
        image_urls=resolve_images(extracted.image_ids, by_id),
        video_url=resolve_video(extracted.video_id, bundle.videos),
        category=category,
        brand=clean_text(extracted.brand),
        colors=[clean_text(c) for c in extracted.colors if clean_text(c)],
        variants=variants,
    )


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
