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

## System design

### Backend: from 5 products to 50 million

Every page in this system is handled on its own. Nothing about one page depends on
another, so the job is embarrassingly parallel: no shared state, no ordering, no
coordination between workers. Fifty million pages is fifty million queue items. The
shape at scale is a queue of URLs, a pool of workers, and a store for the results. The
two stages want different pools. Shrinking a page is CPU work, about 200ms, while
extraction is mostly waiting on a model, about 5 to 10 seconds. Running them separately
lets a few CPU workers feed many concurrent model calls. Today `main.py` runs 5 pages at
once, and at scale the ceiling is the model's rate limit, not the machines.

Cost is the main thing to plan around. Measured on the 22 pages here, with Gemini 2.5
Flash Lite:

| | Per page | Per million pages |
|---|---|---|
| Extraction call | $0.0035 | $3,500 |
| Classification call | $0.0007 | $700 |
| Total | $0.0042 | $4,200 |

A full pass over 50 million pages is about $210K. It is this cheap because the page is
cut from about 1MB of HTML to 70K characters before any model sees it. The next savings
come from not re-extracting: most pages do not change between crawls, so hash the shrunk
bundle, skip pages that match, and only re-check the price.

Prompt caching helps less than it sounds here, and it is worth saying why. Providers
discount input tokens that repeat a previous request's prefix, by half to 90 percent
depending on the provider. The extraction prompt is built for that: the instructions
come first and the page last, so the fixed part is the prefix. But the fixed part is
only about 1K tokens against 20K of page, so the saving on extraction is a few percent.
Classification is the opposite case. The taxonomy tree for a section is up to 8K tokens
and identical for every product in that section, so it is the prefix, and with a
provider that caches it the classification call drops to a fraction of its cost. In
testing, caching worked through OpenAI models and never registered through Gemini on
OpenRouter, which is one reason classification should move to a lookup rather than
depend on a provider's cache behaviour.

Three things here do not scale. Storage is the first. Today each run writes a JSON file
and the server loads every file into memory, which works for 23 products and fails at 23
thousand. A record is about 7KB, so 50 million products is roughly 350GB, and it splits
naturally by how often the data changes. Product records go in a database keyed by a
stable id, a hash of the canonical URL rather than the name slug used here, with variants
as a JSON column since their shape differs by product. Prices and stock go in an
append-only table with a timestamp, because they change daily while descriptions and
images rarely do, and keeping history lets the API answer "when did this change". Raw
HTML and the shrunk bundle go in object storage, so a page can be re-extracted after a
prompt or model change without a re-crawl, and every field can be traced to its source.
Catalog and agent queries run against a search index built from the product table, not
against the table itself.

The second is classification. Calling a model for every product becomes a cache or an
embedding lookup, with the model only for hard cases. The third is quality control.
Judging changes by eye becomes an evaluation set: a few hundred checked pages that every
prompt or model change must pass before it ships. Without it, a small drop in accuracy is
invisible until it is spread across millions of listings.

The biggest cost cut is a distilled model. The current pipeline is a good teacher, and
labelling 50K pages with it costs about $210. A small open model, 3B to 7B, fine-tuned on
those bundle-to-JSON pairs is a one-off job of a few GPU hours, and the training data
comes straight from the stored bundles. Served on our own GPUs, it should run at roughly
$0.001 per page, five to ten times cheaper than the API, with no rate limits and no vendor
dependence, and GPU batching raises throughput further because many pages share one
forward pass. These are estimates from throughput, not measured. The small model would
run on the crawl nodes themselves, so the shrunk page never leaves the machine that
fetched it. The price and size checks stay in place either way, since they are what catch
a smaller model's mistakes, and the evaluation set is what makes the swap safe.

### Frontend: an API for shopping agents

The catalog rail in this app is built only from taxonomy paths, and that is also how an
agent wants to browse. The data is already the right shape. The API would add four
things on top of it. Search with structured filters, not just text: category path, price
range, brand, colour, size, and stock, all of which we already extract. Variant
resolution: given a colour and a size, return the SKU, price, and availability, which is
the question an agent asks right before buying. Freshness: every price and stock value
carries a timestamp so an agent knows whether to trust it or recheck. And provenance:
where each field came from, so an agent can cite it and a developer can debug it.

For developers, three tools would matter most. Webhooks on price and stock changes, so
apps react instead of polling. A sandbox catalog with known data to build against. And
bulk export of the `Product` schema itself, since a clean, typed catalog with structured
variants is the product.
