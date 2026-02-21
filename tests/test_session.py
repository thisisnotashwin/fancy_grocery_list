import logging
from pathlib import Path
import pytest
from fancy_grocery_list.session import SessionManager
from fancy_grocery_list.staples import StapleManager
from fancy_grocery_list.models import GrocerySession, RecipeData


@pytest.fixture
def manager(tmp_path):
    return SessionManager(base_dir=tmp_path)


def test_new_session_creates_file(manager, tmp_path):
    session = manager.new(name="weeknight")
    assert session.name == "weeknight"
    assert session.version == 1
    files = list(tmp_path.glob("*.json"))
    assert any("weeknight" in f.name for f in files)


def test_new_session_sets_as_current(manager, tmp_path):
    manager.new(name="test")
    assert (tmp_path / "current.json").exists()


def test_load_current_returns_active_session(manager):
    created = manager.new(name="test")
    loaded = manager.load_current()
    assert loaded.id == created.id


def test_load_current_raises_when_none(manager):
    with pytest.raises(FileNotFoundError, match="No active session"):
        manager.load_current()


def test_add_recipe_and_save(manager):
    manager.new(name="test")
    session = manager.load_current()
    recipe = RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour"])
    session.recipes.append(recipe)
    manager.save(session)

    reloaded = manager.load_current()
    assert len(reloaded.recipes) == 1
    assert reloaded.recipes[0].title == "Pasta"


def test_finalize_saves_output_path(manager, tmp_path):
    manager.new(name="test")
    session = manager.load_current()
    output_path = tmp_path / "output.txt"
    output_path.write_text("[ ] garlic")
    manager.finalize(session, output_path=output_path)

    reloaded = manager.load_current()
    assert reloaded.finalized is True
    assert reloaded.output_path == str(output_path)


def test_list_sessions_returns_all(manager):
    manager.new(name="first")
    manager.new(name="second")
    sessions = manager.list_sessions()
    assert len(sessions) == 2


def test_open_sets_as_current(manager):
    s1 = manager.new(name="first")
    s2 = manager.new(name="second")
    manager.open_session(s1.id)
    current = manager.load_current()
    assert current.id == s1.id


def test_new_session_loads_staples(tmp_path):
    StapleManager(base_dir=tmp_path).add("eggs", "1 dozen")
    StapleManager(base_dir=tmp_path).add("butter", "1 stick")

    session = SessionManager(base_dir=tmp_path).new()

    sources = [item.recipe_title for item in session.extra_items]
    assert sources == ["[staple]", "[staple]"]
    texts = [item.text for item in session.extra_items]
    assert "1 dozen eggs" in texts
    assert "1 stick butter" in texts


def test_new_session_with_no_staples_has_empty_extra_items(tmp_path):
    session = SessionManager(base_dir=tmp_path).new()
    assert session.extra_items == []


def test_list_sessions_warns_via_logging_not_rich(manager, tmp_path, caplog):
    """Corrupt session files should produce a logging.warning, not a Rich console.print."""
    manager.new(name="good")
    (tmp_path / "bad.json").write_text("not valid json{")

    with caplog.at_level(logging.WARNING, logger="fancy_grocery_list.session"):
        sessions = manager.list_sessions()

    assert len(sessions) == 1
    assert any("bad.json" in msg for msg in caplog.messages)
