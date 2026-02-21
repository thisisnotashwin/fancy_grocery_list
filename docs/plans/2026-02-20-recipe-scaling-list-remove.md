# Recipe Scaling, List, and Remove Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `--scale` to `recipe add`, and add `recipe list`, `recipe remove`, `item list`, `item remove` commands for full CRUD parity.

**Architecture:** Two-file change: `models.py` gains a `scale` field on `RecipeData`; `cli.py` gains five new commands/options. The scale factor is applied as a text prefix (`[×N]`) on each raw ingredient before passing to the existing AI consolidation step — no changes needed to the processor. Remove commands re-run `_process_all` to keep the consolidated list in sync, mirroring the behavior of `item add`. `item list`/`item remove` only operate on manually-added items (`recipe_title == "[added manually]"`); staples are managed via the `staple` command group.

**Tech Stack:** Click (CLI), Pydantic (models), existing `_process_all` / `process()` pipeline

---

### Task 1: Add `scale` field to `RecipeData`

**Files:**
- Modify: `src/fancy_grocery_list/models.py`
- Modify: `tests/test_models.py`

**Step 1: Write the failing tests**

Add to `tests/test_models.py`:

```python
def test_recipe_data_scale_defaults_to_1():
    recipe = RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour"])
    assert recipe.scale == 1.0


def test_recipe_data_scale_can_be_set():
    recipe = RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour"], scale=2.5)
    assert recipe.scale == 2.5


def test_grocery_session_loads_recipe_without_scale_field():
    """Old sessions without scale on recipes must still deserialize."""
    raw = {
        "version": 1,
        "id": "2026-02-20-old",
        "created_at": "2026-02-20T00:00:00Z",
        "updated_at": "2026-02-20T00:00:00Z",
        "recipes": [{"title": "Pasta", "url": "https://example.com", "raw_ingredients": ["1 cup flour"]}],
        "processed_ingredients": [],
        "finalized": False,
        "output_path": None,
    }
    session = GrocerySession.model_validate(raw)
    assert session.recipes[0].scale == 1.0
```

**Step 2: Run to confirm they fail**

```
pytest tests/test_models.py::test_recipe_data_scale_defaults_to_1 tests/test_models.py::test_recipe_data_scale_can_be_set tests/test_models.py::test_grocery_session_loads_recipe_without_scale_field -v
```

Expected: `AttributeError: 'RecipeData' object has no attribute 'scale'`

**Step 3: Add `scale` to `RecipeData`**

In `src/fancy_grocery_list/models.py`, update `RecipeData`:

```python
class RecipeData(BaseModel):
    title: str
    url: str
    raw_ingredients: list[str]
    scale: float = 1.0
```

**Step 4: Run to confirm they pass**

```
pytest tests/test_models.py -v
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/models.py tests/test_models.py
git commit -m "feat: add scale field to RecipeData"
```

---

### Task 2: Apply scale prefix in `_process_all`

**Files:**
- Modify: `src/fancy_grocery_list/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
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
```

**Step 2: Run to confirm they fail**

```
pytest tests/test_cli.py::test_process_all_applies_scale_prefix tests/test_cli.py::test_process_all_no_prefix_for_scale_1 -v
```

Expected: Both FAIL — `_process_all` doesn't apply any prefix yet.

**Step 3: Update `_process_all` in `cli.py`**

Replace the existing `_process_all` function (lines 102–110):

```python
def _process_all(session, manager, config: Config) -> None:
    recipe_raw = [
        RawIngredient(
            text=f"[×{r.scale}] {ing}" if r.scale != 1.0 else ing,
            recipe_title=r.title,
            recipe_url=r.url,
        )
        for r in session.recipes
        for ing in r.raw_ingredients
    ]
    all_raw = recipe_raw + session.extra_items
    session.processed_ingredients = process(all_raw, config)
    manager.save(session)
```

**Step 4: Run to confirm they pass**

```
pytest tests/test_cli.py::test_process_all_applies_scale_prefix tests/test_cli.py::test_process_all_no_prefix_for_scale_1 -v
```

Expected: Both PASS.

**Step 5: Run full suite to ensure no regressions**

