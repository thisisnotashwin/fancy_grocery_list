from pathlib import Path
import pytest
from fancy_grocery_list.session import SessionManager
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
