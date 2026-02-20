import pytest
from fancy_grocery_list.formatter import format_grocery_list
from fancy_grocery_list.models import ProcessedIngredient
from fancy_grocery_list.config import Config


def _make_ingredient(name: str, quantity: str, section: str, confirmed_have: bool = False) -> ProcessedIngredient:
    return ProcessedIngredient(
        name=name, quantity=quantity, section=section,
        raw_sources=[name], confirmed_have=confirmed_have
    )


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    return Config()


def test_format_groups_by_section(config):
    ingredients = [
        _make_ingredient("garlic", "5 cloves", "Produce"),
        _make_ingredient("all-purpose flour", "2 cups", "Pantry & Dry Goods"),
        _make_ingredient("spinach", "1 bag", "Produce"),
    ]
    output = format_grocery_list(ingredients, config)
    produce_pos = output.index("Produce")
    pantry_pos = output.index("Pantry & Dry Goods")
    assert produce_pos < output.index("garlic")
    assert produce_pos < output.index("spinach")
    assert pantry_pos < output.index("flour")


def test_format_uses_checkbox_style(config):
    ingredients = [_make_ingredient("garlic", "5 cloves", "Produce")]
    output = format_grocery_list(ingredients, config)
    assert "[ ] 5 cloves garlic" in output


def test_format_respects_section_order(config):
    ingredients = [
        _make_ingredient("chicken breast", "1 lb", "Meat & Seafood"),
        _make_ingredient("garlic", "5 cloves", "Produce"),
    ]
    output = format_grocery_list(ingredients, config)
    # Produce comes before Meat & Seafood in config.store_sections
    assert output.index("Produce") < output.index("Meat & Seafood")


def test_format_skips_empty_sections(config):
    ingredients = [_make_ingredient("garlic", "5 cloves", "Produce")]
    output = format_grocery_list(ingredients, config)
    assert "Dairy & Eggs" not in output
