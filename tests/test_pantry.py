import click
from click.testing import CliRunner
from fancy_grocery_list.pantry import run_pantry_check
from fancy_grocery_list.models import ProcessedIngredient


def _make_ingredient(name: str, confirmed_have: bool | None = None) -> ProcessedIngredient:
    return ProcessedIngredient(
        name=name, quantity="1 cup", section="Produce",
        raw_sources=[name], confirmed_have=confirmed_have
    )


def test_pantry_check_works_via_click_runner():
    """run_pantry_check must work through CliRunner stdin (requires click.prompt, not input())."""
    ingredients = [_make_ingredient("garlic")]

    @click.command()
    def cmd():
        result = run_pantry_check(ingredients)
        click.echo("confirmed" if result[0].confirmed_have else "not_confirmed")

    runner = CliRunner()
    result = runner.invoke(cmd, input="y\n")
    assert result.exit_code == 0
    assert "confirmed" in result.output


def test_confirms_have_marks_true(monkeypatch):
    monkeypatch.setattr("click.prompt", lambda *a, **kw: "y")
    ingredients = [_make_ingredient("garlic")]
    result = run_pantry_check(ingredients)
    assert result[0].confirmed_have is True


def test_confirms_not_have_marks_false(monkeypatch):
    monkeypatch.setattr("click.prompt", lambda *a, **kw: "n")
    ingredients = [_make_ingredient("garlic")]
    result = run_pantry_check(ingredients)
    assert result[0].confirmed_have is False


def test_already_confirmed_items_are_skipped(monkeypatch):
    call_count = {"n": 0}

    def mock_prompt(*args, **kwargs):
        call_count["n"] += 1
        return "y"

    monkeypatch.setattr("click.prompt", mock_prompt)
    ingredients = [
        _make_ingredient("garlic", confirmed_have=True),  # already confirmed
        _make_ingredient("flour"),                         # needs check
    ]
    result = run_pantry_check(ingredients)
    assert call_count["n"] == 1
    assert result[0].confirmed_have is True


def test_invalid_input_reprompts(monkeypatch):
    responses = iter(["maybe", "x", "n"])
    monkeypatch.setattr("click.prompt", lambda *a, **kw: next(responses))
    ingredients = [_make_ingredient("garlic")]
    result = run_pantry_check(ingredients)
    assert result[0].confirmed_have is False
