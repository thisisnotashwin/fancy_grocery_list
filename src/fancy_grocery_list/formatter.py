from __future__ import annotations
from collections import defaultdict
from fancy_grocery_list.models import ProcessedIngredient
from fancy_grocery_list.config import Config


def format_grocery_list(ingredients: list[ProcessedIngredient], config: Config) -> str:
    by_section: dict[str, list[ProcessedIngredient]] = defaultdict(list)
    for ingredient in ingredients:
        section = ingredient.section if ingredient.section in config.store_sections else "Other"
        by_section[section].append(ingredient)

    lines: list[str] = []
    for section in config.store_sections:
        if section not in by_section:
            continue
        lines.append(f"\n{section}")
        lines.append("-" * len(section))
        for ingredient in by_section[section]:
            lines.append(f"[ ] {ingredient.quantity} {ingredient.name}")

    return "\n".join(lines).strip()
