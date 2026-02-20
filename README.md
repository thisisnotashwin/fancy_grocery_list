# fancy_grocery_list

A CLI that turns recipe URLs into a formatted grocery list, powered by Claude AI.

Paste in recipe URLs, and the tool scrapes ingredients, deduplicates and consolidates them across recipes using Claude, optionally checks your pantry, and outputs a neatly formatted shopping list organized by store section.

## Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`

## Installation

### With uv (recommended)

```bash
git clone <repo-url>
cd fancy_grocery_list
uv sync
```

This installs the `grocery` command into the project's virtual environment.

### With pip

```bash
git clone <repo-url>
cd fancy_grocery_list
pip install -e .
```

### Install globally (editable)

To make `grocery` available system-wide without activating a venv:

```bash
pip install -e .
```

Or with uv:

```bash
uv tool install -e .
```

## Configuration

Create a `.env` file in the project root (or export the variable in your shell):

```bash
ANTHROPIC_API_KEY=your-api-key-here
```

Optional settings (with defaults):

```bash
ANTHROPIC_MODEL=claude-opus-4-6          # Claude model to use
GROCERY_LISTS_DIR=~/.grocery_lists       # Where sessions are stored
```

## Usage

All commands are run via the `grocery` CLI entrypoint.

### Start a new session

```bash
grocery new
grocery new --name "Thanksgiving dinner"
```

### Add recipes

```bash
grocery add
```

You'll be prompted to enter recipe URLs one at a time. Press Enter with no input to stop. Each URL is fetched, scraped, and its ingredients are processed and consolidated.

For paywalled pages, save the HTML locally and pass it directly:

```bash
grocery add --html /path/to/saved-page.html
```

### Finalize the list

```bash
grocery done
```

Runs an interactive pantry check (asking which items you already have), then prints the final grocery list organized by store section. The list is also saved to `~/.grocery_lists/<session-id>.txt`.

### List all sessions

```bash
grocery list
```

Shows a table of all sessions with their status (in progress or finalized).

### Re-open a session

```bash
grocery open
grocery open <session-id>
```

Re-opens a past session so you can add more recipes or re-run `grocery done`.

## Example workflow

```bash
# Start a new session
grocery new --name "Weeknight meals"

# Add a couple of recipes
grocery add
#   Recipe URL: https://example.com/pasta-recipe
#   Recipe URL: https://example.com/chicken-recipe
#   Recipe URL: (press Enter to stop)

# Check what you need to buy
grocery done
```

## Development

Install with dev dependencies:

```bash
uv sync --extra dev
# or
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```
