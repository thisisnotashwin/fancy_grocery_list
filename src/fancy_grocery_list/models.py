from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RawIngredient(BaseModel):
    text: str
    recipe_title: str
    recipe_url: str


class ProcessedIngredient(BaseModel):
    name: str
    quantity: str
    section: str
    raw_sources: list[str]
    confirmed_have: Optional[bool] = None


class RecipeData(BaseModel):
    title: str
    url: str
    raw_ingredients: list[str]
    scale: float = 1.0


class GrocerySession(BaseModel):
    version: int = 1
    id: str
    name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    recipes: list[RecipeData] = Field(default_factory=list)
    extra_items: list[RawIngredient] = Field(default_factory=list)
    processed_ingredients: list[ProcessedIngredient] = Field(default_factory=list)
    finalized: bool = False
    output_path: Optional[str] = None
