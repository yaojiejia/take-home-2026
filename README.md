# Channel3 Take-Home

Turns the raw HTML of a product page into a `Product` object, then shows the results in
a small catalog site. There is no site-specific code. The same pipeline runs on every
page. It has been tested on the 5 provided pages plus 19 more from other stores.

## Setup

Needs Python 3.12, [uv](https://docs.astral.sh/uv/), and Node 20 or newer.

```bash
uv sync
echo "OPEN_ROUTER_API_KEY=sk-or-..." > .env
```

## Run the backend

```bash
uv run python main.py                                     # data/ -> output/products.json
uv run python main.py --input data/extra --output output/products_extra.json
```

Options: `--model` (default `google/gemini-2.5-flash-lite`) and `--concurrency` (default 5).

Each run writes one JSON file with one record per page. A record holds the `Product`,
the source file, the source URL, and the model used. Cost is logged for every call.
The default model costs about half a cent per product.

If a page has no price in its HTML, or is not a product page, the run reports it as a
failure instead of guessing.

## Run the server and frontend

```bash
cd frontend && npm install && npm run build && cd ..
uv run uvicorn server.app:app --port 8000        # open http://localhost:8000
```

The server reads every JSON file in `output/`. When a file changes, it reloads. New
products show up without a restart.

For frontend work, run `npm run dev` inside `frontend/`. It starts on port 5173 and
proxies `/api` to the server.

API: `GET /api/products` returns the catalog list. `GET /api/products/{id}` returns one
full record.

## How it works

1. **Shrink the page.** The HTML is turned into a compact text bundle of about 72K
   characters: page metadata, JSON-LD, embedded JSON, visible text, and a numbered list
   of image and video candidates. Embedded JSON is pruned by how much product signal
   each part carries. Parts that mention the page's own product id are kept.
2. **Extract.** One model call returns the product, its variants, and the image ids for
   each. The model never sees image URLs. It picks ids, and each id maps to the largest
   version of that image found on the page.
3. **Check.** The price must appear in the page as a real price, or the call is retried
   once and then fails. Sizes must appear near their SKU. Placeholder options and colour
   codes are cleaned up without the model.
4. **Classify.** The extractor names the top-level taxonomy section. A second call sees
   that whole section as a numbered tree and answers with one number.

A variant is `{sku, title, options: [{name, value}], price, available, image_urls}`.
Sizes belong only to the colourway shown on the page. Other colourways are listed as
colour-only variants, since their sizes are not selectable there.

The page-shrinking step borrows ideas from [AXE](https://arxiv.org/abs/2602.01838)
(Zhang et al., 2026) and [HtmlRAG](https://arxiv.org/abs/2411.02959) (Tan et al., 2024).

## Data

`data/` has the five provided pages. `data/extra`, `data/pickleball`, and `data/more`
hold 19 more pages fetched with curl to test generalisation. Each folder has a README
with the URLs. Uniqlo fails on purpose: its price is not in the HTML.

## Known limits

- Results are not fully deterministic. Variant and image counts can differ a little
  between runs.
- Pages that load the price or options with JavaScript cannot be extracted from HTML.
- The 2021 taxonomy lacks some modern product types. The classifier picks the closest
  section.
