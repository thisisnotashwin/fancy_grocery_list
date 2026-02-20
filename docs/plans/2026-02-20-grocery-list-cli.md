# Fancy Grocery List CLI — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a session-based CLI that scrapes recipe URLs, consolidates ingredients via Claude API, walks through an interactive pantry check, and outputs a `[ ]` grocery list organized by store section.

**Architecture:** Pipeline of discrete modules (fetcher → scraper → processor → session → pantry → formatter), each independently swappable. Sessions persist as JSON files in `~/.grocery_lists/`. A single Claude API call per `grocery add` run consolidates and categorizes all ingredients.

**Tech Stack:** Python 3.11+, Click (CLI), httpx (HTTP), recipe-scrapers (ingredient extraction), anthropic SDK (Claude API), pydantic v2 (data models + JSON serialization), rich (terminal UI)

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/fancy_grocery_list/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Create `pyproject.toml`**

```toml
[project]
name = "fancy-grocery-list"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "httpx>=0.27",
    "recipe-scrapers>=15.0",
    "anthropic>=0.40",
    "rich>=13.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.14",
    "pytest-httpx>=0.30",
]

[project.scripts]
grocery = "fancy_grocery_list.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fancy_grocery_list"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 2: Create package stub**

```python
# src/fancy_grocery_list/__init__.py
# (empty)
```

```python
# tests/__init__.py
# (empty)
```

**Step 3: Install in development mode**

```bash
pip install -e ".[dev]"
```

Expected: no errors, `grocery` command available.

**Step 4: Verify**

```bash
grocery --help
```

Expected: error "No such command" or similar (no commands defined yet — that's fine, just confirms the entry point resolves).

**Step 5: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: scaffold project structure and dependencies"
```

---

## Task 2: Data Models

**Files:**
- Create: `src/fancy_grocery_list/models.py`
- Create: `tests/test_models.py`

**Step 1: Write failing tests**

```python
# tests/test_models.py
import json
from datetime import datetime, timezone
from fancy_grocery_list.models import (
    RawIngredient, ProcessedIngredient, RecipeData, GrocerySession
)


def test_raw_ingredient_roundtrip():
    ri = RawIngredient(text="2 large garlic cloves, minced", recipe_title="Pasta", recipe_url="https://example.com")
    assert RawIngredient.model_validate(ri.model_dump()) == ri


def test_processed_ingredient_defaults():
    pi = ProcessedIngredient(name="garlic", quantity="5 cloves", section="Produce", raw_sources=["2 cloves garlic", "3 cloves garlic"])
    assert pi.confirmed_have is None


def test_grocery_session_json_roundtrip(tmp_path):
    session = GrocerySession(
        id="test-session",
        created_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
        updated_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
    )
    path = tmp_path / "session.json"
    path.write_text(session.model_dump_json())
    loaded = GrocerySession.model_validate_json(path.read_text())
    assert loaded.id == "test-session"
    assert loaded.version == 1
    assert loaded.finalized is False


def test_recipe_data_stores_ingredients():
    recipe = RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour", "2 eggs"])
    assert len(recipe.raw_ingredients) == 2
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'fancy_grocery_list.models'`

**Step 3: Implement**

```python
# src/fancy_grocery_list/models.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class RawIngredient(BaseModel):
    text: str
    recipe_title: str
    recipe_url: str


class ProcessedIngredient(BaseModel):
    name: str
    quantity: str
    section: str
    raw_sources: list[str]
    confirmed_have: Optional[bool] = None


class RecipeData(BaseModel):
    title: str
    url: str
    raw_ingredients: list[str]


class GrocerySession(BaseModel):
    version: int = 1
    id: str
    name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    recipes: list[RecipeData] = Field(default_factory=list)
    processed_ingredients: list[ProcessedIngredient] = Field(default_factory=list)
    finalized: bool = False
    output_path: Optional[str] = None
```

