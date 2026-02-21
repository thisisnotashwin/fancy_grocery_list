from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from fancy_grocery_list.cli import cli


def test_module_invocation_works():
    """python -m fancy_grocery_list must work (requires __main__.py)."""
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "fancy_grocery_list", "--help"],
        capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(__import__("pathlib").Path(__file__).parents[1] / "src")},
    )
    assert result.returncode == 0
    assert "grocery" in result.stdout.lower() or "Usage" in result.stdout


def test_recipe_add_is_subcommand_of_recipe_group():
    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "--help"])
    assert result.exit_code == 0
    assert "add" in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_add_exits_nonzero_when_no_active_session(MockManager):
    mock_manager = MagicMock()
    mock_manager.load_current.side_effect = FileNotFoundError("No active session. Run: grocery new")
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "add"])

    assert result.exit_code == 1
    assert "No active session" in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_done_exits_nonzero_when_no_active_session(MockManager):
    mock_manager = MagicMock()
    mock_manager.load_current.side_effect = FileNotFoundError("No active session. Run: grocery new")
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["done"])

    assert result.exit_code == 1
    assert "No active session" in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_open_exits_nonzero_when_session_not_found(MockManager):
    mock_manager = MagicMock()
    mock_manager.open_session.side_effect = FileNotFoundError("Session 'xyz' not found.")
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["open", "xyz"])

    assert result.exit_code == 1
    assert "xyz" in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_add_exits_nonzero_on_missing_api_key(MockManager):
    mock_manager = MagicMock()
    mock_manager.load_current.return_value = MagicMock(recipes=[])
    MockManager.return_value = mock_manager

    runner = CliRunner()
    with patch.dict("os.environ", {}, clear=True):
        # Unset ANTHROPIC_API_KEY so Config() raises ValidationError
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = runner.invoke(cli, ["recipe", "add"])

    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY" in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_done_exits_nonzero_on_missing_api_key(MockManager):
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_session.processed_ingredients = [MagicMock(confirmed_have=None)]
    mock_manager.load_current.return_value = mock_session
    MockManager.return_value = mock_manager

    runner = CliRunner()
    with patch("fancy_grocery_list.cli.Config") as MockConfig:
        from pydantic import ValidationError
        MockConfig.side_effect = ValidationError.from_exception_data(
            "Config", [{"type": "value_error", "loc": ("anthropic_api_key",), "msg": "ANTHROPIC_API_KEY is required", "input": "", "ctx": {"error": ValueError("ANTHROPIC_API_KEY is required")}}]
        )
        result = runner.invoke(cli, ["done"])

    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY" in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_done_validates_config_before_pantry_check(MockManager):
    """Config must fail before pantry check runs — no interactive work before config error."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_session.processed_ingredients = [MagicMock(confirmed_have=None)]
    mock_manager.load_current.return_value = mock_session
    MockManager.return_value = mock_manager

    runner = CliRunner()
    with patch("fancy_grocery_list.cli.Config") as MockConfig, \
         patch("fancy_grocery_list.cli.run_pantry_check") as mock_pantry:
        MockConfig.side_effect = Exception("config_fail")
        result = runner.invoke(cli, ["done"])

    mock_pantry.assert_not_called()


@patch("fancy_grocery_list.cli.SessionManager")
def test_new_command_creates_session(MockManager):
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_session.id = "2026-02-20-dinner"
    mock_session.name = "dinner"
    mock_manager.new.return_value = mock_session
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "--name", "dinner"])

    assert result.exit_code == 0
    assert "dinner" in result.output
    mock_manager.new.assert_called_once_with(name="dinner")


@patch("fancy_grocery_list.cli.SessionManager")
def test_list_command_shows_sessions(MockManager):
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_session.id = "2026-02-20-dinner"
    mock_session.name = "dinner"
    mock_session.recipes = []
    mock_session.finalized = False
    mock_manager.list_sessions.return_value = [mock_session]
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "2026-02-20-dinner" in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_new_command_without_name(MockManager):
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_session.id = "2026-02-20-session"
    mock_session.name = None
    mock_manager.new.return_value = mock_session
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["new"])
    assert result.exit_code == 0
    mock_manager.new.assert_called_once_with(name=None)


# --- item add tests ---

@patch("fancy_grocery_list.cli.SessionManager")
def test_item_add_exits_nonzero_when_no_active_session(MockManager):
    mock_manager = MagicMock()
    mock_manager.load_current.side_effect = FileNotFoundError("No active session. Run: grocery new")
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["item", "add", "eggs", "1 dozen"])
    assert result.exit_code == 1
    assert "No active session" in result.output


@patch("fancy_grocery_list.cli.process")
@patch("fancy_grocery_list.cli.Config")
@patch("fancy_grocery_list.cli.SessionManager")
def test_item_add_appends_to_extra_items(MockManager, MockConfig, mock_process):
    from fancy_grocery_list.models import GrocerySession
    from datetime import datetime, timezone

    mock_manager = MagicMock()
    session = GrocerySession(
        id="2026-02-20-test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    mock_manager.load_current.return_value = session
    MockManager.return_value = mock_manager
    MockConfig.return_value = MagicMock()
    mock_process.return_value = []

    runner = CliRunner()
    result = runner.invoke(cli, ["item", "add", "eggs", "1 dozen"])

    assert result.exit_code == 0
    assert len(session.extra_items) == 1
    assert session.extra_items[0].text == "1 dozen eggs"
    assert session.extra_items[0].recipe_title == "[added manually]"


# --- staple tests ---

@patch("fancy_grocery_list.cli.StapleManager")
def test_staple_add_command(MockStapleManager):
    mock_mgr = MagicMock()
    MockStapleManager.return_value = mock_mgr

    runner = CliRunner()
    result = runner.invoke(cli, ["staple", "add", "eggs", "1 dozen"])

    assert result.exit_code == 0
    mock_mgr.add.assert_called_once_with("eggs", "1 dozen")


@patch("fancy_grocery_list.cli.StapleManager")
def test_staple_remove_command(MockStapleManager):
    mock_mgr = MagicMock()
    MockStapleManager.return_value = mock_mgr

    runner = CliRunner()
    result = runner.invoke(cli, ["staple", "remove", "eggs"])

    assert result.exit_code == 0
    mock_mgr.remove.assert_called_once_with("eggs")


@patch("fancy_grocery_list.cli.StapleManager")
def test_staple_list_command_shows_staples(MockStapleManager):
    from fancy_grocery_list.staples import Staple
    mock_mgr = MagicMock()
    mock_mgr.list.return_value = [Staple(name="eggs", quantity="1 dozen"), Staple(name="butter")]
    MockStapleManager.return_value = mock_mgr

    runner = CliRunner()
    result = runner.invoke(cli, ["staple", "list"])

    assert result.exit_code == 0
    assert "eggs" in result.output
    assert "1 dozen" in result.output
    assert "butter" in result.output


@patch("fancy_grocery_list.cli.StapleManager")
def test_staple_list_command_empty(MockStapleManager):
    mock_mgr = MagicMock()
    mock_mgr.list.return_value = []
    MockStapleManager.return_value = mock_mgr

    runner = CliRunner()
    result = runner.invoke(cli, ["staple", "list"])

    assert result.exit_code == 0
    assert "No staples" in result.output


def test_process_all_applies_scale_prefix():
    """_process_all must annotate ingredient text when scale != 1.0."""
    from fancy_grocery_list.cli import _process_all
    from fancy_grocery_list.models import GrocerySession, RecipeData
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        recipes=[RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour"], scale=2.0)],
    )
    mock_manager = MagicMock()
    mock_config = MagicMock()

    captured_raws = []

    def capture(raw_list, config):
        captured_raws.extend(raw_list)
        return []

    with patch("fancy_grocery_list.cli.process", side_effect=capture):
        _process_all(session, mock_manager, mock_config)

    assert len(captured_raws) == 1
    assert captured_raws[0].text == "[×2.0] 1 cup flour"


def test_process_all_no_prefix_for_scale_1():
    """_process_all must NOT add a prefix when scale == 1.0."""
    from fancy_grocery_list.cli import _process_all
    from fancy_grocery_list.models import GrocerySession, RecipeData
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        recipes=[RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour"], scale=1.0)],
    )
    captured_raws = []

    def capture(raw_list, config):
        captured_raws.extend(raw_list)
        return []

    with patch("fancy_grocery_list.cli.process", side_effect=capture):
        _process_all(session, MagicMock(), MagicMock())

    assert captured_raws[0].text == "1 cup flour"


@patch("fancy_grocery_list.cli.SessionManager")
def test_recipe_list_shows_recipes(MockManager):
    from fancy_grocery_list.models import GrocerySession, RecipeData
    from datetime import datetime, timezone

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        recipes=[
            RecipeData(title="Pasta Bolognese", url="https://example.com/pasta", raw_ingredients=["1 cup flour", "2 eggs"]),
            RecipeData(title="Chicken Tikka", url="https://example.com/tikka", raw_ingredients=["1 lb chicken"], scale=2.0),
        ],
    )
    mock_manager = MagicMock()
    mock_manager.load_current.return_value = session
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "list"])

    assert result.exit_code == 0
    assert "Pasta Bolognese" in result.output
    assert "Chicken Tikka" in result.output
    assert "×2" in result.output
    assert "1." in result.output
    assert "2." in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_recipe_list_empty(MockManager):
    from fancy_grocery_list.models import GrocerySession
    from datetime import datetime, timezone

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    mock_manager = MagicMock()
    mock_manager.load_current.return_value = session
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "list"])

    assert result.exit_code == 0
    assert "No recipes" in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_recipe_list_exits_nonzero_when_no_active_session(MockManager):
    mock_manager = MagicMock()
    mock_manager.load_current.side_effect = FileNotFoundError("No active session. Run: grocery new")
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "list"])

    assert result.exit_code == 1
    assert "No active session" in result.output


def test_recipe_add_help_shows_scale_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "add", "--help"])
    assert result.exit_code == 0
    assert "--scale" in result.output


@patch("fancy_grocery_list.cli.fetch")
@patch("fancy_grocery_list.cli.scrape")
@patch("fancy_grocery_list.cli.process")
@patch("fancy_grocery_list.cli.Config")
@patch("fancy_grocery_list.cli.SessionManager")
def test_recipe_add_scale_stored_on_recipe(MockManager, MockConfig, mock_process, mock_scrape, mock_fetch):
    from fancy_grocery_list.models import GrocerySession, RecipeData
    from datetime import datetime, timezone

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    mock_manager = MagicMock()
    mock_manager.load_current.return_value = session
    MockManager.return_value = mock_manager
    MockConfig.return_value = MagicMock()
    mock_process.return_value = []
    mock_fetch.return_value = "<html></html>"
    mock_scrape.return_value = RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour"])

    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "add", "--scale", "2"], input="https://example.com\n\n")

    assert result.exit_code == 0
    assert len(session.recipes) == 1
    assert session.recipes[0].scale == 2.0
