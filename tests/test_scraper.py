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
