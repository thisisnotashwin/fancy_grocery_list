from __future__ import annotations
import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-6"
    grocery_lists_dir: Path = Path.home() / ".grocery_lists"
    store_sections: list[str] = [
        "Produce",
        "Meat & Seafood",
        "Dairy & Eggs",
        "Bakery & Bread",
        "Pantry & Dry Goods",
        "Canned & Jarred Goods",
        "Frozen",
        "Spices & Seasonings",
        "Oils & Condiments",
        "Beverages",
        "Other",
    ]
    system_prompt: str = (
        "You are a kitchen assistant that processes recipe ingredients. "
        "Given raw ingredient strings from one or more recipes, you must:\n"
        "1. Parse each into: name, quantity (with unit), and store section\n"
        "2. Consolidate duplicates across recipes (e.g. '2 garlic cloves' + '3 cloves garlic' -> '5 cloves garlic')\n"
        "3. Normalize names: lowercase, singular form (e.g. 'garlic clove', 'all-purpose flour')\n"
        "4. Assign exactly one store section per ingredient from the provided list\n"
        "5. Express quantities in metric units, followed by the most practical US grocery store equivalent in brackets\n\n"
        "Quantity format rules:\n"
        "- Weights: use grams (g) or kilograms (kg), bracket the nearest common US grocery size "
        "(e.g. '450g [1 lb]', '115g [1/4 lb]')\n"
        "- Volumes: use milliliters (ml) or liters (L), bracket the nearest common US measure "
        "(e.g. '240ml [1 cup]', '15ml [1 tbsp]', '950ml [1 quart]')\n"
        "- Countable items (cloves, eggs, cans, sprigs): keep the count as-is, no metric needed "
        "(e.g. '4 cloves', '3 large eggs', '1 (28 oz) can')\n"
        "- 'to taste', 'as needed': leave unchanged\n"
        "- When combining across recipes, sum in metric first, then re-express the bracket\n\n"
        "Return ONLY a JSON array. Each object must have:\n"
        "  name: string\n"
        "  quantity: string (e.g. '450g [1 lb]', '240ml [1 cup]', '4 cloves', 'to taste')\n"
        "  section: string (must be one of the provided sections)\n"
        "  raw_sources: array of original strings that were merged\n\n"
        "Rules:\n"
        "- If quantity is unspecified, use 'as needed'\n"
        "- Do not split one ingredient into multiple items"
    )

    @field_validator("anthropic_api_key", mode="after")
    @classmethod
    def require_api_key(cls, v: str) -> str:
        env_val = os.environ.get("ANTHROPIC_API_KEY", v)
        if not env_val:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return env_val
