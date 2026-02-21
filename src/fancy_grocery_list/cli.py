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
from fancy_grocery_list.staples import StapleManager

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
    console.print("Run [bold]grocery recipe add[/bold] to add recipes.\n")


@cli.group("recipe")
def recipe():
    """Manage recipes in the current session."""
    pass


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

    if html_source:
        _add_from_html(session, manager, html_source, config, scale=scale)
        return

    while True:
        url = click.prompt("  Recipe URL", default="", show_default=False).strip()
        if not url:
            break
        try:
            console.print("  Fetching...", end="\r")
            html = fetch(url)
            recipe_data = scrape(html, url)
            recipe_data.scale = scale
            session.recipes.append(recipe_data)
            added_count += 1
            console.print(f"  [green]✓[/green] {recipe_data.title} ({len(recipe_data.raw_ingredients)} ingredients)")
        except (FetchError, ScrapeError) as e:
            console.print(f"  [red]✗[/red] {e}")

    if added_count == 0:
        console.print("\nNo recipes added.")
        return

    total = sum(len(r.raw_ingredients) for r in session.recipes)
    console.print(f"\n[dim]Processing {total} ingredients...[/dim]")
    try:
        _process_all(session, manager, config)
        count = len(session.processed_ingredients)
        console.print(f"[green]✓[/green] Consolidated to [bold]{count}[/bold] ingredients.\n")
        console.print("Run [bold]grocery done[/bold] when you're ready to build your list.")
    except ProcessorError as e:
        console.print(f"[red]Error processing ingredients:[/red] {e}")
        console.print("Your recipes were saved. Try running [bold]grocery recipe add[/bold] again.")
        manager.save(session)


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


@cli.group("item")
def item():
    """Manage manually added items in the current session."""
    pass


@item.command("add")
@click.argument("name")
@click.argument("quantity", default="")
def item_add(name: str, quantity: str):
    """Add an item to the current session by name and quantity."""
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

    text = f"{quantity} {name}".strip()
    session.extra_items.append(RawIngredient(text=text, recipe_title="[added manually]", recipe_url=""))
    console.print(f"  [green]✓[/green] Added: {text}")

    console.print("[dim]Processing ingredients...[/dim]")
    try:
        _process_all(session, manager, config)
        console.print(f"[green]✓[/green] Consolidated to {len(session.processed_ingredients)} ingredients.")
    except ProcessorError as e:
        console.print(f"[red]Error processing ingredients:[/red] {e}")
        manager.save(session)


@cli.group("staple")
def staple():
    """Manage your persistent staples list."""
    pass


@staple.command("add")
@click.argument("name")
@click.argument("quantity", default="")
def staple_add(name: str, quantity: str):
    """Add an item to your staples list (auto-added to every new session)."""
    StapleManager().add(name, quantity)
    label = f"{quantity} {name}".strip()
    console.print(f"[green]✓[/green] Added staple: [bold]{label}[/bold]")


@staple.command("remove")
@click.argument("name")
def staple_remove(name: str):
    """Remove an item from your staples list."""
    StapleManager().remove(name)
    console.print(f"[green]✓[/green] Removed staple: [bold]{name}[/bold]")


@staple.command("list")
def staple_list():
    """Show all staples that are added to every new session."""
    staples = StapleManager().list()
    if not staples:
        console.print("No staples configured. Use [bold]grocery staple add[/bold] to add some.")
        return
    console.print("\n[bold]Staples[/bold] (added to every new session)\n")
    for s in staples:
        label = f"{s.quantity} {s.name}".strip()
        console.print(f"  • {label}")
    console.print()


def _add_from_html(session, manager, html_source: str, config: Config, scale: float = 1.0) -> None:
    if html_source.startswith("http://") or html_source.startswith("https://"):
        url = html_source
        try:
            html = fetch(url)
        except FetchError as e:
            console.print(f"  [red]✗[/red] {e}")
            return
    else:
        html = Path(html_source).read_text()
        url = click.prompt("  URL for this page (for reference)", default="https://unknown").strip()
    try:
        recipe_data = scrape(html, url)
        recipe_data.scale = scale
        session.recipes.append(recipe_data)
        console.print(f"  [green]✓[/green] {recipe_data.title} ({len(recipe_data.raw_ingredients)} ingredients)")
        _process_all(session, manager, config)
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
            "[yellow]No ingredients found. Run[/yellow] [bold]grocery recipe add[/bold] [yellow]first.[/yellow]"
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
            "Run [bold]grocery recipe add[/bold] to add more recipes, "
            "or [bold]grocery done[/bold] to finalize."
        )
    except FileNotFoundError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
