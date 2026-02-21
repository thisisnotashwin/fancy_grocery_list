# Persistent Pantry & Markdown Output — Design Doc
*2026-02-21*

## Overview

Two extensions to reduce friction in the daily workflow:

1. **Persistent pantry** — a managed list of items you always keep stocked, auto-skipped during pantry check, with self-populating prompts after each session.
2. **Markdown output** — richer, phone-friendly output format using `- [ ]` checkboxes and emoji section headers, compatible with Apple Notes, Notion, Bear, etc.

---

## Feature 1: Persistent Pantry

### Storage

A new `pantry.json` file lives in `~/.grocery_lists/` alongside `staples.json`. It stores items you always keep stocked. A `PantryManager` class mirrors `StapleManager` — same interface, same JSON storage pattern.

```json
[
  {"name": "olive oil", "quantity": ""},
  {"name": "kosher salt", "quantity": ""},
  {"name": "garlic", "quantity": ""}
]
```

### CLI Commands

```
grocery pantry add <name> [quantity]   # Mark an item as always stocked
grocery pantry remove <name>           # Remove from pantry
grocery pantry list                    # Show all pantry items
```

### Auto-skip During Pantry Check

During `grocery done`, before the interactive pantry check runs, the app auto-marks any `ProcessedIngredient` whose name matches a pantry item as `confirmed_have=True`. Those items are silently skipped — the user is never prompted for them. The interactive check only fires for items not in the pantry.

Name matching uses the normalized names Claude already produces (e.g., `"olive oil"`, `"kosher salt"`). No fuzzy matching required.

### Self-Populating After Pantry Check

At the end of the interactive pantry check, the app collects every item the user said "yes" to that isn't already in the pantry, and presents them as a batch prompt:

```
  Pantry check complete.

  You said you have these items — add any to your pantry so you're never asked again?

    1. olive oil
    2. kosher salt
    3. garlic

  Enter numbers to save (e.g. 1 3), or press Enter to skip:
```

Selected items are immediately written to `pantry.json`. This keeps the pantry check flow uninterrupted and ensures the pantry is always opt-in.

### Future Consideration

A `grocery pantry restock <name>` command would temporarily remove an item from the pantry so the user gets prompted for it in the next session (for when pantry stock is running low). Deferred to a later iteration.

### Multi-user Note

Pantry is inherently personal. When multi-user support is added, each user will have their own pantry file. This design does not complicate that extension.

---

## Feature 2: Markdown Output

### New Formatter

A `MarkdownFormatter` is added to `formatter.py` alongside the existing `PlainTextFormatter`. It becomes the new default.

Output format:

```markdown
## 🥦 Produce
- [ ] 3 cloves garlic
- [ ] 1 bunch cilantro

## 🥩 Meat & Seafood
- [ ] 1 lb ground beef

## 🧴 Pantry
- [ ] 1 can crushed tomatoes
- [ ] 2 tbsp olive oil
```

### Section Emoji

Each store section gets a fixed emoji, defined in `config.py` alongside `STORE_SECTIONS`. Example mapping:

| Section | Emoji |
|---|---|
| Produce | 🥦 |
| Meat & Seafood | 🥩 |
| Dairy & Eggs | 🧀 |
| Pantry | 🧴 |
| Frozen | 🧊 |
| Bakery | 🍞 |
| Beverages | 🧃 |
| Other | 🛒 |

### Compatibility

`- [ ]` renders as a native checkbox in Apple Notes, Notion, Bear, and most Markdown-aware apps. It remains perfectly readable as plain text in apps that don't render Markdown.

### Configuration

A `FORMAT` setting in `config.py` controls which formatter is used. Default changes to `"markdown"`. The plain text formatter remains available for users who want to revert.

---

## Components Touched

| File | Change |
|---|---|
| `src/fancy_grocery_list/pantry.py` | Add `PantryManager` class; update `run_pantry_check` to auto-skip pantry items and prompt for self-population |
| `src/fancy_grocery_list/models.py` | Add `PantryItem` model (mirrors `Staple`) |
| `src/fancy_grocery_list/cli.py` | Add `grocery pantry` command group (`add`, `remove`, `list`) |
| `src/fancy_grocery_list/formatter.py` | Add `MarkdownFormatter`; update `format_grocery_list` to dispatch by config |
| `src/fancy_grocery_list/config.py` | Add `SECTION_EMOJI` mapping; add `FORMAT` setting (default `"markdown"`) |
| `tests/test_pantry.py` | Tests for auto-skip and self-population logic |
| `tests/test_formatter.py` | Tests for `MarkdownFormatter` |

---

## Data Flow (Updated)

```
grocery done
  └─▶ load session
        └─▶ auto-mark pantry items as confirmed_have=True   ← new
              └─▶ interactive pantry check (remaining items only)
                    └─▶ batch prompt: add "yes" items to pantry?  ← new
                          └─▶ MarkdownFormatter → stdout + .md file  ← changed
```