```
pytest -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/fancy_grocery_list/cli.py tests/test_cli.py
git commit -m "feat: apply scale prefix in _process_all"
```

---

### Task 3: Add `--scale` flag to `recipe add`

**Files:**
- Modify: `src/fancy_grocery_list/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
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
```

**Step 2: Run to confirm they fail**

```
pytest tests/test_cli.py::test_recipe_add_help_shows_scale_flag tests/test_cli.py::test_recipe_add_scale_stored_on_recipe -v
```

Expected: FAIL — `--scale` option doesn't exist yet.

**Step 3: Add `--scale` to `recipe_add` in `cli.py`**

Replace the `recipe_add` decorator and signature (starting at line 44):

```python
@recipe.command("add")
@click.option(
    "--html", "html_source", default=None, type=str,
    help="URL or path to saved HTML file (for paywalled/single-recipe use)"
)
@click.option(
    "--scale", "scale", default=1.0, type=float, show_default=True,
    help="Scale factor for recipe ingredients (e.g. 2 doubles all quantities)"
)
def recipe_add(html_source: str | None, scale: float):
    """Add recipe URLs to the current session."""
```

Then, where each recipe is appended to `session.recipes`, set its scale. Find the line:
```python
session.recipes.append(recipe_data)
```
Replace with:
```python
recipe_data.scale = scale
session.recipes.append(recipe_data)
```

Also update `_add_from_html` signature and call site to accept and apply scale:

```python
def _add_from_html(session, manager, html_source: str, config: Config, scale: float = 1.0) -> None:
```

And inside `_add_from_html`, after `session.recipes.append(recipe_data)`:
```python
recipe_data.scale = scale
session.recipes.append(recipe_data)
```

And update the call in `recipe_add`:
```python
_add_from_html(session, manager, html_source, config, scale=scale)
```

**Step 4: Run to confirm they pass**

```
pytest tests/test_cli.py::test_recipe_add_help_shows_scale_flag tests/test_cli.py::test_recipe_add_scale_stored_on_recipe -v
```

Expected: Both PASS.

**Step 5: Run full suite**

```
pytest -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/fancy_grocery_list/cli.py tests/test_cli.py
git commit -m "feat: add --scale flag to recipe add"
```

---

### Task 4: Add `recipe list` command

**Files:**
- Modify: `src/fancy_grocery_list/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
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
```

**Step 2: Run to confirm they fail**

```
pytest tests/test_cli.py::test_recipe_list_shows_recipes tests/test_cli.py::test_recipe_list_empty tests/test_cli.py::test_recipe_list_exits_nonzero_when_no_active_session -v
```

Expected: FAIL — `recipe list` subcommand not found.

**Step 3: Add `recipe list` to `cli.py`**

Add after the `recipe_add` function (before the `item` group):

```python
@recipe.command("list")
def recipe_list():
    """Show recipes in the current session."""
    manager = SessionManager()
    try:
        session = manager.load_current()
    except FileNotFoundError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    if not session.recipes:
        console.print("No recipes in this session. Run [bold]grocery recipe add[/bold] to add some.")
        return

    console.print("\n[bold]Recipes in current session[/bold]\n")
    for i, r in enumerate(session.recipes, start=1):
        scale_label = f" ×{r.scale}" if r.scale != 1.0 else " ×1"
        console.print(f"  {i}. {r.title} ({len(r.raw_ingredients)} ingredients,{scale_label})")
    console.print()
```

**Step 4: Run to confirm they pass**

```
pytest tests/test_cli.py::test_recipe_list_shows_recipes tests/test_cli.py::test_recipe_list_empty tests/test_cli.py::test_recipe_list_exits_nonzero_when_no_active_session -v
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/cli.py tests/test_cli.py
git commit -m "feat: add 'grocery recipe list' command"
```

---

### Task 5: Add `recipe remove <index>` command

