import pytest
import httpx
from pytest_httpx import HTTPXMock
from fancy_grocery_list.fetcher import fetch, FetchError


def test_fetch_returns_html(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="https://www.seriouseats.com/recipe", text="<html>recipe</html>")
    html = fetch("https://www.seriouseats.com/recipe")
    assert html == "<html>recipe</html>"


def test_fetch_paywall_raises_fetch_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="https://cooking.nytimes.com/recipe", status_code=401)
    with pytest.raises(FetchError, match="paywall"):
        fetch("https://cooking.nytimes.com/recipe")


def test_fetch_404_raises_fetch_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="https://example.com/gone", status_code=404)
    with pytest.raises(FetchError, match="not found"):
        fetch("https://example.com/gone")


def test_fetch_network_error_raises_fetch_error(httpx_mock: HTTPXMock):
    httpx_mock.add_exception(httpx.ConnectError("failed"))
    with pytest.raises(FetchError, match="Could not connect"):
        fetch("https://example.com/recipe")


def test_fetch_sends_browser_headers(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="https://example.com/recipe", text="<html></html>")
    fetch("https://example.com/recipe")
    request = httpx_mock.get_requests()[0]
    assert "Mozilla" in request.headers["user-agent"]
