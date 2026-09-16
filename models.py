from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

# Load categories once at module level
CATEGORIES_FILE = Path(__file__).parent / "categories.txt"
VALID_CATEGORIES = set()
if CATEGORIES_FILE.exists():
    with open(CATEGORIES_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                VALID_CATEGORIES.add(line)

class Category(BaseModel):
    # A category from Google's Product Taxonomy
    # https://www.google.com/basepages/producttype/taxonomy.en-US.txt
    name: str

    @field_validator("name")
    @classmethod
    def validate_name_exists(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Category '{v}' is not a valid category in categories.txt")
        return v

class Price(BaseModel):
    price: float
    currency: str
    # If a product is on sale, this is the original price
    compare_at_price: float | None = None

class VariantOption(BaseModel):
    name: str
    value: str


class Variant(BaseModel):
    sku: str | None = None
    title: str | None = None
    options: list[VariantOption]
    price: Price | None = None
    available: bool | None = None
    image_urls: list[str] = []


# This is the final product schema that you need to output.
# You may add additional models as needed.
class Product(BaseModel):
    name: str
    price: Price
    description: str
    key_features: list[str]
    image_urls: list[str]
    video_url: str | None = None
    category: Category
    brand: str
    colors: list[str]
    variants: list[Variant]

class ImageCandidate(BaseModel):
    id: int
    url: str
    source: str
    context: str = ""


class PageBundle(BaseModel):
    source_url: str | None = None
    meta: dict[str, str]
    json_ld: list[dict]
    embedded_json: dict[str, Any]
    visible_text: str
    images: list[ImageCandidate]
    videos: list[str]


class ExtractedVariant(BaseModel):
    sku: str | None
    options: list[VariantOption]
    price: float | None
    compare_at_price: float | None
    available: bool | None
    image_ids: list[int]


class ExtractedColorway(BaseModel):
    color: str
    sku: str | None
    price: float | None
    compare_at_price: float | None
    available: bool | None
    image_ids: list[int]


class ExtractedProduct(BaseModel):
    name: str
    brand: str
    description: str
    key_features: list[str]
    price: float | None
    currency: str
    compare_at_price: float | None
    colors: list[str]
    gallery_image_ids: list[int]
    video_id: str | None
    variants: list[ExtractedVariant]
    linked_colorways: list[ExtractedColorway]
    category_hints: list[str]
    taxonomy_root: str


class CategoryChoice(BaseModel):
    reasoning: str
    category_id: int


class ExtractionResult(BaseModel):
    id: str
    source_file: str
    source_url: str | None = None
    model: str
    product: Product


class CatalogItem(BaseModel):
    id: str
    name: str
    brand: str
    price: Price
    image_url: str | None
    hover_image_url: str | None
    category: str
    color_count: int
    variant_count: int
