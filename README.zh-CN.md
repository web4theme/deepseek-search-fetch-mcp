# deepseek-search-fetch-mcp

一个 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 服务器，将官方 **DeepSeek 网页搜索与抓取（Search / Fetch）API** 封装为两个 MCP 工具：`search` 和 `fetch`。

- `search` — 使用 DeepSeek 自研搜索引擎检索网页，返回结构化结果（标题、链接、短摘要、长摘要、正文、站点信息、发布时间、权威性、排序分数）。
- `fetch` — 抓取单个网页，返回页面标题与完整的 Markdown 正文。

> [English documentation → README.md](README.md)

## ⚠️ 免责声明

**本项目是独立的社区开源实现，与 DeepSeek（深度求索）官方无关，未经官方认可、背书或赞助。**

- “DeepSeek” 及相关名称均为其各自权利人的商标。
- 本项目及所有版本的版权归其持有人 **web4theme** 所有。
- 本项目仅是对 DeepSeek 公开 Search / Fetch API 的封装。您需自行承担 API 使用、费用结算及对 DeepSeek 服务条款的合规责任。

## 工作原理

```
MCP 客户端 ──stdio──▶ deepseek-search-fetch-mcp ──HTTPS──▶ api.deepseek.com
                          (search → POST /v1/tools/search
                           fetch  → POST /v1/tools/fetch)
```

