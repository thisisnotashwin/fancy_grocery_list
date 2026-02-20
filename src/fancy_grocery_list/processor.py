from __future__ import annotations
import json
import re
import anthropic
from fancy_grocery_list.models import RawIngredient, ProcessedIngredient
from fancy_grocery_list.config import Config


class ProcessorError(Exception):
    pass


def _extract_json(text: str) -> str:
    """Extract JSON array from text that may contain extra prose."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def process(raw_ingredients: list[RawIngredient], config: Config) -> list[ProcessedIngredient]:
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    sections_list = "\n".join(f"  - {s}" for s in config.store_sections)
    ingredient_lines = "\n".join(
        f"- {ri.text} (from: {ri.recipe_title})" for ri in raw_ingredients
    )
    user_content = (
        f"Store sections to use:\n{sections_list}\n\n"
        f"Ingredients to process:\n{ingredient_lines}"
    )

    response = client.messages.create(
        model=config.anthropic_model,
        max_tokens=4096,
        system=config.system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = response.content[0].text
    try:
        data = json.loads(_extract_json(raw_text))
    except (json.JSONDecodeError, AttributeError) as e:
        raise ProcessorError(
            f"Failed to parse LLM response as JSON: {e}\n\nRaw response:\n{raw_text}"
        ) from e

    try:
        return [ProcessedIngredient(**item) for item in data]
    except Exception as e:
        raise ProcessorError(f"LLM returned unexpected ingredient format: {e}") from e