**Step 4: Run tests to confirm pass**

```bash
pytest tests/test_models.py -v
```

Expected: 4 tests pass.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/models.py tests/test_models.py
git commit -m "feat: add pydantic data models"
```

---

## Task 3: Configuration Module

**Files:**
- Create: `src/fancy_grocery_list/config.py`
- Create: `tests/test_config.py`

**Step 1: Write failing tests**

```python
# tests/test_config.py
import os
from fancy_grocery_list.config import Config


def test_config_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    config = Config()
    assert config.anthropic_api_key == "test-key-123"


def test_config_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import pytest
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Config()


def test_config_default_sections():
    config = Config(anthropic_api_key="key")
    assert "Produce" in config.store_sections
    assert "Dairy & Eggs" in config.store_sections


def test_config_default_model():
    config = Config(anthropic_api_key="key")
    assert config.anthropic_model == "claude-opus-4-6"
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'fancy_grocery_list.config'`

**Step 3: Implement**

```python
# src/fancy_grocery_list/config.py
from __future__ import annotations
import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-6"
    grocery_lists_dir: Path = Path.home() / ".grocery_lists"
    store_sections: list[str] = [
        "Produce",
        "Meat & Seafood",
        "Dairy & Eggs",
        "Bakery & Bread",
        "Pantry & Dry Goods",
        "Canned & Jarred Goods",
        "Frozen",
        "Spices & Seasonings",
        "Oils & Condiments",
        "Beverages",
        "Other",
    ]
    system_prompt: str = (
        "You are a kitchen assistant that processes recipe ingredients. "
        "Given raw ingredient strings from one or more recipes, you must:\n"
        "1. Parse each into: name, quantity (with unit), and store section\n"
        "2. Consolidate duplicates across recipes (e.g. '2 garlic cloves' + '3 cloves garlic' → '5 cloves garlic')\n"
        "3. Normalize names: lowercase, singular form (e.g. 'garlic clove', 'all-purpose flour')\n"
        "4. Assign exactly one store section per ingredient from the provided list\n\n"
        "Return ONLY a JSON array. Each object must have:\n"
        "  name: string\n"
        "  quantity: string (e.g. '5 cloves', '2 cups', 'to taste')\n"
        "  section: string (must be one of the provided sections)\n"
        "  raw_sources: array of original strings that were merged\n\n"
        "Rules:\n"
        "- Combine quantities using the same unit where possible\n"
        "- If quantity is unspecified, use 'as needed'\n"
        "- Do not split one ingredient into multiple items"
    )

    @field_validator("anthropic_api_key", mode="after")
    @classmethod
    def require_api_key(cls, v: str) -> str:
        env_val = os.environ.get("ANTHROPIC_API_KEY", v)
        if not env_val:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return env_val
```

Note: `pydantic-settings` is a separate package. Add it to `pyproject.toml` dependencies:

```toml
"pydantic-settings>=2.0",
```

Then reinstall:

```bash
pip install -e ".[dev]"
```

**Step 4: Run tests to confirm pass**

```bash
pytest tests/test_config.py -v
```

Expected: 4 tests pass.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/config.py tests/test_config.py pyproject.toml
git commit -m "feat: add configuration module with env var loading"
```

---

## Task 4: HTTP Fetcher

**Files:**
- Create: `src/fancy_grocery_list/fetcher.py`
- Create: `tests/test_fetcher.py`

**Step 1: Write failing tests**

