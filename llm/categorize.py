from collections import defaultdict
from pathlib import Path

from llm import ai
from llm.prompts import CATEGORY_PROMPT
from llm.settings import request_options
from models import Category, CategoryChoice

TAXONOMY_FILE = Path(__file__).resolve().parent.parent / "categories.txt"
SEPARATOR = " > "
# Every top-level section renders under this size, so classification is one call over the
# whole section as an indented, numbered tree. The earlier two-level walk was greedy: once it
# picked Athletics it could never reach Pickleball under Outdoor Games.
MAX_OPTION_CHARS = 33_000
MAX_STEPS = 6
MAX_REJECTED = 2


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
TOP_LEVEL = CHILDREN[""]


# The extractor names the top-level section; this picks within it. An out-of-range id gets
# one retry, then the deepest valid node so far is the answer.
async def classify(summary: str, root_hint: str, model: str) -> Category:
    node = resolve_root(root_hint)
    rejected: list[int] = []
    for _ in range(MAX_STEPS):
        options, complete = candidate_options(node)
        if len(options) <= 1:
            break
        choice = await ai.responses(
            model,
            [
                {"role": "system", "content": CATEGORY_PROMPT},
                {"role": "user", "content": build_prompt(summary, options, rejected)},
            ],
            text_format=CategoryChoice,
            **request_options(model),
        )
        if not 0 <= choice.category_id < len(options):
            rejected.append(choice.category_id)
            if len(rejected) >= MAX_REJECTED:
                break
            continue
        picked = options[choice.category_id]
        if picked == node:
            break
        node = picked
        rejected = []
        if complete or not CHILDREN.get(node):
            break
    if not node:
        raise ValueError(f"Could not map the product to a taxonomy category (answers: {rejected})")
    return Category(name=node)


def resolve_root(hint: str) -> str:
    wanted = hint.strip().lower()
    for top in TOP_LEVEL:
        if top.lower() == wanted:
            return top
    return ""


# Two-level fallback only if a section ever outgrows the cap.
def candidate_options(node: str) -> tuple[list[str], bool]:
    everything = ([node] if node else []) + descendants(node)
    if len(render_tree(everything)) <= MAX_OPTION_CHARS:
        return everything, True
    two_levels = [node] if node else []
    for child in CHILDREN.get(node, []):
        two_levels.append(child)
        two_levels.extend(CHILDREN.get(child, []))
    return two_levels, False


def descendants(node: str) -> list[str]:
    if not node:
        return PATHS
    prefix = node + SEPARATOR
    return [p for p in PATHS if p.startswith(prefix)]


def render_tree(options: list[str]) -> str:
    base_depth = options[0].count(SEPARATOR)
    lines = []
    for i, path in enumerate(options):
        depth = path.count(SEPARATOR) - base_depth
        lines.append(f"{'  ' * depth}[{i}] {path.rsplit(SEPARATOR, 1)[-1]}")
    return "\n".join(lines)


def build_prompt(summary: str, options: list[str], rejected: list[int]) -> str:
    warning = ""
    if rejected:
        warning = f"\n\nYour previous answer was not a valid id and was rejected: {rejected}\nReply with an id between 0 and {len(options) - 1}."
    return (
        f"CANDIDATE CATEGORIES (indented tree, [id] name; the top entry is the current category):\n"
        f"{render_tree(options)}\n\n"
        f"PRODUCT:\n{summary}" + warning
    )
