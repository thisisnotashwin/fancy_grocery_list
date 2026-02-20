from __future__ import annotations
from pathlib import Path
import click
from pydantic import ValidationError
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
err_console = Console(stderr=True)


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
@click.option(
    "--html", "html_file", default=None, type=click.Path(exists=True),
    help="Path to saved HTML file (for paywalled pages)"
)
def add(html_file: str | None):
    """Add recipe URLs to the current session."""
    manager = SessionManager()
    try:
        session = manager.load_current()
    except FileNotFoundError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    try:
        config = Config()
    except ValidationError:
        err_console.print("[red]Error:[/red] ANTHROPIC_API_KEY environment variable is not set.")
        raise SystemExit(1)
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
            console.print("  Fetching...", end="\r")
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

    total = sum(len(r.raw_ingredients) for r in session.recipes)
    console.print(f"\n[dim]Processing {total} ingredients...[/dim]")
    try:
        all_raw = [
            RawIngredient(text=ing, recipe_title=r.title, recipe_url=r.url)
            for r in session.recipes
            for ing in r.raw_ingredients
        ]
        session.processed_ingredients = process(all_raw, config)
        manager.save(session)
        count = len(session.processed_ingredients)
        console.print(f"[green]✓[/green] Consolidated to [bold]{count}[/bold] ingredients.\n")
        console.print("Run [bold]grocery done[/bold] when you're ready to build your list.")
    except ProcessorError as e:
        console.print(f"[red]Error processing ingredients:[/red] {e}")
        console.print("Your recipes were saved. Try running [bold]grocery add[/bold] again.")
        manager.save(session)


def _add_from_html(session, manager, html_file: str, config: Config) -> None:
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
        err_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    try:
        config = Config()
    except ValidationError:
        err_console.print("[red]Error:[/red] ANTHROPIC_API_KEY environment variable is not set.")
        raise SystemExit(1)

    if not session.processed_ingredients:
        console.print(
            "[yellow]No ingredients found. Run[/yellow] [bold]grocery add[/bold] [yellow]first.[/yellow]"
        )
        return

    session.processed_ingredients = run_pantry_check(session.processed_ingredients)

    need_to_buy = [i for i in session.processed_ingredients if i.confirmed_have is False]
    console.print(f"\n[bold]{len(need_to_buy)}[/bold] items to buy.\n")

    output = format_grocery_list(need_to_buy, config)
    console.print(output)

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
        console.print(
            "Run [bold]grocery add[/bold] to add more recipes, "
            "or [bold]grocery done[/bold] to finalize."
        )
    except FileNotFoundError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
