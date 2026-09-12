import difflib
from collections import defaultdict
from pathlib import Path

from llm import ai
from llm.prompts import CATEGORY_PROMPT
from models import Category, CategoryChoice

TAXONOMY_FILE = Path(__file__).resolve().parent.parent / "categories.txt"
SEPARATOR = " > "
MAX_OPTION_CHARS = 50_000
MAX_STEPS = 6
SAMPLING = {"temperature": 0}


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
    for _ in range(MAX_STEPS):
        options, complete = candidate_options(node)
        if not options:
            break
        choice = await ai.responses(
            model,
            [
                {"role": "system", "content": CATEGORY_PROMPT},
                {"role": "user", "content": build_prompt(summary, node, options)},
            ],
            text_format=CategoryChoice,
            **SAMPLING,
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
    return (
        f"PRODUCT:\n{summary}\n\n"
        f"CURRENT CATEGORY: {node or '(none yet)'}\n\n"
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
