EXTRACTION_PROMPT = """You extract structured product data from a compacted representation of a single
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

CATEGORY_PROMPT = """You classify retail products into Google's Product Taxonomy.
You are shown a product summary and a list of candidate categories. Reply with exactly one
category string copied verbatim from the candidate list. The retailer's own breadcrumb is only
a hint; it is never a valid answer unless it also appears in the candidate list. Choose the most
specific candidate that genuinely describes what the product is (not what it is used with, or
where it is sold). If no candidate is more specific than the current category, reply with the
current category."""