```python
# tests/test_fetcher.py
import pytest
import httpx
from pytest_httpx import HTTPXMock
from fancy_grocery_list.fetcher import fetch, FetchError


def test_fetch_returns_html(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="https://www.seriouseats.com/recipe", text="<html>recipe</html>")
    html = fetch("https://www.seriouseats.com/recipe")
    assert html == "<html>recipe</html>"


def test_fetch_paywall_raises_fetch_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="https://cooking.nytimes.com/recipe", status_code=401)
    with pytest.raises(FetchError, match="paywall"):
        fetch("https://cooking.nytimes.com/recipe")


def test_fetch_404_raises_fetch_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="https://example.com/gone", status_code=404)
    with pytest.raises(FetchError, match="not found"):
        fetch("https://example.com/gone")


def test_fetch_network_error_raises_fetch_error(httpx_mock: HTTPXMock):
    httpx_mock.add_exception(httpx.ConnectError("failed"))
    with pytest.raises(FetchError, match="Could not connect"):
        fetch("https://example.com/recipe")


def test_fetch_sends_browser_headers(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="https://example.com/recipe", text="<html></html>")
    fetch("https://example.com/recipe")
    request = httpx_mock.get_requests()[0]
    assert "Mozilla" in request.headers["user-agent"]
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_fetcher.py -v
```

Expected: `ModuleNotFoundError: No module named 'fancy_grocery_list.fetcher'`

**Step 3: Implement**

```python
# src/fancy_grocery_list/fetcher.py
from __future__ import annotations
import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class FetchError(Exception):
    pass


def fetch(url: str) -> str:
    try:
        response = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
    except httpx.ConnectError:
        raise FetchError(f"Could not connect to {url}. Check your internet connection.")
    except httpx.TimeoutException:
        raise FetchError(f"Request to {url} timed out.")

    if response.status_code in (401, 403):
        raise FetchError(
            f"This page appears to be behind a paywall or requires login ({response.status_code}). "
            "To use a paywalled recipe, save the page HTML from your browser "
            "and run: grocery add --html path/to/saved.html"
        )
    if response.status_code == 404:
        raise FetchError(f"Page not found (404): {url}")
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code} error fetching {url}")

    return response.text
```

**Step 4: Run tests to confirm pass**

```bash
pytest tests/test_fetcher.py -v
```

Expected: 5 tests pass.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/fetcher.py tests/test_fetcher.py
git commit -m "feat: add HTTP fetcher with paywall error handling"
```

---

## Task 5: Recipe Scraper

**Files:**
- Create: `src/fancy_grocery_list/scraper.py`
- Create: `tests/fixtures/serious_eats.html`
- Create: `tests/test_scraper.py`

**Step 1: Create a minimal HTML fixture**

Save this as `tests/fixtures/serious_eats.html`. It uses JSON-LD schema.org/Recipe, which is what real recipe sites use:

```html
<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{
  "@context": "http://schema.org",
  "@type": "Recipe",
  "name": "Simple Pasta",
  "recipeIngredient": [
    "2 cups all-purpose flour",
    "3 large eggs",
    "1 teaspoon salt",
    "2 tablespoons olive oil"
  ]
}
</script>
</head>
<body><h1>Simple Pasta</h1></body>
</html>
```

**Step 2: Write failing tests**

```python
# tests/test_scraper.py
from pathlib import Path
import pytest
from fancy_grocery_list.scraper import scrape, ScrapeError
from fancy_grocery_list.models import RecipeData

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_scrape_extracts_title_and_ingredients():
    html = (FIXTURE_DIR / "serious_eats.html").read_text()
    recipe = scrape(html, url="https://www.seriouseats.com/simple-pasta")
    assert recipe.title == "Simple Pasta"
    assert len(recipe.raw_ingredients) == 4
    assert "2 cups all-purpose flour" in recipe.raw_ingredients


def test_scrape_stores_url():
    html = (FIXTURE_DIR / "serious_eats.html").read_text()
    recipe = scrape(html, url="https://www.seriouseats.com/simple-pasta")
    assert recipe.url == "https://www.seriouseats.com/simple-pasta"


def test_scrape_invalid_html_raises():
    with pytest.raises(ScrapeError):
        scrape("<html><body>no recipe here</body></html>", url="https://example.com")