**Files:**
- Modify: `src/fancy_grocery_list/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
@patch("fancy_grocery_list.cli.process")
@patch("fancy_grocery_list.cli.Config")
@patch("fancy_grocery_list.cli.SessionManager")
def test_recipe_remove_removes_by_index(MockManager, MockConfig, mock_process):
    from fancy_grocery_list.models import GrocerySession, RecipeData
    from datetime import datetime, timezone

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        recipes=[
            RecipeData(title="Pasta", url="https://example.com/pasta", raw_ingredients=["1 cup flour"]),
            RecipeData(title="Tikka", url="https://example.com/tikka", raw_ingredients=["1 lb chicken"]),
        ],
    )
    mock_manager = MagicMock()
    mock_manager.load_current.return_value = session
    MockManager.return_value = mock_manager
    MockConfig.return_value = MagicMock()
    mock_process.return_value = []

    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "remove", "1"])

    assert result.exit_code == 0
    assert len(session.recipes) == 1
    assert session.recipes[0].title == "Tikka"


@patch("fancy_grocery_list.cli.SessionManager")
def test_recipe_remove_out_of_range_exits_nonzero(MockManager):
    from fancy_grocery_list.models import GrocerySession, RecipeData
    from datetime import datetime, timezone

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        recipes=[RecipeData(title="Pasta", url="https://example.com", raw_ingredients=["1 cup flour"])],
    )
    mock_manager = MagicMock()
    mock_manager.load_current.return_value = session
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "remove", "5"])

    assert result.exit_code == 1
    assert len(session.recipes) == 1  # unchanged


@patch("fancy_grocery_list.cli.SessionManager")
def test_recipe_remove_exits_nonzero_when_no_active_session(MockManager):
    mock_manager = MagicMock()
    mock_manager.load_current.side_effect = FileNotFoundError("No active session. Run: grocery new")
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["recipe", "remove", "1"])

    assert result.exit_code == 1
    assert "No active session" in result.output
```

**Step 2: Run to confirm they fail**

```
pytest tests/test_cli.py::test_recipe_remove_removes_by_index tests/test_cli.py::test_recipe_remove_out_of_range_exits_nonzero tests/test_cli.py::test_recipe_remove_exits_nonzero_when_no_active_session -v
```

Expected: FAIL — `recipe remove` subcommand not found.

**Step 3: Add `recipe remove` to `cli.py`**

Add after `recipe_list`:

```python
@recipe.command("remove")
@click.argument("index", type=int)
def recipe_remove(index: int):
    """Remove a recipe from the current session by its index (from 'recipe list')."""
    manager = SessionManager()
    try:
        session = manager.load_current()
    except FileNotFoundError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    if index < 1 or index > len(session.recipes):
        err_console.print(f"[red]Error:[/red] Index {index} is out of range. Use 'grocery recipe list' to see valid indices.")
        raise SystemExit(1)

    removed = session.recipes.pop(index - 1)
    console.print(f"[green]✓[/green] Removed: {removed.title}")

    if session.recipes or session.extra_items:
        try:
            config = Config()
        except ValidationError:
            err_console.print("[red]Error:[/red] ANTHROPIC_API_KEY environment variable is not set.")
            raise SystemExit(1)
        console.print("[dim]Re-processing ingredients...[/dim]")
        try:
            _process_all(session, manager, config)
            console.print(f"[green]✓[/green] Consolidated to {len(session.processed_ingredients)} ingredients.")
        except ProcessorError as e:
            console.print(f"[red]Error processing ingredients:[/red] {e}")
            manager.save(session)
    else:
        session.processed_ingredients = []
        manager.save(session)
```

**Step 4: Run to confirm they pass**

```
pytest tests/test_cli.py::test_recipe_remove_removes_by_index tests/test_cli.py::test_recipe_remove_out_of_range_exits_nonzero tests/test_cli.py::test_recipe_remove_exits_nonzero_when_no_active_session -v
```

Expected: All PASS.

**Step 5: Run full suite**

```
pytest -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/fancy_grocery_list/cli.py tests/test_cli.py
git commit -m "feat: add 'grocery recipe remove <index>' command"
```

---

### Task 6: Add `item list` command

**Files:**
- Modify: `src/fancy_grocery_list/cli.py`
- Modify: `tests/test_cli.py`

**Note:** `item list` shows only manually-added items (`recipe_title == "[added manually]"`). Staples are displayed via `grocery staple list`, not here.

**Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
@patch("fancy_grocery_list.cli.SessionManager")
def test_item_list_shows_manual_items(MockManager):
    from fancy_grocery_list.models import GrocerySession, RawIngredient
    from datetime import datetime, timezone

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        extra_items=[
            RawIngredient(text="1 dozen eggs", recipe_title="[added manually]", recipe_url=""),
            RawIngredient(text="butter", recipe_title="[staple]", recipe_url=""),
            RawIngredient(text="birthday candles", recipe_title="[added manually]", recipe_url=""),
        ],
    )
    mock_manager = MagicMock()
    mock_manager.load_current.return_value = session
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["item", "list"])

    assert result.exit_code == 0
    assert "1 dozen eggs" in result.output
    assert "birthday candles" in result.output
    assert "butter" not in result.output  # staple, not shown here
    assert "1." in result.output
    assert "2." in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_item_list_empty(MockManager):
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
    result = runner.invoke(cli, ["item", "list"])

    assert result.exit_code == 0
    assert "No manually added items" in result.output


@patch("fancy_grocery_list.cli.SessionManager")
def test_item_list_exits_nonzero_when_no_active_session(MockManager):
    mock_manager = MagicMock()
    mock_manager.load_current.side_effect = FileNotFoundError("No active session. Run: grocery new")
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["item", "list"])

    assert result.exit_code == 1
    assert "No active session" in result.output
```

**Step 2: Run to confirm they fail**

```
pytest tests/test_cli.py::test_item_list_shows_manual_items tests/test_cli.py::test_item_list_empty tests/test_cli.py::test_item_list_exits_nonzero_when_no_active_session -v
```

Expected: FAIL — `item list` subcommand not found.

**Step 3: Add `item list` to `cli.py`**

Add after the `item_add` function (before the `staple` group):

```python
@item.command("list")
def item_list():
    """Show manually added items in the current session."""
    manager = SessionManager()
    try:
        session = manager.load_current()
    except FileNotFoundError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    manual_items = [it for it in session.extra_items if it.recipe_title == "[added manually]"]
    if not manual_items:
        console.print("No manually added items. Use [bold]grocery item add[/bold] to add some.")
        return

    console.print("\n[bold]Manually added items[/bold]\n")
    for i, it in enumerate(manual_items, start=1):
        console.print(f"  {i}. {it.text}")
    console.print()
```

**Step 4: Run to confirm they pass**

```
pytest tests/test_cli.py::test_item_list_shows_manual_items tests/test_cli.py::test_item_list_empty tests/test_cli.py::test_item_list_exits_nonzero_when_no_active_session -v
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add src/fancy_grocery_list/cli.py tests/test_cli.py
git commit -m "feat: add 'grocery item list' command"
```

---

### Task 7: Add `item remove <index>` command

**Files:**
- Modify: `src/fancy_grocery_list/cli.py`
- Modify: `tests/test_cli.py`

**Note:** Index is 1-based over the manually-added items only (same list as `item list`). Staple-sourced items are not removable via this command.

**Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
@patch("fancy_grocery_list.cli.process")
@patch("fancy_grocery_list.cli.Config")
@patch("fancy_grocery_list.cli.SessionManager")
def test_item_remove_removes_by_index(MockManager, MockConfig, mock_process):
    from fancy_grocery_list.models import GrocerySession, RawIngredient
    from datetime import datetime, timezone

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        extra_items=[
            RawIngredient(text="butter", recipe_title="[staple]", recipe_url=""),
            RawIngredient(text="1 dozen eggs", recipe_title="[added manually]", recipe_url=""),
            RawIngredient(text="birthday candles", recipe_title="[added manually]", recipe_url=""),
        ],
    )
    mock_manager = MagicMock()
    mock_manager.load_current.return_value = session
    MockManager.return_value = mock_manager
    MockConfig.return_value = MagicMock()
    mock_process.return_value = []

    runner = CliRunner()
    result = runner.invoke(cli, ["item", "remove", "1"])

    assert result.exit_code == 0
    texts = [it.text for it in session.extra_items]
    assert "1 dozen eggs" not in texts
    assert "butter" in texts        # staple untouched
    assert "birthday candles" in texts


@patch("fancy_grocery_list.cli.SessionManager")
def test_item_remove_out_of_range_exits_nonzero(MockManager):
    from fancy_grocery_list.models import GrocerySession, RawIngredient
    from datetime import datetime, timezone

    session = GrocerySession(
        id="test",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        extra_items=[
            RawIngredient(text="eggs", recipe_title="[added manually]", recipe_url=""),
        ],
    )
    mock_manager = MagicMock()
    mock_manager.load_current.return_value = session
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["item", "remove", "5"])

    assert result.exit_code == 1
    assert len(session.extra_items) == 1  # unchanged


@patch("fancy_grocery_list.cli.SessionManager")
def test_item_remove_exits_nonzero_when_no_active_session(MockManager):
    mock_manager = MagicMock()
    mock_manager.load_current.side_effect = FileNotFoundError("No active session. Run: grocery new")
    MockManager.return_value = mock_manager

    runner = CliRunner()
    result = runner.invoke(cli, ["item", "remove", "1"])

    assert result.exit_code == 1
    assert "No active session" in result.output
```

