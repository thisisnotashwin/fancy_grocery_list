from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from fancy_grocery_list.cli import cli


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
