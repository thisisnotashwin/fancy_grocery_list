from __future__ import annotations
import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class FetchError(Exception):
    pass


def fetch(url: str) -> str:
    try:
        response = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
    except httpx.ConnectError:
        raise FetchError(f"Could not connect to {url}. Check your internet connection.")
    except httpx.TimeoutException:
        raise FetchError(f"Request to {url} timed out.")

    if response.status_code in (401, 403):
        raise FetchError(
            f"This page appears to be behind a paywall or requires login ({response.status_code}). "
            "To use a paywalled recipe, save the page HTML from your browser "
            "and run: grocery add --html path/to/saved.html"
        )
    if response.status_code == 404:
        raise FetchError(f"Page not found (404): {url}")
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code} error fetching {url}")

    return response.text
