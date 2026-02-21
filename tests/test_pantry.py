import json
from pathlib import Path
import click
from click.testing import CliRunner
from fancy_grocery_list.pantry import run_pantry_check, PantryManager
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


def test_pantry_add(tmp_path):
    mgr = PantryManager(base_dir=tmp_path)
    mgr.add("olive oil")
    items = mgr.list()
    assert len(items) == 1
    assert items[0].name == "olive oil"
    assert items[0].quantity == ""


def test_pantry_add_with_quantity(tmp_path):
    mgr = PantryManager(base_dir=tmp_path)
    mgr.add("olive oil", "1 bottle")
    assert mgr.list()[0].quantity == "1 bottle"


def test_pantry_add_duplicate_is_idempotent(tmp_path):
    mgr = PantryManager(base_dir=tmp_path)
    mgr.add("olive oil")
    mgr.add("olive oil")
    assert len(mgr.list()) == 1


def test_pantry_remove(tmp_path):
    mgr = PantryManager(base_dir=tmp_path)
    mgr.add("olive oil")
    mgr.add("kosher salt")
    mgr.remove("olive oil")
    names = [p.name for p in mgr.list()]
    assert "olive oil" not in names
    assert "kosher salt" in names


def test_pantry_remove_nonexistent_is_silent(tmp_path):
    mgr = PantryManager(base_dir=tmp_path)
    mgr.remove("ghost item")  # should not raise


def test_pantry_names_returns_set(tmp_path):
    mgr = PantryManager(base_dir=tmp_path)
    mgr.add("olive oil")
    mgr.add("kosher salt")
    assert mgr.names() == {"olive oil", "kosher salt"}


def test_pantry_persists_across_instances(tmp_path):
    PantryManager(base_dir=tmp_path).add("olive oil")
    loaded = PantryManager(base_dir=tmp_path).list()
    assert loaded[0].name == "olive oil"


def test_pantry_empty_by_default(tmp_path):
    mgr = PantryManager(base_dir=tmp_path)
    assert mgr.list() == []
    assert mgr.names() == set()


def test_pantry_items_are_auto_skipped(monkeypatch):
    """Items whose names are in pantry_names are marked confirmed_have=True without prompting."""
    prompt_called = {"n": 0}

    def mock_prompt(*args, **kwargs):
        prompt_called["n"] += 1
        return "y"

    monkeypatch.setattr("click.prompt", mock_prompt)
    ingredients = [
        _make_ingredient("olive oil"),   # in pantry
        _make_ingredient("garlic"),      # not in pantry
    ]
    result = run_pantry_check(ingredients, pantry_names={"olive oil"})
    assert result[0].confirmed_have is True   # auto-marked
    assert prompt_called["n"] == 1            # only prompted for garlic


def test_pantry_auto_skip_does_not_override_already_confirmed(monkeypatch):
    """Items already confirmed are still skipped, regardless of pantry."""
    monkeypatch.setattr("click.prompt", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not prompt")))
    ingredients = [_make_ingredient("garlic", confirmed_have=True)]
    result = run_pantry_check(ingredients, pantry_names=set())
    assert result[0].confirmed_have is True


def test_no_pantry_names_behaves_as_before(monkeypatch):
    """Calling without pantry_names still prompts for all unconfirmed items."""
    monkeypatch.setattr("click.prompt", lambda *a, **kw: "y")
    ingredients = [_make_ingredient("garlic")]
    result = run_pantry_check(ingredients)
    assert result[0].confirmed_have is True
