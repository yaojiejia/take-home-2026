import os

DEFAULT_MODEL = os.environ.get("EXTRACTION_MODEL", "google/gemini-2.5-flash-lite")


def request_options(model: str) -> dict:
    if model.startswith("openai/gpt-5"):
        return {"reasoning": {"effort": "minimal"}}
    return {"temperature": 0}
