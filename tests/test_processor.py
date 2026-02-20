import json
import pytest
from unittest.mock import MagicMock, patch
from fancy_grocery_list.processor import process, ProcessorError
from fancy_grocery_list.models import RawIngredient, ProcessedIngredient
from fancy_grocery_list.config import Config


SAMPLE_RESPONSE = json.dumps([
    {
        "name": "garlic clove",
        "quantity": "5 cloves",
        "section": "Produce",
        "raw_sources": ["2 large garlic cloves, minced", "3 cloves garlic"]
    },
    {
        "name": "all-purpose flour",
        "quantity": "2 cups",
        "section": "Pantry & Dry Goods",
        "raw_sources": ["2 cups all-purpose flour"]
    }
])


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return Config()


@pytest.fixture
def raw_ingredients():
    return [
        RawIngredient(text="2 large garlic cloves, minced", recipe_title="Pasta", recipe_url="https://example.com/pasta"),
        RawIngredient(text="3 cloves garlic", recipe_title="Soup", recipe_url="https://example.com/soup"),
        RawIngredient(text="2 cups all-purpose flour", recipe_title="Pasta", recipe_url="https://example.com/pasta"),
    ]


def test_process_returns_processed_ingredients(config, raw_ingredients):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text=SAMPLE_RESPONSE)]

    with patch("fancy_grocery_list.processor.anthropic.Anthropic", return_value=mock_client):
        result = process(raw_ingredients, config)

    assert len(result) == 2
    assert all(isinstance(i, ProcessedIngredient) for i in result)


def test_process_consolidates_duplicates(config, raw_ingredients):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text=SAMPLE_RESPONSE)]

    with patch("fancy_grocery_list.processor.anthropic.Anthropic", return_value=mock_client):
        result = process(raw_ingredients, config)

    garlic = next(i for i in result if "garlic" in i.name)
    assert garlic.quantity == "5 cloves"
    assert len(garlic.raw_sources) == 2


def test_process_invalid_json_raises(config, raw_ingredients):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="not json at all")]

    with patch("fancy_grocery_list.processor.anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(ProcessorError, match="parse"):
            process(raw_ingredients, config)


def test_process_passes_sections_in_prompt(config, raw_ingredients):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text=SAMPLE_RESPONSE)]

    with patch("fancy_grocery_list.processor.anthropic.Anthropic", return_value=mock_client):
        process(raw_ingredients, config)

    call_kwargs = mock_client.messages.create.call_args
    user_content = call_kwargs[1]["messages"][0]["content"]
    assert "Produce" in user_content
