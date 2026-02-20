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
        "4. Assign exactly one store section per ingredient from the provided list\n\n"
        "Return ONLY a JSON array. Each object must have:\n"
        "  name: string\n"
        "  quantity: string (e.g. '5 cloves', '2 cups', 'to taste')\n"
        "  section: string (must be one of the provided sections)\n"
        "  raw_sources: array of original strings that were merged\n\n"
        "Rules:\n"
        "- Combine quantities using the same unit where possible\n"
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
