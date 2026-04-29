# AdMob MCP Server

基于 [Model Context Protocol](https://modelcontextprotocol.io/) 的 AdMob 分析服务，让 Claude 直接查询你的 AdMob 广告收益数据。

## 功能

提供以下 MCP Tools：

### 报告与基础查询

| Tool | 说明 |
|------|------|
| `list_accounts` | 列出所有 AdMob 发布者账户 |
| `get_account` | 获取指定账户详情 |
| `list_apps` | 列出账户下所有应用 |
| `list_ad_units` | 列出所有广告单元 |
| `fetch_network_report` | 生成网络报告（收入、展示、点击等，支持自定义维度和指标） |
| `fetch_mediation_report` | 生成中介报告（按广告源查看表现） |
| `fetch_revenue` | 快捷查询：按日汇总广告收入 |

### Mediation 管理（v1beta，需账户白名单）

| Tool | 说明 |
|------|------|
| `list_mediation_groups` | 列出账户下所有 Mediation Group |
| `create_mediation_group` | 创建 Mediation Group（写）|
| `update_mediation_group` | 更新 Mediation Group（PATCH，写）|
| `create_mediation_ab_experiment` | 在指定 Group 下创建 A/B 实验（写）|
| `stop_mediation_ab_experiment` | 停止 A/B 实验并选择要保留的变体（写）|
| `list_ad_unit_mappings` | 列出某 Ad Unit 下的第三方广告源映射 |
| `create_ad_unit_mapping` | 创建单个 Ad Unit Mapping（写）|
| `batch_create_ad_unit_mappings` | 批量创建 Ad Unit Mappings（写）|
| `list_ad_sources` | 列出账户可用的 Ad Source（含 adSourceId）|
| `list_adapters` | 列出指定 Ad Source 下的 Adapter 元数据 |

> 上述接口需要 AdMob 团队为账户开通白名单。读取使用 `admob.readonly`，写入需要
> `admob.monetization` scope，旧 token 仅含读权限的请重新运行 `python auth_flow.py` 重新授权。
>
> ⚠ AdMob v1beta 有不少官方文档没明说的接口缺口与字段限制（如 `mediationAbExperiments`
> 没有 list/get、`adUnitMappings` 没有 update/delete、`update_mediation_group` 不能 patch
> `mediationGroupLines` 等）。做需求评估前请查 [docs/admob-api-gaps.md](docs/admob-api-gaps.md)。

## 前置条件

- Python >= 3.10
- Google Cloud 项目，已启用 [AdMob API](https://console.cloud.google.com/apis/library/admob.googleapis.com)
- OAuth 2.0 Client ID（Desktop 类型）

## 安装

```bash
# 克隆项目
git clone git@github.com:SueeiiiZhu/admob-mcp.git
cd admob-mcp

# 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

pip install -e .
```

或使用 [uv](https://docs.astral.sh/uv/)（推荐）：

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

### 依赖清单

| 包名 | 用途 |
|------|------|
| `mcp[cli]` | MCP SDK + CLI 工具（含 uvicorn、starlette） |
| `google-api-python-client` | Google API 客户端（AdMob API v1） |
| `google-auth` | Google OAuth2 认证 |
| `google-auth-oauthlib` | OAuth2 授权流程（仅首次授权时需要） |
| `python-dotenv` | 从 `.env` 文件加载环境变量 |

## 配置

### 1. 获取 OAuth 授权令牌

首次使用需要完成 OAuth 授权：

```bash
# 将 OAuth Client ID 密钥放到 credentials 目录
cp /path/to/client_secret.json credentials/client_secret.json

# 运行授权流程（会打开浏览器）
python auth_flow.py
```

授权完成后会生成 `credentials/token.pickle`。

如果你已有 `token.pickle` 文件，直接复制即可：

```bash
cp /path/to/token.pickle credentials/token.pickle
```

### 2. 设置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# 必填
GOOGLE_TOKEN_FILE=credentials/token.pickle
ADMOB_ACCOUNT_ID=pub-XXXXXXXXXXXXXXXX

# 可选（HTTP 模式）
MCP_HOST=127.0.0.1
MCP_PORT=8000
```

## 运行

### stdio 模式（默认，用于 Claude Desktop / Claude Code）

```bash
python server.py
```

### HTTP 模式（用于远程调用 / 常驻后台）

```bash
python server.py --transport streamable-http
# 监听 http://127.0.0.1:8000/mcp
```

### SSE 模式（旧版兼容）

```bash
python server.py --transport sse
```

## 接入 Claude

### Claude Code（`.mcp.json`）

```json
{
  "mcpServers": {
    "admob": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["server.py"],
      "env": {
        "GOOGLE_TOKEN_FILE": "credentials/token.pickle",
        "ADMOB_ACCOUNT_ID": "pub-XXXXXXXXXXXXXXXX"
      }
    }
  }
}
```

### Claude Desktop

将以下内容添加到 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "admob": {
      "command": "/absolute/path/to/admob-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/admob-mcp/server.py"],
      "env": {
        "GOOGLE_TOKEN_FILE": "/absolute/path/to/credentials/token.pickle",
        "ADMOB_ACCOUNT_ID": "pub-XXXXXXXXXXXXXXXX"
      }
    }
  }
}
```

### HTTP 模式接入

先启动 HTTP 服务，然后配置：

```json
{
  "mcpServers": {
    "admob": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## 系统服务部署

`examples/` 目录提供了启动配置模板：

- `admob-mcp.service` — systemd（Linux）
- `com.admob-mcp.plist` — launchd（macOS）
- `claude_desktop_config.json` — Claude Desktop

## 调试

```bash
# MCP Inspector（交互式测试）
npx @modelcontextprotocol/inspector python server.py

# FastMCP 开发模式
fastmcp dev server.py:mcp
```

## 许可证

MIT
