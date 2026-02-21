# Recipe Scaling, List, and Remove Design

**Date:** 2026-02-20

## Goal

Add three capabilities to the fancy grocery list CLI:
1. Scale a recipe's ingredient quantities by a float multiplier when adding it
2. `recipe list` and `item list` commands to inspect the current session
3. `recipe remove <index>` and `item remove <index>` to delete entries from the current session

## Data Model Changes

`RecipeData` gains one field:

```python
scale: float = 1.0
```

Stored in session JSON. Backward-compatible — old sessions without `scale` default to 1.0.

No changes to `GrocerySession` or other models.

## Command Surface

```
grocery recipe add [--html <src>] [--scale <float>]   # NEW: --scale flag (default 1.0)
grocery recipe list                                    # NEW
grocery recipe remove <index>                          # NEW (1-based index)

grocery item add <name> [quantity]                     # existing
grocery item list                                      # NEW
grocery item remove <index>                            # NEW (1-based index)

grocery staple add <name> [quantity]                   # existing (unchanged)
grocery staple list                                    # existing (unchanged)
grocery staple remove <name>                           # existing, by name (global list, not session)
```

## Scaling Behavior

Scale is stored as `RecipeData.scale`. Applied in `_process_all` when building raw ingredients:

```python
for r in session.recipes:
    prefix = f"[×{r.scale}] " if r.scale != 1.0 else ""
    for ing in r.raw_ingredients:
        RawIngredient(text=f"{prefix}{ing}", recipe_title=r.title, recipe_url=r.url)
```

The AI consolidation step receives the scale prefix as free-form context and applies it during quantity reasoning. This avoids brittle quantity parsing.

## List Output Format

`recipe list`:
```
Recipes in current session

  1. Pasta Bolognese           (12 ingredients, ×1)
  2. Chicken Tikka Masala      (18 ingredients, ×2)
```

`item list`:
```
Manually added items

  1. 1 dozen eggs
  2. birthday candles
```

If the session has no recipes / items, print a helpful empty-state message.

## Remove Behavior

- `recipe remove <index>`: removes recipe at 1-based index, then re-runs `_process_all` to keep consolidated list in sync
- `item remove <index>`: removes item at 1-based index from `extra_items` (skipping staple-sourced items), then re-runs `_process_all`
- Out-of-range index: print error, exit 1, no changes made

## Consistency Notes

- `staple remove` uses name (not index) because staples are a global persistent list, not positional
- `recipe remove` and `item remove` use index because they are session-scoped and `list` assigns indices
- Re-consolidation on remove mirrors the behavior of `item add` (which also re-consolidates immediately)

## Files to Change

- `src/fancy_grocery_list/models.py` — add `scale: float = 1.0` to `RecipeData`
- `src/fancy_grocery_list/cli.py` — add `--scale` to `recipe add`; add `recipe list`, `recipe remove`, `item list`, `item remove` commands; update `_process_all` to apply scale prefix
- `tests/test_cli.py` — new tests for all new commands
- `tests/test_models.py` — test `scale` field defaults and backward compat
