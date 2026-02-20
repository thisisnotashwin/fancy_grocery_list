from __future__ import annotations
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode
from fancy_grocery_list.models import RecipeData


class ScrapeError(Exception):
    pass


def scrape(html: str, url: str) -> RecipeData:
    try:
        scraper = scrape_html(html, org_url=url, supported_only=False)
        ingredients = scraper.ingredients()
        if not ingredients:
            raise ScrapeError(f"No ingredients found at {url}. The page may not contain a recipe.")
        title = scraper.title() or url
        return RecipeData(title=title, url=url, raw_ingredients=ingredients)
    except (WebsiteNotImplementedError, NoSchemaFoundInWildMode):
        raise ScrapeError(
            f"Could not parse recipe from {url}. "
            "Try saving the page HTML and using: grocery add --html path/to/saved.html"
        )
    except ScrapeError:
        raise
    except Exception as e:
        raise ScrapeError(f"Unexpected error scraping {url}: {e}") from e