def test_scrape_returns_recipe_data_type():
    html = (FIXTURE_DIR / "serious_eats.html").read_text()
    result = scrape(html, url="https://www.seriouseats.com/simple-pasta")
    assert isinstance(result, RecipeData)
```

**Step 3: Run to confirm failure**

```bash
pytest tests/test_scraper.py -v
```

Expected: `ModuleNotFoundError: No module named 'fancy_grocery_list.scraper'`

**Step 4: Implement**

```python
# src/fancy_grocery_list/scraper.py
from __future__ import annotations
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode
from fancy_grocery_list.models import RecipeData


class ScrapeError(Exception):
    pass


def scrape(html: str, url: str) -> RecipeData:
    try:
        scraper = scrape_html(html, org_url=url, wild_mode=True)
        ingredients = scraper.ingredients()
        if not ingredients:
            raise ScrapeError(f"No ingredients found at {url}. The page may not contain a recipe.")
        title = scraper.title() or url
        return RecipeData(title=title, url=url, raw_ingredients=ingredients)
    except (WebsiteNotImplementedError, NoSchemaFoundInWildMode):
        raise ScrapeError(
            f"Could not parse recipe from {url}. "
            "Try saving the page HTML and using: grocery add --html path/to/saved.html"
        )
    except ScrapeError:
        raise
    except Exception as e:
        raise ScrapeError(f"Unexpected error scraping {url}: {e}") from e
```

**Step 5: Run tests to confirm pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: 4 tests pass.

**Step 6: Commit**

```bash
git add src/fancy_grocery_list/scraper.py tests/test_scraper.py tests/fixtures/
git commit -m "feat: add recipe scraper wrapping recipe-scrapers library"
```

---

## Task 6: LLM Ingredient Processor

**Files:**
- Create: `src/fancy_grocery_list/processor.py`
- Create: `tests/test_processor.py`

**Step 1: Write failing tests**

```python
# tests/test_processor.py
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
def config():
    return Config(anthropic_api_key="test-key")


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
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_processor.py -v
```

Expected: `ModuleNotFoundError: No module named 'fancy_grocery_list.processor'`

**Step 3: Implement**

```python
# src/fancy_grocery_list/processor.py
from __future__ import annotations
import json
import re
import anthropic
from fancy_grocery_list.models import RawIngredient, ProcessedIngredient
from fancy_grocery_list.config import Config


class ProcessorError(Exception):
    pass


