# Fancy Grocery List — Design Doc
*2026-02-20*

## Overview

A personal CLI tool that takes recipe URLs, extracts and consolidates ingredients, walks through a pantry check, and outputs a formatted `[ ]` grocery checklist organized by store section — ready to paste into Apple Notes (or any text editor).

---

## Architecture

Single Python CLI (`grocery.py`) with no server, no database. All state is local files. The tool is structured as a pipeline of discrete, swappable components:

```
URL(s)
  └─▶ Fetcher          (httpx; swappable for Playwright)
        └─▶ Scraper    (recipe-scrapers; swappable per-site)
              └─▶ LLM Processor  (Claude API; normalize + consolidate + categorize)
                    └─▶ Session Store   (JSON on disk)
                          └─▶ Pantry Check  (interactive CLI)
                                └─▶ Formatter  (pluggable output format)
                                      └─▶ Output (.txt + stdout)
```

Each stage is a small, independently testable module. Swapping in Playwright for NYT Cooking, or switching output formats, touches one module only.

---

## Components

### `fetcher.py`
Fetches raw HTML from a URL. Currently uses `httpx` with browser-like headers. Returns raw HTML string or raises a `FetchError` with a human-readable message. If a page returns 401/403 (paywall), the error message instructs the user to save the HTML manually and use `grocery add --html path/to/file.html`.

Interface:
```python
def fetch(url: str) -> str:  # returns HTML
```

Extensibility: Replace or wrap `fetch()` with a Playwright-based implementation without changing anything downstream.

### `scraper.py`
Wraps `recipe-scrapers`. Takes raw HTML + URL, returns a `Recipe` dataclass: `title`, `url`, `ingredients: list[str]` (raw strings like `"2 large garlic cloves, minced"`).

Interface:
```python
def scrape(html: str, url: str) -> Recipe:
```

Extensibility: Per-site scraper overrides can be registered in a dict before falling back to `recipe-scrapers`.

### `processor.py`
Sends all raw ingredient strings (across all recipes in the session) to Claude API in a single call. Claude returns structured JSON: normalized ingredient list with quantity, unit, name, and store section. Also consolidates duplicates (e.g., `"2 garlic cloves"` + `"3 cloves of garlic"` → `"5 cloves garlic"`).

The prompt and the store section taxonomy are defined in `config.py` so they can be tuned without touching code.

Interface:
```python
def process(ingredients: list[RawIngredient]) -> list[ProcessedIngredient]:
```

`ProcessedIngredient`:
```python
@dataclass
class ProcessedIngredient:
    name: str
    quantity: str        # e.g. "5 cloves"
    section: str         # e.g. "Produce"
    raw_sources: list[str]  # original strings, for debugging
    confirmed_have: bool | None  # None = not yet asked
```

Extensibility: Swap the model, tune the prompt, or add a local NLP fallback — all in one place.

### `session.py`
Manages the lifecycle of a grocery session. Sessions live in `~/.grocery_lists/` as versioned JSON files. A `current.json` pointer tracks the active session.

Session file schema (versioned for future migration):
```json
{
  "version": 1,
  "id": "2026-02-20-weeknight-meals",
  "created_at": "...",
  "updated_at": "...",
  "recipes": [{"title": "...", "url": "...", "raw_ingredients": [...]}],
  "processed_ingredients": [...],
  "finalized": false,
  "output_path": null
}
```

Operations: `new()`, `load()`, `add_recipe()`, `save()`, `finalize()`, `list_sessions()`.

### `pantry.py`
Interactive y/n check over the processed ingredient list using `rich` for clean terminal rendering. Skips ingredients already confirmed in this session (so `grocery add` doesn't re-ask). Returns the updated ingredient list with `confirmed_have` populated.

### `formatter.py`
Takes the final ingredient list (pantry-confirmed, `confirmed_have=False` only) and formats it for output. Currently implements `AppleNotesFormatter` — plain text, grouped by store section, `[ ] quantity item` per line.

Extensibility: Add `MarkdownFormatter`, `ObsidianFormatter`, etc. by implementing a simple `format(ingredients) -> str` interface. The formatter to use is set in `config.py`.

### `config.py`
Single source of truth for tunable behavior:
- `ANTHROPIC_MODEL` — which Claude model to use
- `STORE_SECTIONS` — ordered list of section names (controls output order)
- `OUTPUT_FORMATTER` — which formatter class to use
- `GROCERY_LISTS_DIR` — where sessions are stored (default `~/.grocery_lists/`)
- `SYSTEM_PROMPT` — LLM system prompt for ingredient processing

---

## CLI Commands

```
grocery new [--name NAME]     Start a new session
grocery add [--html FILE]     Add recipe URLs to current session (interactive)
grocery done                  Run pantry check and output final list
grocery list                  Show all past sessions
grocery open [SESSION_ID]     Re-open a past session for editing
```

---

## Data Flow

1. `grocery new` → creates session file, sets as current
2. `grocery add` → prompts for URLs one at a time; fetches + scrapes each; appends raw ingredients to session; re-runs LLM processor over full ingredient set; saves session
3. `grocery done` → runs pantry check over unconfirmed ingredients; formats output; saves `.txt` to same dir as session JSON; prints to stdout

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Paywall / 401 / 403 | Clear error message + instructions to use `--html` flag |
| Unsupported site | `recipe-scrapers` raises `WebsiteNotImplementedError` → user-friendly message |
| Bad URL | Caught at fetch; user re-prompted |
| LLM API failure | Retry once; on second failure, save raw ingredients and exit with instructions to re-run `grocery done` |
| Malformed session file | Version field checked; clear error if migration needed |

---

## Extensibility Points (summary)

- **New scraper**: register in `scraper.py`'s site override dict
- **Paywall support**: swap `fetcher.py` implementation to Playwright
- **New output format**: add formatter class in `formatter.py`
- **Different LLM**: change `ANTHROPIC_MODEL` in `config.py`
- **Store section taxonomy**: edit `STORE_SECTIONS` in `config.py`
- **Session storage**: `session.py` interface is storage-agnostic; could back to SQLite later
