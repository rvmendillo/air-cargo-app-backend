import os
import json
import re

from ..core.gemini import genai
from .prompt_builder import PromptBuilder
from .prompts import SYSTEM_PROMPT
from .embeddings import get_embedding
from .cache import search_cache, store_cache
from .intent_normalizer import normalize_intent


model = genai.GenerativeModel("gemini-2.5-flash")
builder = PromptBuilder(SYSTEM_PROMPT)


def extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        return {
            "status": "error",
            "message": "No JSON returned"
        }

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON",
            "raw_output": text
        }

def run_ai(user_text: str):
    intent = normalize_intent(user_text)

    normalized_input = f"{intent}:{user_text.strip().lower()}"
    embedding = get_embedding(normalized_input)

    cached = search_cache(embedding)

    if cached:
        # To validate if caching is working
        return {
            "cached": True,
            "data": cached
        }
        # return cached

    prompt = builder.build(user_text)

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.2
        }
    )

    result = extract_json(response.text)

    store_cache(embedding, result)

    # To validate if caching is working
    return {
        "cached": False,
        "data": result
    }

    # return result