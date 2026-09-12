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
    extracted = await ai.responses(
        model,
        [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": render_bundle(bundle)},
        ],
        text_format=ExtractedProduct,
        **request_options(model),
    )
    category = await classify(category_summary(extracted), model)
    return assemble(extracted, bundle, category), bundle


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
    base_price = (extracted.price, extracted.compare_at_price)
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


def variant_price(price: float | None, compare_at: float | None, currency: str, base: tuple[float, float | None]) -> Price | None:
    if price is None or (price == base[0] and compare_at in (None, base[1])):
        return None
    return Price(price=price, currency=currency, compare_at_price=compare_at)


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
