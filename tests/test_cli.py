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
