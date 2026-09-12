EXTRACTION_PROMPT_TEMPLATE = """You extract structured product data from a compacted representation of a single
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
  ISO 4217 currency code. The VISIBLE TEXT is what the shopper sees; when structured data and
  visible text disagree, the visible text wins. If a higher original price is shown crossed out or
  as a "was" price, put it in compare_at_price; otherwise compare_at_price is null. If no price
  appears anywhere in the page, set price to null instead of guessing.
- colors: every colour option the page offers for this product, using the page's own colour names.
  Include sibling colourways that are presented as options even if they link to their own pages.
  If the page offers no colour choice and names no colour, leave the list empty; never infer one.
- gallery_image_ids: the image gallery shown for the displayed configuration, in display order.
  The displayed configuration is the colour or style whose code appears in the page URL and
  metadata, or that the page data marks as selected. A gallery is normally a handful of images.
  Images of other colourways never belong here. Exclude logos, icons, promotional banners, swatch
  chips, size charts, and pictures of other products. Every candidate already points at its best
  available resolution.
- video_id: the numeric id of the primary product video from the VIDEO CANDIDATES list, if that
  list contains a video of this product; otherwise null.
- variants: every purchasable option combination a shopper can select on this page, one entry
  per combination. If the page offers colour and size choices together, list each colour and
  size pair the page data provides. If the page shows one colourway with a size list, list each
  size. Name each option the way the page does ("Color", "Size", "Length", "Fit", "Material",
  and so on) and use the page's own values. Every option value must appear somewhere in the page
  representation. When the page identifies a colour both by a code and by a name, the option
  value is the name; the code belongs in the SKU or title. If the data lists SKUs without size labels, do not invent sizes: use whatever
  dimension the data does provide, or emit one variant per SKU without a size option. Give each
  variant its SKU if present, its own price only if it differs from the product price,
  availability if known, and the ids of images that are specific to it. Do not invent
  combinations the page does not list.
- linked_colorways: colourways that are presented as options but link to their own product
  pages, meaning their sizes are not selectable here. One entry per colourway with its colour
  name, SKU or style code if present, price if shown, availability if known, and the ids of its
  images. Never list a linked colourway's sizes anywhere. Leave this empty when colour is a
  same-page option already covered by variants.
- category_hints: breadcrumb entries, product type labels, or similar taxonomy clues from the page,
  most general first.
- taxonomy_root: the one top-level section of Google's Product Taxonomy that the product itself
  belongs to (what it is, not what it is used with), copied exactly from this list:
  {taxonomy_roots}

Be faithful to the page. Never fabricate values that the page does not support."""

CATEGORY_PROMPT = """You classify retail products into Google's Product Taxonomy.
You are shown a product summary and an indented tree of candidate categories, each with a
numeric id. Indentation shows the parent; a child only applies when its parent applies too.
Reply with the id of the single most specific category that genuinely describes what the
product is (not what it is used with, or where it is sold). The retailer's own breadcrumb is
only a hint. If no deeper category fits, reply with the id of the current category."""


def extraction_prompt(taxonomy_roots: list[str]) -> str:
    return EXTRACTION_PROMPT_TEMPLATE.replace("{taxonomy_roots}", "; ".join(taxonomy_roots))
