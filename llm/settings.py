import os

DEFAULT_MODEL = os.environ.get("EXTRACTION_MODEL", "google/gemini-2.5-flash-lite")


MAX_OUTPUT_TOKENS = 60_000


def request_options(model: str) -> dict:
    options = {"max_output_tokens": MAX_OUTPUT_TOKENS}
    if model.startswith("openai/gpt-5"):
        return options | {"reasoning": {"effort": "minimal"}}
    return options | {"temperature": 0}
