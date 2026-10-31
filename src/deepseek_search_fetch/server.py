"""MCP server exposing the DeepSeek Search / Fetch API as search and fetch tools.

API reference: https://api-docs.deepseek.com/zh-cn/api/search
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://api.deepseek.com"
SEARCH_ENDPOINT = "/v1/tools/search"
FETCH_ENDPOINT = "/v1/tools/fetch"

USER_AGENT = f"deepseek-search-fetch-mcp/{__version__}"

# Statuses the official guide says to retry after waiting: 408, 429, 5xx.
RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

SEARCH_QUERY_MIN = 1
SEARCH_QUERY_MAX = 128
SEARCH_COUNT_MIN = 1
SEARCH_COUNT_MAX = 50
FETCH_URL_MAX = 8192


class DeepSeekAPIError(Exception):
    """Raised when the DeepSeek Search / Fetch API returns an error."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class DeepSeekClient:
    """Minimal HTTP client for the DeepSeek Search / Fetch API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

    def _error_message(self, status_code: int, body: Any) -> str:
        """Extract the human-readable message from an OpenAI-compatible error body."""
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if body.get("message"):
                return str(body["message"])
        return f"HTTP {status_code}: {body}"

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a JSON payload, retrying transient failures with backoff."""
        url = self.base_url + path
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise DeepSeekAPIError(0, f"Network error contacting {url}: {exc}") from exc

            if response.status_code == 200:
                return response.json()

            if response.status_code in RETRYABLE_STATUSES and attempt < self.max_retries:
                time.sleep(0.5 * (2**attempt))
                continue

            try:
                body = response.json()
            except ValueError:
                body = response.text
            raise DeepSeekAPIError(response.status_code, self._error_message(response.status_code, body))

        assert last_error is not None
        raise DeepSeekAPIError(0, f"Network error contacting {url}: {last_error}")


def _validate_query(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-blank string of 1-128 characters")
    if len(query) > SEARCH_QUERY_MAX:
        raise ValueError(f"query must be at most {SEARCH_QUERY_MAX} characters")
    return query


def _validate_count(count: int) -> int:
    if not SEARCH_COUNT_MIN <= count <= SEARCH_COUNT_MAX:
        raise ValueError(f"count must be between {SEARCH_COUNT_MIN} and {SEARCH_COUNT_MAX}")
    return count


def _validate_url(url: str) -> str:
    if not isinstance(url, str) or not url:
        raise ValueError("url must be a non-empty string")
    if len(url) > FETCH_URL_MAX:
        raise ValueError(f"url must be at most {FETCH_URL_MAX} characters")

    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("url must be an absolute HTTP/HTTPS URL with a host")
    if parts.username or parts.password:
        raise ValueError("url must not contain username or password credentials")
    return url


def build_server(
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 30.0,
    max_retries: int = 3,
) -> MCPServer:
    """Create the MCPServer with the `search` and `fetch` tools."""
    client = DeepSeekClient(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=max_retries)

    mcp = MCPServer(name="deepseek-search-fetch")

    @mcp.tool(description=(
        "Search the web via the DeepSeek Search API. Returns structured results "
        "(title, url, snippet, summary, content, site, date, authority and rerank score). "
        "The query supports operators: site:, -site:, \"exact phrase\", -keyword, "
        "lang:zh,en, after:YYYY-MM-DD, before:YYYY-MM-DD."
    ))
    def search(
        query: str,
        count: int = 10,
        ori_question: str | None = None,
        localization: str = "",
        need_content: bool = False,
    ) -> str:
        """Search the web and return structured results as JSON.

        Args:
            query: Search terms, 1-128 characters. Supports search syntax such as
                site:, -site:, "exact phrase", lang:, after:, before:.
            count: Number of results to return, 1-50 (default 10).
            ori_question: The user's original question that triggered this search,
                1-128 characters, to improve intent understanding.
            localization: An IP address to prefer localized results (default "").
            need_content: Whether to include full page content in each result.
        """
        _validate_query(query)
        _validate_count(count)

        payload: dict[str, Any] = {
            "query": query,
            "count": count,
            "need_content": bool(need_content),
        }
        if ori_question is not None:
            if not 1 <= len(ori_question) <= 128:
                raise ValueError("ori_question must be 1-128 characters")
            payload["ori_question"] = ori_question
        if localization:
            payload["localization"] = localization

        data = client.post(SEARCH_ENDPOINT, payload)
        return json.dumps(data, ensure_ascii=False, indent=2)

    @mcp.tool(description=(
        "Fetch a single web page via the DeepSeek Fetch API and return its title "
        "and full content in Markdown. The URL must be an absolute HTTP/HTTPS URL "
        "with a host and must not contain embedded credentials."
    ))
    def fetch(url: str) -> str:
        """Fetch a web page and return its title and Markdown content.

        Args:
            url: The HTTP/HTTPS URL of the page to fetch, at most 8192 characters.
        """
        _validate_url(url)
        data = client.post(FETCH_ENDPOINT, {"url": url})
        return json.dumps(data, ensure_ascii=False, indent=2)

    return mcp


def main() -> None:
    """Entry point: read configuration from the environment and run the server."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit(
            "DEEPSEEK_API_KEY is required. Set it to your DeepSeek API key "
            "(https://platform.deepseek.com/api_keys) before starting the server."
        )

    base_url = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)

    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, "")) if os.environ.get(name) else default
        except ValueError:
            return default

    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.environ.get(name, "")) if os.environ.get(name) else default
        except ValueError:
            return default

    server = build_server(
        api_key=api_key,
        base_url=base_url,
        timeout=_env_float("DEEPSEEK_TIMEOUT", 30.0),
        max_retries=_env_int("DEEPSEEK_MAX_RETRIES", 3),
    )
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
