# deepseek-search-fetch-mcp

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that exposes the official **DeepSeek Search / Fetch API** as two MCP tools: `search` and `fetch`.

- `search` — search the web with the DeepSeek in-house search engine and get structured results (title, URL, snippet, summary, content, site info, date, authority, rerank score).
- `fetch` — fetch a single web page and return its title and full content in Markdown.

> [简体中文说明（Simplified Chinese）→ README.zh-CN.md](README.zh-CN.md)

## ⚠️ Disclaimer

**This project is an independent, community-built open-source implementation and is NOT affiliated with, endorsed by, or sponsored by DeepSeek (深度求索).**

- "DeepSeek" and related names are trademarks of their respective owners.
- The copyright of this project and all its versions belongs to its holder, **web4theme**.
- This project simply wraps the public DeepSeek Search / Fetch API. You are responsible for your own API usage, billing, and compliance with DeepSeek's terms of service.

## How it works

```
MCP client ──stdio──▶ deepseek-search-fetch-mcp ──HTTPS──▶ api.deepseek.com
                            (search → POST /v1/tools/search
                             fetch  → POST /v1/tools/fetch)
```

The tools call the DeepSeek API endpoints documented at [api-docs.deepseek.com](https://api-docs.deepseek.com/zh-cn/api/search):

| Tool    | Endpoint                     |
| --------| ---------------------------- |
| `search`| `POST https://api.deepseek.com/v1/tools/search` |
| `fetch` | `POST https://api.deepseek.com/v1/tools/fetch`  |

## Tools

### `search`

Search the web and return structured results as JSON.

| Parameter      | Type     | Required | Default | Description |
| -------------- | -------- | -------- | ------- | ----------- |
| `query`        | string   | ✅       | —       | Search terms, 1–128 characters, must not be blank. Supports search syntax (see below). |
| `count`        | integer  | —        | `10`    | Number of results, 1–50. |
| `ori_question` | string   | —        | `null`  | The user's original question that triggered the search, 1–128 characters, improves intent understanding. |
| `localization` | string   | —        | `""`    | An IP address to prefer localized results. |
| `need_content` | boolean  | —        | `false` | Include full page content in each result. |

Each result contains: `rerank_score`, `title`, `url`, `snippet`, `summary`, `content`, `site_name`, `site_icon`, `date` (RFC 3339 UTC), `authority`.

### `fetch`

Fetch a web page and return its title and Markdown content.

| Parameter | Type   | Required | Description |
| --------- | -------- | -------- | ----------- |
| `url`     | string | ✅       | The HTTP/HTTPS URL to fetch, at most 8192 characters, must include a host and must not contain embedded credentials. |

## Search syntax

The `query` supports the following operators (pass them to `search` exactly as documented by DeepSeek):

| Operator | Example | Description |
| -------- | ------- | ----------- |
| `site:`  | `DeepSeek site:github.com` | Limit results to a site. Combine multiple with `OR`, e.g. `site:github.com OR site:huggingface.co`. |
| `-site:` | `DeepSeek -site:example.com` | Exclude a site. |
| `-`      | `DeepSeek -广告` | Exclude pages containing a keyword. |
| `-"..."` | `DeepSeek -"release notes"` | Exclude pages containing a phrase. |
| `"..."`  | `DeepSeek "精确短语"` | Exact phrase match. |
| `lang:`  | `DeepSeek lang:zh,en` | Limit results to languages (comma-separated). |
| `after:` | `DeepSeek after:2025-01-01` | Only pages published after a date. |
| `before:`| `DeepSeek before:2026-06-01` | Only pages published before a date. |

Example: `query="DeepSeek site:github.com OR site:huggingface.co lang:zh after:2025"`.

## Requirements

- Python 3.10+
- A DeepSeek API key ([platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys))
- [uv](https://docs.astral.sh/uv/) (recommended) or `pip`

## Installation

### Option A — clone and run with uv (recommended)

```bash
git clone https://github.com/web4theme/deepseek-search-fetch-mcp.git
cd deepseek-search-fetch-mcp
uv sync
```

### Option B — pip

```bash
git clone https://github.com/web4theme/deepseek-search-fetch-mcp.git
cd deepseek-search-fetch-mcp
pip install .
```

## Configuration

Set the environment variables before starting the server:

| Variable                  | Required | Default                | Description |
| ------------------------- | -------- | ---------------------- | ----------- |
| `DEEPSEEK_API_KEY`        | ✅       | —                      | Your DeepSeek API key. |
| `DEEPSEEK_BASE_URL`       | —        | `https://api.deepseek.com` | Override the API base URL (e.g. a proxy). |
| `DEEPSEEK_TIMEOUT`        | —        | `30`                   | HTTP timeout in seconds. |
| `DEEPSEEK_MAX_RETRIES`    | —        | `3`                    | Retries for transient failures (HTTP 408/429/5xx), with exponential backoff. |

## Usage with MCP clients

### Claude Code

```bash
claude mcp add deepseek-search-fetch -- \
  uv run --directory /path/to/deepseek-search-fetch-mcp deepseek-search-fetch
```

### Cursor / other stdio clients

Add to your MCP client configuration (JSON):

```json
{
  "mcpServers": {
    "deepseek-search-fetch": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/deepseek-search-fetch-mcp", "deepseek-search-fetch"],
      "env": {
        "DEEPSEEK_API_KEY": "your-api-key"
      }
    }
  }
}
```

> Note: tool names are `search` and `fetch`, which may collide with tools from other MCP servers. If you run multiple search MCP servers, rename the tools in this repo (they are registered in `src/deepseek_search_fetch/server.py`) or namespace them in your client.

## Error handling

The server surfaces the API's errors (OpenAI-compatible format) with their HTTP status code:

| Status | Meaning |
| ------ | ------- |
| 400 | Invalid request headers/body or field values. |
| 401 | Missing or invalid API key. |
| 402 | Insufficient account balance. |
| 403 | Fetch request rejected by security policy. |
| 404 | Fetch could not obtain usable page content. |
| 408 | Request body read timeout. |
| 413 | Request body too large. |
| 429 | QPS limit exceeded (Search: 100 QPS, Fetch: 25 QPS per account). |
| 500 | Server internal error. |
| 504 | Downstream request timeout. |

The client automatically retries 408/429/5xx with exponential backoff (up to `DEEPSEEK_MAX_RETRIES`). Other 4xx errors are not retried, per DeepSeek's guidance.

## Billing & rate limits (per DeepSeek docs)

- Both Search and Fetch are billed **per successful request**: ¥5 per 1,000 successful requests (Search) and ¥5 per 1,000 (Fetch). Requests that fail, return no results, or time out are **not** billed. `count` does not affect the price.
- Rate limits are per account: Search **100 QPS**, Fetch **25 QPS**, independent of each other.

See the official [Web Search & Fetch guide](https://api-docs.deepseek.com/zh-cn/guides/search) for the latest information.

## Development

```bash
uv sync
# Run the server on stdio (requires DEEPSEEK_API_KEY):
DEEPSEEK_API_KEY=sk-... uv run deepseek-search-fetch
# Or invoke as a module:
DEEPSEEK_API_KEY=sk-... uv run python -m deepseek_search_fetch
```

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 **web4theme**.
