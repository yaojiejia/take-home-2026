import argparse
import asyncio
import json
import logging
import re
from pathlib import Path

from llm import ai
from llm.extract import extract_product
from llm.settings import DEFAULT_MODEL
from models import ExtractionResult

logger = logging.getLogger("ingest")


async def ingest(input_dir: Path, output_file: Path, model: str, concurrency: int) -> None:
    files = sorted(input_dir.glob("*.html"))
    semaphore = asyncio.Semaphore(concurrency)

    async def run(path: Path) -> ExtractionResult | None:
        async with semaphore:
            try:
                product, bundle = await extract_product(path.read_text(encoding="utf-8", errors="ignore"), model=model)
            except Exception:
                logger.exception("Failed to extract %s", path.name)
                return None
        logger.info("Extracted %s -> %s (%d images, %d variants)", path.name, product.name, len(product.image_urls), len(product.variants))
        return ExtractionResult(
            id=product_id(product.brand, product.name) or path.stem,
            source_file=path.name,
            source_url=bundle.source_url,
            model=model,
            product=product,
        )

    results = [r for r in await asyncio.gather(*(run(p) for p in files)) if r is not None]
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps([r.model_dump() for r in results], indent=2, ensure_ascii=False))
    totals = ai.usage_totals
    logger.info(
        "Wrote %d/%d products to %s | %d AI calls, %d input + %d output tokens, $%.4f total ($%.4f per product)",
        len(results), len(files), output_file, totals["calls"], totals["input_tokens"], totals["output_tokens"],
        totals["cost_usd"], totals["cost_usd"] / max(len(results), 1),
    )


def product_id(brand: str, name: str) -> str:
    label = name if name.lower().startswith(brand.lower()) else f"{brand} {name}"
    return re.sub(r"[^a-z0-9]+", "-", label.lower())[:80].strip("-")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract structured products from raw PDP HTML files.")
    parser.add_argument("--input", default="data", type=Path)
    parser.add_argument("--output", default="output/products.json", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--concurrency", default=5, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(ingest(args.input, args.output, args.model, args.concurrency))
