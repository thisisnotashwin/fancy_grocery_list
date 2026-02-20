from __future__ import annotations
import click
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
