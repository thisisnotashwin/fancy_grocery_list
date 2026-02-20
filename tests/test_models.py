import json
from datetime import datetime, timezone
from fancy_grocery_list.models import (
    RawIngredient, ProcessedIngredient, RecipeData, GrocerySession
)


def test_raw_ingredient_roundtrip():
    ri = RawIngredient(text="2 large garlic cloves, minced", recipe_title="Pasta", recipe_url="https://example.com")
    assert RawIngredient.model_validate(ri.model_dump()) == ri


def test_processed_ingredient_defaults():
    pi = ProcessedIngredient(name="garlic", quantity="5 cloves", section="Produce", raw_sources=["2 cloves garlic", "3 cloves garlic"])
    assert pi.confirmed_have is None


def test_grocery_session_json_roundtrip(tmp_path):
    session = GrocerySession(
        id="test-session",
        created_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
        updated_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
    )
    path = tmp_path / "session.json"
    path.write_text(session.model_dump_json())
    loaded = GrocerySession.model_validate_json(path.read_text())
    assert loaded.id == "test-session"
    assert loaded.version == 1
    assert loaded.finalized is False


def test_recipe_data_stores_ingredients():
    recipe = RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour", "2 eggs"])
    assert len(recipe.raw_ingredients) == 2
