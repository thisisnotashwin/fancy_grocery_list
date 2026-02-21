from __future__ import annotations
import json
from pathlib import Path
import click
from rich.console import Console
from fancy_grocery_list.models import ProcessedIngredient, PantryItem

console = Console()


class PantryManager:
    def __init__(self, base_dir: Path | None = None):
        self._path = (base_dir or (Path.home() / ".grocery_lists")) / "pantry.json"

    def list(self) -> list[PantryItem]:
        if not self._path.exists():
            return []
        return [PantryItem.model_validate(p) for p in json.loads(self._path.read_text())]

    def add(self, name: str, quantity: str = "") -> None:
        items = self.list()
        if not any(p.name == name for p in items):
            items.append(PantryItem(name=name, quantity=quantity))
            self._save(items)

    def remove(self, name: str) -> None:
        self._save([p for p in self.list() if p.name != name])

    def names(self) -> set[str]:
        return {p.name for p in self.list()}

    def _save(self, items: list[PantryItem]) -> None:
        self._path.write_text(json.dumps([p.model_dump() for p in items], indent=2))


def run_pantry_check(
    ingredients: list[ProcessedIngredient],
    pantry_names: set[str] | None = None,
) -> list[ProcessedIngredient]:
    # Auto-mark pantry items without prompting
    if pantry_names:
        for ingredient in ingredients:
            if ingredient.confirmed_have is None and ingredient.name in pantry_names:
                ingredient.confirmed_have = True

    to_check = [i for i in ingredients if i.confirmed_have is None]

    if not to_check:
        return ingredients

    console.print(f"\n[bold]Pantry check:[/bold] {len(to_check)} ingredient(s) to confirm\n")

    for ingredient in to_check:
        while True:
            answer = click.prompt(
                f"  Do you have {ingredient.quantity} {ingredient.name}? (y/n)"
            ).strip().lower()
            if answer in ("y", "yes"):
                ingredient.confirmed_have = True
                break
            elif answer in ("n", "no"):
                ingredient.confirmed_have = False
                break
            else:
                console.print("  [yellow]Please enter y or n[/yellow]")

    return ingredients
