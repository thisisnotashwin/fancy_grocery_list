import os
import pytest
from fancy_grocery_list.config import Config


def test_config_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    config = Config()
    assert config.anthropic_api_key == "test-key-123"


def test_config_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Config()


def test_config_default_sections(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    config = Config()
    assert "Produce" in config.store_sections
    assert "Dairy & Eggs" in config.store_sections


def test_config_default_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    config = Config()
    assert config.anthropic_model == "claude-opus-4-6"
