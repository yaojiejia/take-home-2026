import difflib
from collections import defaultdict
from pathlib import Path

import ai
from models import Category, CategoryChoice

TAXONOMY_FILE = Path(__file__).parent / "categories.txt"
SEPARATOR = " > "
MAX_OPTION_CHARS = 50_000

SYSTEM_PROMPT = """You classify retail products into Google's Product Taxonomy.
You are shown a product summary and a list of candidate categories. Reply with exactly one
category string copied verbatim from the candidate list. The retailer's own breadcrumb is only
a hint; it is never a valid answer unless it also appears in the candidate list. Choose the most
specific candidate that genuinely describes what the product is (not what it is used with, or
where it is sold). If no candidate is more specific than the current category, reply with the
current category."""


def load_taxonomy() -> tuple[list[str], dict[str, list[str]]]:
    paths: list[str] = []
    children: dict[str, list[str]] = defaultdict(list)
    for line in TAXONOMY_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        paths.append(line)
        parent = line.rsplit(SEPARATOR, 1)[0] if SEPARATOR in line else ""
        children[parent].append(line)
    return paths, children


PATHS, CHILDREN = load_taxonomy()
PATH_SET = set(PATHS)


async def classify(summary: str, model: str) -> Category:
    node = ""
    for _ in range(6):
        options, complete = candidate_options(node)
        if not options:
            break
        choice = await ai.responses(
            model,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(summary, node, options)},
            ],
            text_format=CategoryChoice,
        )
        picked = resolve(choice.category, options + ([node] if node else []))
        if picked is None:
            continue
        if picked == node:
            break
        node = picked
        if complete or not CHILDREN.get(node):
            break
    if not node:
        raise ValueError("Could not map the product to a taxonomy category")
    return Category(name=node)


def candidate_options(node: str) -> tuple[list[str], bool]:
    everything = descendants(node)
    if sum(len(p) + 1 for p in everything) <= MAX_OPTION_CHARS:
        return everything, True
    two_levels = []
    for child in CHILDREN.get(node, []):
        two_levels.append(child)
        two_levels.extend(CHILDREN.get(child, []))
    return two_levels, False


def descendants(node: str) -> list[str]:
    if not node:
        return PATHS
    prefix = node + SEPARATOR
    return [p for p in PATHS if p.startswith(prefix)]


def build_prompt(summary: str, node: str, options: list[str]) -> str:
    current = node or "(none yet)"
    return (
        f"PRODUCT:\n{summary}\n\n"
        f"CURRENT CATEGORY: {current}\n\n"
        f"CANDIDATE CATEGORIES:\n" + "\n".join(options)
    )


def resolve(answer: str, options: list[str]) -> str | None:
    answer = answer.strip().strip("\"'")
    if answer in options or answer in PATH_SET:
        return answer
    lowered = {o.lower(): o for o in options}
    if answer.lower() in lowered:
        return lowered[answer.lower()]
    prefixes = [o for o in options if answer.lower().startswith(o.lower() + SEPARATOR)]
    if prefixes:
        return max(prefixes, key=len)
    close = difflib.get_close_matches(answer, options, n=1, cutoff=0.8)
    if close:
        return close[0]
    leaf = answer.rsplit(SEPARATOR, 1)[-1].lower()
    by_leaf = [o for o in options if o.rsplit(SEPARATOR, 1)[-1].lower() == leaf]
    return by_leaf[0] if len(by_leaf) == 1 else None