def _extract_json(text: str) -> str:
    """Extract JSON array from text that may contain extra prose."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def process(raw_ingredients: list[RawIngredient], config: Config) -> list[ProcessedIngredient]:
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    sections_list = "\n".join(f"  - {s}" for s in config.store_sections)
    ingredient_lines = "\n".join(
        f"- {ri.text} (from: {ri.recipe_title})" for ri in raw_ingredients
    )
    user_content = (
        f"Store sections to use:\n{sections_list}\n\n"
        f"Ingredients to process:\n{ingredient_lines}"
    )

    response = client.messages.create(
        model=config.anthropic_model,
        max_tokens=4096,
        system=config.system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = response.content[0].text
    try:
        data = json.loads(_extract_json(raw_text))
    except (json.JSONDecodeError, AttributeError) as e:
        raise ProcessorError(f"Failed to parse LLM response as JSON: {e}\n\nRaw response:\n{raw_text}") from e

    try:
        return [ProcessedIngredient(**item) for item in data]
    except Exception as e:
        raise ProcessorError(f"LLM returned unexpected ingredient format: {e}") from e
```

**Step 4: Run tests to confirm pass**

```bash
pytest tests/test_processor.py -v
```

Expected: 4 tests pass.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/processor.py tests/test_processor.py
git commit -m "feat: add Claude API processor for ingredient normalization and categorization"
```

---

## Task 7: Session Manager

**Files:**
- Create: `src/fancy_grocery_list/session.py`
- Create: `tests/test_session.py`

**Step 1: Write failing tests**

```python
# tests/test_session.py
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fancy_grocery_list.session import SessionManager
from fancy_grocery_list.models import GrocerySession, RecipeData, ProcessedIngredient


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
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'fancy_grocery_list.session'`

**Step 3: Implement**

```python
# src/fancy_grocery_list/session.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from fancy_grocery_list.models import GrocerySession


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_id(name: str | None) -> str:
    date = _now().strftime("%Y-%m-%d")
    suffix = name.replace(" ", "-").lower() if name else "session"
    return f"{date}-{suffix}"


class SessionManager:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or (Path.home() / ".grocery_lists")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._current_pointer = self.base_dir / "current.json"

    def _session_path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def new(self, name: str | None = None) -> GrocerySession:
        now = _now()
        session = GrocerySession(id=_make_id(name), name=name, created_at=now, updated_at=now)
        self.save(session)
        self._set_current(session.id)
        return session

    def save(self, session: GrocerySession) -> None:
        session.updated_at = _now()
        self._session_path(session.id).write_text(session.model_dump_json(indent=2))

    def load(self, session_id: str) -> GrocerySession:
        path = self._session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Session '{session_id}' not found.")
        return GrocerySession.model_validate_json(path.read_text())

    def load_current(self) -> GrocerySession:
        if not self._current_pointer.exists():
            raise FileNotFoundError("No active session. Run: grocery new")
        session_id = json.loads(self._current_pointer.read_text())["id"]
        return self.load(session_id)

    def _set_current(self, session_id: str) -> None:
        self._current_pointer.write_text(json.dumps({"id": session_id}))

    def finalize(self, session: GrocerySession, output_path: Path) -> None:
        session.finalized = True
        session.output_path = str(output_path)
        self.save(session)

    def list_sessions(self) -> list[GrocerySession]:
        sessions = []
        for path in sorted(self.base_dir.glob("*.json")):
            if path.name == "current.json":
                continue
            sessions.append(GrocerySession.model_validate_json(path.read_text()))
        return sessions

    def open_session(self, session_id: str) -> GrocerySession:
        session = self.load(session_id)
        session.finalized = False
        self.save(session)
        self._set_current(session.id)
        return session
```

**Step 4: Run tests to confirm pass**

```bash
pytest tests/test_session.py -v
```

Expected: 8 tests pass.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/session.py tests/test_session.py
git commit -m "feat: add session manager with JSON persistence"
```

---

## Task 8: Interactive Pantry Check

**Files:**
- Create: `src/fancy_grocery_list/pantry.py`
- Create: `tests/test_pantry.py`

**Step 1: Write failing tests**

```python
# tests/test_pantry.py
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
        _make_ingredient("garlic", confirmed_have=True),   # already confirmed
        _make_ingredient("flour"),                           # needs check
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
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_pantry.py -v
```

Expected: `ModuleNotFoundError: No module named 'fancy_grocery_list.pantry'`

**Step 3: Implement**

```python
# src/fancy_grocery_list/pantry.py
from __future__ import annotations
from rich.console import Console
from fancy_grocery_list.models import ProcessedIngredient

console = Console()


def run_pantry_check(ingredients: list[ProcessedIngredient]) -> list[ProcessedIngredient]:
    to_check = [i for i in ingredients if i.confirmed_have is None]

    if not to_check:
        return ingredients

    console.print(f"\n[bold]Pantry check:[/bold] {len(to_check)} ingredient(s) to confirm\n")

    for ingredient in to_check:
        while True:
            answer = input(f"  Do you have [bold]{ingredient.quantity} {ingredient.name}[/bold]? (y/n): ").strip().lower()
            if answer in ("y", "yes"):
                ingredient.confirmed_have = True
                break
            elif answer in ("n", "no"):
                ingredient.confirmed_have = False
                break
            else:
                console.print("  [yellow]Please enter y or n[/yellow]")

    return ingredients
```

**Step 4: Run tests to confirm pass**

```bash
pytest tests/test_pantry.py -v
```

Expected: 4 tests pass.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/pantry.py tests/test_pantry.py
git commit -m "feat: add interactive pantry check"
```

---

## Task 9: Output Formatter

**Files:**
- Create: `src/fancy_grocery_list/formatter.py`
- Create: `tests/test_formatter.py`

**Step 1: Write failing tests**

```python
# tests/test_formatter.py
from fancy_grocery_list.formatter import format_grocery_list
from fancy_grocery_list.models import ProcessedIngredient
from fancy_grocery_list.config import Config


def _make_ingredient(name: str, quantity: str, section: str, confirmed_have: bool = False) -> ProcessedIngredient:
    return ProcessedIngredient(
        name=name, quantity=quantity, section=section,
        raw_sources=[name], confirmed_have=confirmed_have
    )


@pytest.fixture
def config():
    return Config(anthropic_api_key="key")


def test_format_groups_by_section(config):
    ingredients = [
        _make_ingredient("garlic", "5 cloves", "Produce"),
        _make_ingredient("all-purpose flour", "2 cups", "Pantry & Dry Goods"),
        _make_ingredient("spinach", "1 bag", "Produce"),
    ]
    output = format_grocery_list(ingredients, config)
    produce_pos = output.index("Produce")
    pantry_pos = output.index("Pantry & Dry Goods")
    garlic_pos = output.index("garlic")
    spinach_pos = output.index("spinach")
    assert produce_pos < garlic_pos
    assert produce_pos < spinach_pos
    assert pantry_pos < output.index("flour")


def test_format_uses_checkbox_style(config):
    ingredients = [_make_ingredient("garlic", "5 cloves", "Produce")]
    output = format_grocery_list(ingredients, config)
    assert "[ ] 5 cloves garlic" in output


def test_format_respects_section_order(config):
    ingredients = [
        _make_ingredient("chicken breast", "1 lb", "Meat & Seafood"),
        _make_ingredient("garlic", "5 cloves", "Produce"),
    ]
    output = format_grocery_list(ingredients, config)
    produce_pos = output.index("Produce")
    meat_pos = output.index("Meat & Seafood")
    # Produce comes before Meat & Seafood in config.store_sections
    assert produce_pos < meat_pos


def test_format_skips_empty_sections(config):
    ingredients = [_make_ingredient("garlic", "5 cloves", "Produce")]
    output = format_grocery_list(ingredients, config)
    assert "Dairy & Eggs" not in output


import pytest
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_formatter.py -v
```

Expected: `ModuleNotFoundError: No module named 'fancy_grocery_list.formatter'`

**Step 3: Implement**

```python
# src/fancy_grocery_list/formatter.py
from __future__ import annotations
from collections import defaultdict
from fancy_grocery_list.models import ProcessedIngredient
from fancy_grocery_list.config import Config


def format_grocery_list(ingredients: list[ProcessedIngredient], config: Config) -> str:
    by_section: dict[str, list[ProcessedIngredient]] = defaultdict(list)
    for ingredient in ingredients:
        section = ingredient.section if ingredient.section in config.store_sections else "Other"
        by_section[section].append(ingredient)

    lines: list[str] = []
    for section in config.store_sections:
        if section not in by_section:
            continue
        lines.append(f"\n{section}")
        lines.append("-" * len(section))
        for ingredient in by_section[section]:
            lines.append(f"[ ] {ingredient.quantity} {ingredient.name}")

    return "\n".join(lines).strip()
```

**Step 4: Run tests to confirm pass**

```bash
pytest tests/test_formatter.py -v
```

Expected: 4 tests pass.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/formatter.py tests/test_formatter.py
git commit -m "feat: add Apple Notes-style grocery list formatter"
```

---

## Task 10: CLI Entry Point

**Files:**
- Create: `src/fancy_grocery_list/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write failing tests**

```python
# tests/test_cli.py
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
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'fancy_grocery_list.cli'`

**Step 3: Implement**

```python
# src/fancy_grocery_list/cli.py
from __future__ import annotations
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from fancy_grocery_list.config import Config
from fancy_grocery_list.fetcher import fetch, FetchError
from fancy_grocery_list.scraper import scrape, ScrapeError
from fancy_grocery_list.processor import process, ProcessorError
from fancy_grocery_list.session import SessionManager
from fancy_grocery_list.pantry import run_pantry_check
from fancy_grocery_list.formatter import format_grocery_list
from fancy_grocery_list.models import RawIngredient

console = Console()


@click.group()
def cli():
    """Fancy Grocery List — recipe URL to grocery list."""
    pass


@cli.command()
@click.option("--name", default=None, help="Optional name for this shopping trip")
def new(name: str | None):
    """Start a new grocery list session."""
    manager = SessionManager()
    session = manager.new(name=name)
    label = f"'{session.name}'" if session.name else session.id
    console.print(f"\n[green]✓[/green] Started session: [bold]{label}[/bold]")
    console.print("Run [bold]grocery add[/bold] to add recipes.\n")


@cli.command()
@click.option("--html", "html_file", default=None, type=click.Path(exists=True),
              help="Path to saved HTML file (for paywalled pages)")
def add(html_file: str | None):
    """Add recipe URLs to the current session."""
    manager = SessionManager()
    try:
        session = manager.load_current()
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        return

    config = Config()
    added_count = 0

    console.print("\n[bold]Add recipes[/bold] (press Enter with no URL to finish)\n")

    if html_file:
        _add_from_html(session, manager, html_file, config)
        return

    while True:
        url = click.prompt("  Recipe URL", default="", show_default=False).strip()
        if not url:
            break
        try:
            console.print(f"  Fetching...", end="\r")
            html = fetch(url)
            recipe = scrape(html, url)
            session.recipes.append(recipe)
            added_count += 1
            console.print(f"  [green]✓[/green] {recipe.title} ({len(recipe.raw_ingredients)} ingredients)")
        except (FetchError, ScrapeError) as e:
            console.print(f"  [red]✗[/red] {e}")

    if added_count == 0:
        console.print("\nNo recipes added.")
        return

    console.print(f"\n[dim]Processing {sum(len(r.raw_ingredients) for r in session.recipes)} ingredients...[/dim]")
    try:
        all_raw = [
            RawIngredient(text=ing, recipe_title=r.title, recipe_url=r.url)
            for r in session.recipes
            for ing in r.raw_ingredients
        ]
        session.processed_ingredients = process(all_raw, config)
        manager.save(session)
        console.print(f"[green]✓[/green] Consolidated to [bold]{len(session.processed_ingredients)}[/bold] ingredients.\n")
        console.print("Run [bold]grocery done[/bold] when you're ready to build your list.")
    except ProcessorError as e:
        console.print(f"[red]Error processing ingredients:[/red] {e}")
        console.print("Your recipes were saved. Try running [bold]grocery add[/bold] again.")
        manager.save(session)


def _add_from_html(session, manager, html_file: str, config: Config):
    html = Path(html_file).read_text()
    url = click.prompt("  URL for this page (for reference)", default="https://unknown").strip()
    try:
        recipe = scrape(html, url)
        session.recipes.append(recipe)
        console.print(f"  [green]✓[/green] {recipe.title} ({len(recipe.raw_ingredients)} ingredients)")
        all_raw = [
            RawIngredient(text=ing, recipe_title=r.title, recipe_url=r.url)
            for r in session.recipes
            for ing in r.raw_ingredients
        ]
        session.processed_ingredients = process(all_raw, config)
        manager.save(session)
        console.print(f"[green]✓[/green] Consolidated to {len(session.processed_ingredients)} ingredients.")
    except (ScrapeError, ProcessorError) as e:
        console.print(f"[red]Error:[/red] {e}")


@cli.command()
def done():
    """Run pantry check and output final grocery list."""
    manager = SessionManager()
    try:
        session = manager.load_current()
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        return

    if not session.processed_ingredients:
        console.print("[yellow]No ingredients found. Run[/yellow] [bold]grocery add[/bold] [yellow]first.[/yellow]")
        return

    config = Config()
    session.processed_ingredients = run_pantry_check(session.processed_ingredients)

    need_to_buy = [i for i in session.processed_ingredients if not i.confirmed_have]
    console.print(f"\n[bold]{len(need_to_buy)}[/bold] items to buy.\n")

    output = format_grocery_list(need_to_buy, config)
    console.print(output)

    # Save .txt file
    output_path = manager.base_dir / f"{session.id}.txt"
    output_path.write_text(output)
    manager.finalize(session, output_path=output_path)
    console.print(f"\n[dim]Saved to {output_path}[/dim]")


@cli.command("list")
def list_sessions():
    """Show all grocery list sessions."""
    manager = SessionManager()
    sessions = manager.list_sessions()
    if not sessions:
        console.print("No sessions found. Run [bold]grocery new[/bold] to start.")
        return

    table = Table(title="Grocery Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Recipes", justify="right")
    table.add_column("Status")

    for s in sessions:
        status = "[green]Finalized[/green]" if s.finalized else "[yellow]In progress[/yellow]"
        table.add_row(s.id, s.name or "—", str(len(s.recipes)), status)

    console.print(table)


@cli.command("open")
@click.argument("session_id", required=False)
def open_session(session_id: str | None):
    """Re-open a past session to add recipes or edit."""
    manager = SessionManager()
    if not session_id:
        sessions = manager.list_sessions()
        if not sessions:
            console.print("No sessions found.")
            return
        console.print("Available sessions:")
        for s in sessions:
            console.print(f"  {s.id}")
        session_id = click.prompt("Session ID to open").strip()

    try:
        session = manager.open_session(session_id)
        console.print(f"[green]✓[/green] Opened session: [bold]{session.id}[/bold]")
        console.print("Run [bold]grocery add[/bold] to add more recipes, or [bold]grocery done[/bold] to finalize.")
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
```

**Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests pass.

**Step 5: Smoke test the CLI manually**

```bash
grocery --help
grocery new --name "test-run"
grocery list
```

Expected: help text shows all commands, new session created, list shows it.

**Step 6: Commit**

```bash
git add src/fancy_grocery_list/cli.py tests/test_cli.py
git commit -m "feat: add Click CLI with new, add, done, list, open commands"
```

---

## Task 11: Final Integration Check

**Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests pass, zero failures.

**Step 2: Verify CLI is installed and shows help**

```bash
grocery --help
grocery new --help
grocery add --help
grocery done --help
grocery list --help
grocery open --help
```

**Step 3: Set API key and do a real smoke test (optional)**

```bash
export ANTHROPIC_API_KEY=your_key_here
grocery new --name "smoke-test"
grocery add  # paste a Serious Eats URL when prompted
grocery done
```

**Step 4: Commit if any fixes were needed**

```bash
git add -p
git commit -m "fix: integration fixes from smoke test"
```

---

## Notes for Implementer

- **API key**: The CLI reads `ANTHROPIC_API_KEY` from the environment. Export it before running.
- **NYT Cooking paywall**: Use `grocery add --html saved.html` after saving the page from your browser.
- **Extensibility hooks**: To change store sections → edit `config.py`. To add a new output format → add a class in `formatter.py`. To support Playwright → swap `fetcher.py`'s `fetch()` implementation.
- **Session location**: `~/.grocery_lists/` — all sessions are plain JSON, freely editable.