**Step 2: Run to confirm they fail**

```
pytest tests/test_cli.py::test_item_remove_removes_by_index tests/test_cli.py::test_item_remove_out_of_range_exits_nonzero tests/test_cli.py::test_item_remove_exits_nonzero_when_no_active_session -v
```

Expected: FAIL — `item remove` subcommand not found.

**Step 3: Add `item remove` to `cli.py`**

Add after `item_list`:

```python
@item.command("remove")
@click.argument("index", type=int)
def item_remove(index: int):
    """Remove a manually added item by its index (from 'item list')."""
    manager = SessionManager()
    try:
        session = manager.load_current()
    except FileNotFoundError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    manual_items = [it for it in session.extra_items if it.recipe_title == "[added manually]"]
    if index < 1 or index > len(manual_items):
        err_console.print(f"[red]Error:[/red] Index {index} is out of range. Use 'grocery item list' to see valid indices.")
        raise SystemExit(1)

    target = manual_items[index - 1]
    session.extra_items.remove(target)
    console.print(f"[green]✓[/green] Removed: {target.text}")

    if session.recipes or session.extra_items:
        try:
            config = Config()
        except ValidationError:
            err_console.print("[red]Error:[/red] ANTHROPIC_API_KEY environment variable is not set.")
            raise SystemExit(1)
        console.print("[dim]Re-processing ingredients...[/dim]")
        try:
            _process_all(session, manager, config)
            console.print(f"[green]✓[/green] Consolidated to {len(session.processed_ingredients)} ingredients.")
        except ProcessorError as e:
            console.print(f"[red]Error processing ingredients:[/red] {e}")
            manager.save(session)
    else:
        session.processed_ingredients = []
        manager.save(session)
```

**Step 4: Run to confirm they pass**

```
pytest tests/test_cli.py::test_item_remove_removes_by_index tests/test_cli.py::test_item_remove_out_of_range_exits_nonzero tests/test_cli.py::test_item_remove_exits_nonzero_when_no_active_session -v
```

Expected: All PASS.

**Step 5: Run the full test suite**

```
pytest -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/fancy_grocery_list/cli.py tests/test_cli.py
git commit -m "feat: add 'grocery item remove <index>' command"
```

---

### Task 8: Smoke test the full command surface

No automated test — manual verification of the UX.

```bash
# Verify help text shows all new commands
grocery recipe --help    # should show: add, list, remove
grocery item --help      # should show: add, list, remove
grocery staple --help    # should show: add, list, remove (unchanged)

# New session
grocery new --name "test"

# Add a recipe at ×2 scale
grocery recipe add --scale 2   # enter a recipe URL when prompted

# List recipes
grocery recipe list             # should show recipe with ×2

# Remove it
grocery recipe remove 1

# Add manual items
grocery item add eggs "1 dozen"
grocery item add "birthday candles"

# List items
grocery item list               # should show 1. 1 dozen eggs  2. birthday candles

# Remove one
grocery item remove 1           # removes eggs

# Verify
grocery item list               # should show only birthday candles
```
