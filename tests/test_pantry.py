from fancy_grocery_list.pantry import run_pantry_check
from fancy_grocery_list.models import ProcessedIngredient


def _make_ingredient(name: str, confirmed_have: bool | None = None) -> ProcessedIngredient:
    return ProcessedIngredient(
        name=name, quantity="1 cup", section="Produce",
        raw_sources=[name], confirmed_have=confirmed_have
    )


def test_confirms_have_marks_true(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    ingredients = [_make_ingredient("garlic")]
    result = run_pantry_check(ingredients)
    assert result[0].confirmed_have is True


def test_confirms_not_have_marks_false(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    ingredients = [_make_ingredient("garlic")]
    result = run_pantry_check(ingredients)
    assert result[0].confirmed_have is False


def test_already_confirmed_items_are_skipped(monkeypatch):
    call_count = {"n": 0}

    def mock_input(_):
        call_count["n"] += 1
        return "y"

    monkeypatch.setattr("builtins.input", mock_input)
    ingredients = [
        _make_ingredient("garlic", confirmed_have=True),  # already confirmed
        _make_ingredient("flour"),                         # needs check
    ]
    result = run_pantry_check(ingredients)
    assert call_count["n"] == 1
    assert result[0].confirmed_have is True


def test_invalid_input_reprompts(monkeypatch):
    responses = iter(["maybe", "x", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    ingredients = [_make_ingredient("garlic")]
    result = run_pantry_check(ingredients)
    assert result[0].confirmed_have is False
