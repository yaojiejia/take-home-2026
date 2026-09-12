import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from models import ExtractionResult, Price

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
DIST_DIR = ROOT / "frontend" / "dist"


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


def load_products() -> dict[str, ExtractionResult]:
    records: dict[str, ExtractionResult] = {}
    for path in sorted(OUTPUT_DIR.glob("*.json")):
        for item in json.loads(path.read_text()):
            result = ExtractionResult.model_validate(item)
            records[result.id] = result
    return records


def catalog_item(result: ExtractionResult) -> CatalogItem:
    product = result.product
    return CatalogItem(
        id=result.id,
        name=product.name,
        brand=product.brand,
        price=product.price,
        image_url=product.image_urls[0] if product.image_urls else None,
        hover_image_url=product.image_urls[1] if len(product.image_urls) > 1 else None,
        category=product.category.name,
        color_count=len(product.colors),
        variant_count=len(product.variants),
    )


app = FastAPI(title="Product catalog")
PRODUCTS = load_products()


@app.get("/api/products", response_model=list[CatalogItem])
def list_products() -> list[CatalogItem]:
    return [catalog_item(result) for result in PRODUCTS.values()]


@app.get("/api/products/{product_id}", response_model=ExtractionResult)
def get_product(product_id: str) -> ExtractionResult:
    result = PRODUCTS.get(product_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        candidate = DIST_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
