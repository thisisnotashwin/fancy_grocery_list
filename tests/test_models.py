import json
from datetime import datetime, timezone
from fancy_grocery_list.models import (
    RawIngredient, ProcessedIngredient, RecipeData, GrocerySession, PantryItem
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


def test_grocery_session_extra_items_defaults_to_empty():
    session = GrocerySession(
        id="2026-02-20-test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    assert session.extra_items == []


def test_grocery_session_loads_without_extra_items_field():
    """Old sessions serialized without extra_items must still load."""
    raw = {
        "version": 1,
        "id": "2026-02-20-old",
        "created_at": "2026-02-20T00:00:00Z",
        "updated_at": "2026-02-20T00:00:00Z",
        "recipes": [],
        "processed_ingredients": [],
        "finalized": False,
        "output_path": None,
    }
    session = GrocerySession.model_validate(raw)
    assert session.extra_items == []


def test_recipe_data_scale_defaults_to_1():
    recipe = RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour"])
    assert recipe.scale == 1.0


def test_recipe_data_scale_can_be_set():
    recipe = RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour"], scale=2.5)
    assert recipe.scale == 2.5


def test_grocery_session_loads_recipe_without_scale_field():
    """Old sessions without scale on recipes must still deserialize."""
    raw = {
        "version": 1,
        "id": "2026-02-20-old",
        "created_at": "2026-02-20T00:00:00Z",
        "updated_at": "2026-02-20T00:00:00Z",
        "recipes": [{"title": "Pasta", "url": "https://example.com", "raw_ingredients": ["1 cup flour"]}],
        "processed_ingredients": [],
        "finalized": False,
        "output_path": None,
    }
    session = GrocerySession.model_validate(raw)
    assert session.recipes[0].scale == 1.0


def test_pantry_item_defaults():
    item = PantryItem(name="olive oil")
    assert item.name == "olive oil"
    assert item.quantity == ""


def test_pantry_item_with_quantity():
    item = PantryItem(name="olive oil", quantity="1 bottle")
    assert item.quantity == "1 bottle"