本工具调用 DeepSeek 官方文档（[api-docs.deepseek.com](https://api-docs.deepseek.com/zh-cn/api/search)）中定义的接口：

| 工具     | 接口                              |
| -------- | --------------------------------- |
| `search` | `POST https://api.deepseek.com/v1/tools/search` |
| `fetch`  | `POST https://api.deepseek.com/v1/tools/fetch`  |

## 工具说明

### `search`

按关键词搜索网页，以 JSON 返回结构化结果。

| 参数           | 类型     | 必填 | 默认值   | 说明 |
| -------------- | -------- | ---- | -------- | ---- |
| `query`        | string   | ✅   | —        | 搜索词，1～128 个字符，不能全为空白，支持搜索语法（见下）。 |
| `count`        | integer  | —    | `10`     | 返回条数，1～50。 |
| `ori_question` | string   | —    | `null`   | 触发搜索的用户原始问题，1～128 个字符，有助于理解搜索意图。 |
| `localization` | string   | —    | `""`     | 用于优先返回本地化搜索结果的 IP 地址。 |
| `need_content` | boolean  | —    | `false`  | 是否在结果中返回网页正文。 |

每条结果包含：`rerank_score`、`title`、`url`、`snippet`、`summary`、`content`、`site_name`、`site_icon`、`date`（UTC RFC 3339）、`authority`。

### `fetch`

抓取网页，返回页面标题与 Markdown 正文。

| 参数  | 类型   | 必填 | 说明 |
| ----- | ------ | ---- | ---- |
| `url` | string | ✅   | 要抓取的网页地址，长度不超过 8192，必须为含 host 的 HTTP/HTTPS URL，且不能携带用户名或密码。 |

## 搜索语法

`query` 支持以下操作符（按 DeepSeek 官方文档原样传递即可）：

| 操作符   | 示例 | 说明 |
| -------- | ---- | ---- |
| `site:`  | `DeepSeek site:github.com` | 将结果限制在指定站点；多个站点用 `OR` 连接，如 `site:github.com OR site:huggingface.co`。 |
| `-site:` | `DeepSeek -site:example.com` | 排除指定站点。 |
| `-`      | `DeepSeek -广告` | 排除包含指定关键词的网页。 |
| `-"..."` | `DeepSeek -"release notes"` | 排除包含指定短语的网页。 |
| `"..."`  | `DeepSeek "精确短语"` | 精确匹配指定短语。 |
| `lang:`  | `DeepSeek lang:zh,en` | 将结果限制在指定语言（逗号分隔）。 |
| `after:` | `DeepSeek after:2025-01-01` | 仅返回指定日期之后发布的网页。 |
| `before:`| `DeepSeek before:2026-06-01` | 仅返回指定日期之前发布的网页。 |

示例：`query="DeepSeek site:github.com OR site:huggingface.co lang:zh after:2025"`。

## 环境要求

- Python 3.10 及以上
- DeepSeek API Key（[platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)）
- [uv](https://docs.astral.sh/uv/)（推荐）或 `pip`

## 安装

### 方式 A — 克隆后使用 uv 运行（推荐）

```bash
git clone https://github.com/web4theme/deepseek-search-fetch-mcp.git
cd deepseek-search-fetch-mcp
uv sync
```

### 方式 B — pip

```bash
git clone https://github.com/web4theme/deepseek-search-fetch-mcp.git
cd deepseek-search-fetch-mcp
pip install .
```

## 环境变量配置

启动服务器前设置以下环境变量：

| 变量                  | 必填 | 默认值                       | 说明 |
| --------------------- | ---- | ---------------------------- | ---- |
| `DEEPSEEK_API_KEY`    | ✅   | —                            | 你的 DeepSeek API Key。 |
| `DEEPSEEK_BASE_URL`   | —    | `https://api.deepseek.com`   | 覆盖 API 基础地址（如代理）。 |
| `DEEPSEEK_TIMEOUT`    | —    | `30`                         | HTTP 超时（秒）。 |
| `DEEPSEEK_MAX_RETRIES`| —    | `3`                          | 对临时性错误（HTTP 408/429/5xx）的重试次数，指数退避。 |

## MCP 客户端接入

### Claude Code

```bash
claude mcp add deepseek-search-fetch -- \
  uv run --directory /path/to/deepseek-search-fetch-mcp deepseek-search-fetch
```

### Cursor / 其他 stdio 客户端

在 MCP 客户端配置（JSON）中添加：

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

> 提示：工具名为 `search` 和 `fetch`，可能与其他 MCP 服务器中的同名工具冲突。若同时接入多个搜索类 MCP，可修改 `src/deepseek_search_fetch/server.py` 中注册的工具名，或在客户端中做命名空间隔离。

## 错误处理

服务器会透出 API 的错误信息（OpenAI 兼容格式）及对应 HTTP 状态码：

| 状态码 | 含义 |
| ------ | ---- |
| 400 | 请求头或请求体不合法，包括字段值无效。 |
| 401 | API Key 缺失或无效。 |
| 402 | 账号余额不足。 |
| 403 | Fetch 请求被安全策略拒绝。 |
| 404 | Fetch 未能获取可用的网页内容。 |
| 408 | 读取请求体超时。 |
| 413 | 请求体超过大小限制。 |
| 429 | 超过 QPS 限制（Search：100 QPS，Fetch：25 QPS，按账号计算）。 |
| 500 | 服务器内部错误。 |
| 504 | 下游请求超时。 |

客户端会自动对 408/429/5xx 进行指数退避重试（最多 `DEEPSEEK_MAX_RETRIES` 次）；其他 4xx 错误按官方指引不做重试。

## 计费与限速（依据 DeepSeek 官方文档）

- Search 与 Fetch 均**按成功请求次数计费**：Search 每 1,000 次成功请求 5 元，Fetch 每 1,000 次成功请求 5 元。请求失败、无结果或超时**不计费**；`count` 只影响返回条数，不影响单次价格。
- 限速按账号粒度：Search **100 QPS**、Fetch **25 QPS**，两者相互独立。

最新信息请以官方[网页搜索与抓取指南](https://api-docs.deepseek.com/zh-cn/guides/search)为准。

## 开发

```bash
uv sync
# 以 stdio 方式运行服务器（需设置 DEEPSEEK_API_KEY）：
DEEPSEEK_API_KEY=sk-... uv run deepseek-search-fetch
# 或以模块方式运行：
DEEPSEEK_API_KEY=sk-... uv run python -m deepseek_search_fetch
```

## 许可证

MIT — 详见 [LICENSE](LICENSE)。版权所有 (c) 2026 **web4theme**。
