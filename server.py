import argparse
import os
import re
import sys
import json
import logging
from decimal import Decimal
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

load_dotenv()

# All logging to stderr — stdout is reserved for MCP STDIO transport
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("admob-mcp")

mcp = FastMCP(
    "AdMob-Analyst",
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_PORT", "8000")),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "localhost:*",
            "127.0.0.1:*",
            "admob-mcp.boostvision.net",
            "admob-mcp.boostvision.net:*",
        ],
    ),
)


def _get_account_id(account_id: str = "") -> str:
    """Get account ID from parameter or env var, strip 'accounts/' prefix if present."""
    aid = (account_id or os.getenv("ADMOB_ACCOUNT_ID", "")).strip()
    if not aid:
        raise ValueError(
            "account_id not provided and ADMOB_ACCOUNT_ID env var not set. "
            "Run list_accounts first to find your account ID."
        )
    return aid


def _parse_csv_enum(raw: str) -> list[str]:
    """Parse comma-separated enum string, auto upper-case."""
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _tool_error(exc: Exception) -> str:
    """Format sanitized error response for MCP tools.

    Strips internal paths and sensitive details before returning to caller.
    Full stack trace is only written to stderr via logger.exception().
    """
    try:
        from googleapiclient.errors import HttpError

        if isinstance(exc, HttpError):
            return json.dumps(
                {
                    "ok": False,
                    "status": exc.resp.status,
                    "detail": exc.reason,
                },
                ensure_ascii=False,
            )
    except ImportError:
        pass

    # Sanitize: strip file system paths from error message
    msg = str(exc)
    msg = re.sub(r"[~/\\][\w~/\\\-. ]+", "<path>", msg)
    return json.dumps(
        {"ok": False, "error_type": type(exc).__name__, "detail": msg},
        ensure_ascii=False,
    )


# ── Account Management Tools ──


@mcp.tool()
def list_accounts() -> str:
    """列出所有 AdMob 发布者账户，返回账户 ID 和名称列表"""
    try:
        from auth import get_admob_service
        from admob_api import list_accounts as _list_accounts

        service = get_admob_service()
        result = _list_accounts(service)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("list_accounts failed")
        return _tool_error(e)


@mcp.tool()
def get_account(account_id: str) -> str:
    """获取指定 AdMob 账户的详细信息"""
    try:
        from auth import get_admob_service
        from admob_api import get_account as _get_account

        service = get_admob_service()
        result = _get_account(service, account_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("get_account failed")
        return _tool_error(e)


@mcp.tool()
def list_apps(account_id: str = "") -> str:
    """列出账户下所有已注册的应用"""
    try:
        from auth import get_admob_service
        from admob_api import list_apps as _list_apps

        service = get_admob_service()
        aid = _get_account_id(account_id)
        result = _list_apps(service, aid)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("list_apps failed")
        return _tool_error(e)


@mcp.tool()
def list_ad_units(account_id: str = "") -> str:
    """列出账户下所有广告单元（Banner、插屏、激励视频等）"""
    try:
        from auth import get_admob_service
        from admob_api import list_ad_units as _list_ad_units

        service = get_admob_service()
        aid = _get_account_id(account_id)
        result = _list_ad_units(service, aid)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("list_ad_units failed")
        return _tool_error(e)


# ── Report Tools ──


@mcp.tool()
def fetch_network_report(
    days: int = 7,
    dimensions: str = "DATE",
    metrics: str = "",
    account_id: str = "",
    currency: str = "USD",
    max_rows: int = 100000,
) -> str:
    """生成 AdMob 网络报告。
    维度(dimensions): DATE, MONTH, WEEK, AD_UNIT, APP, AD_TYPE, COUNTRY, FORMAT, PLATFORM（逗号分隔）。
    指标(metrics): ESTIMATED_EARNINGS, IMPRESSIONS, CLICKS, AD_REQUESTS, IMPRESSION_CTR, IMPRESSION_RPM, MATCHED_REQUESTS, MATCH_RATE, SHOW_RATE（逗号分隔，留空使用默认全部指标）。"""
    try:
        from auth import get_admob_service
        from admob_api import generate_network_report

        service = get_admob_service()
        aid = _get_account_id(account_id)
        dim_list = _parse_csv_enum(dimensions)
        met_list = _parse_csv_enum(metrics) or None

        result = generate_network_report(
            service,
            aid,
            days=days,
            dimensions=dim_list,
            metrics=met_list,
            currency_code=currency,
            max_rows=max_rows,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("fetch_network_report failed")
        return _tool_error(e)


@mcp.tool()
def fetch_mediation_report(
    days: int = 7,
    dimensions: str = "DATE,AD_SOURCE",
    metrics: str = "",
    account_id: str = "",
    currency: str = "USD",
    max_rows: int = 100000,
) -> str:
    """生成 AdMob 中介报告，按广告源查看表现。
    维度(dimensions): DATE, MONTH, WEEK, AD_SOURCE, AD_SOURCE_INSTANCE, AD_UNIT, APP, COUNTRY, FORMAT, PLATFORM（逗号分隔）。
    指标(metrics): ESTIMATED_EARNINGS, IMPRESSIONS, CLICKS, MATCHED_REQUESTS, OBSERVED_ECPM（逗号分隔，留空使用默认指标）。"""
    try:
        from auth import get_admob_service
        from admob_api import generate_mediation_report

        service = get_admob_service()
        aid = _get_account_id(account_id)
        dim_list = _parse_csv_enum(dimensions)
        met_list = _parse_csv_enum(metrics) or None

        result = generate_mediation_report(
            service,
            aid,
            days=days,
            dimensions=dim_list,
            metrics=met_list,
            currency_code=currency,
            max_rows=max_rows,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("fetch_mediation_report failed")
        return _tool_error(e)


@mcp.tool()
def fetch_revenue(days: int = 7, account_id: str = "", currency: str = "USD") -> str:
    """快捷查询：获取指定天数的每日广告收入汇总，返回每日明细和总计"""
    try:
        from auth import get_admob_service
        from admob_api import generate_network_report

        service = get_admob_service()
        aid = _get_account_id(account_id)

        report = generate_network_report(
            service,
            aid,
            days=days,
            dimensions=["DATE"],
            metrics=["ESTIMATED_EARNINGS"],
            currency_code=currency,
        )

        total = sum(
            Decimal(row.get("ESTIMATED_EARNINGS", "0"))
            for row in report["rows"]
        )
        result = {
            "total_earnings": str(total),
            "currency": currency,
            "days": days,
            "matching_row_count": report["matching_row_count"],
            "warnings": report["warnings"],
            "daily_breakdown": report["rows"],
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("fetch_revenue failed")
        return _tool_error(e)


# ── v1beta Mediation 管理工具（白名单接口）──


def _parse_json_arg(name: str, raw: str) -> dict:
    """Parse a JSON object string argument; raise ValueError with a helpful message."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError(f"{name} must be a non-empty JSON object string")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"{name} is not valid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise ValueError(f"{name} must be a JSON object")
    return obj


_MG_DEFAULT_FIELDS = (
    "mediationGroups("
    "name,mediationGroupId,displayName,state,mediationAbExperimentState,targeting"
    "),nextPageToken"
)


def _compose_mg_filter(
    state: str,
    platform: str,
    ad_format: str,
    extra: str,
) -> Optional[str]:
    """Compose AdMob mediationGroups list filter from convenience args + raw expr.

    AdMob v1beta only supports STATE / PLATFORM / FORMAT as filter fields; any
    other field (e.g. AD_UNIT_ID, MEDIATION_GROUP_ID) is rejected with HTTP 400.
    """
    parts: list[str] = []
    if state:
        parts.append(f'STATE = "{state.strip().upper()}"')
    if platform:
        parts.append(f'PLATFORM = "{platform.strip().upper()}"')
    if ad_format:
        parts.append(f'FORMAT = "{ad_format.strip().upper()}"')
    if extra:
        parts.append(f"({extra.strip()})")
    return " AND ".join(parts) if parts else None


@mcp.tool()
def list_mediation_groups(
    account_id: str = "",
    state: str = "",
    platform: str = "",
    ad_format: str = "",
    filter_expr: str = "",
    page_size: int = 50,
    max_items: int = 100,
    fields: str = "",
    full_response: bool = False,
) -> str:
    """列出 Mediation Groups（中介组），含分页/过滤/字段裁剪。需要白名单权限。

    便捷过滤（会自动 AND 拼接到 filter，AdMob 仅支持以下字段）：
      - state: ENABLED | DISABLED
      - platform: ANDROID | IOS
      - ad_format: BANNER | INTERSTITIAL | REWARDED | REWARDED_INTERSTITIAL | NATIVE | APP_OPEN

    其他参数：
      - filter_expr: 原始 AdMob 过滤表达式，会与上面便捷条件 AND 拼接。注意 AdMob v1beta
        实测仅支持 STATE / PLATFORM / FORMAT 字段，AD_UNIT_ID / MEDIATION_GROUP_ID 等
        会被拒绝为 "Invalid field name"。
      - page_size: 单次 RPC 页大小，默认 50
      - max_items: 跨页总条数上限，默认 100；返回结果含 truncated 与 nextPageToken；
        大账户（>500 groups）配合 full_response=True 一次取回会超过工具结果上限，请保持
        默认 max_items 或自行翻页
      - fields: 自定义 FieldMask；留空则使用默认裁剪（去掉沉重的 mediationGroupLines）
      - full_response: True 时返回完整字段（忽略 fields 参数）"""
    try:
        from auth import get_admob_service_v1beta
        from admob_api import list_mediation_groups as _list

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        composed_filter = _compose_mg_filter(
            state, platform, ad_format, filter_expr,
        )
        if full_response:
            fields_arg: Optional[str] = None
        else:
            fields_arg = fields.strip() or _MG_DEFAULT_FIELDS

        result = _list(
            service, aid,
            filter_expr=composed_filter,
            page_size=page_size or None,
            max_items=max_items or None,
            fields=fields_arg,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("list_mediation_groups failed")
        return _tool_error(e)


@mcp.tool()
def create_mediation_group(body_json: str, account_id: str = "") -> str:
    """创建 Mediation Group。需要 admob.monetization scope（写权限）。

    body_json 关键字段（MediationGroup）：
      - displayName (str)
      - state ("ENABLED" | "DISABLED")
      - targeting:
          {"platform":"ANDROID|IOS",
           "format":"BANNER|INTERSTITIAL|REWARDED|REWARDED_INTERSTITIAL|NATIVE|APP_OPEN",
           "adUnitIds":["ca-app-pub-XXX/123", ...]}        # ⚠ 短字符串，非 resource name
      - mediationGroupLines: **map<string, MediationGroupLine>**（不是数组），
        创建时 key 可任写一个标签，AdMob 返回时会替换为自动生成的 line id。
        每条 MediationGroupLine 的 adUnitMappings 也是 map<string, string>，
        **key = 完整 ca-app-pub-XXX/123，value = 对应 mapping 的 resource name**。
        targeted ad unit 的格式必须与 targeting.format 一致，否则 400。
        允许传空 map `{}`，AdMob 会自动加一条默认 AdMob Network line。"""
    try:
        from auth import get_admob_service_v1beta
        from admob_api import create_mediation_group as _create

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        body = _parse_json_arg("body_json", body_json)
        result = _create(service, aid, body)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("create_mediation_group failed")
        return _tool_error(e)


@mcp.tool()
def update_mediation_group(
    mediation_group_id: str,
    body_json: str,
    update_mask: str = "",
    account_id: str = "",
) -> str:
    """更新 Mediation Group（PATCH）。需要 admob.monetization scope。

    mediation_group_id 为组 ID（不含 accounts/.../mediationGroups/ 前缀）。
    update_mask 为逗号分隔的字段路径（接受 camelCase 或 snake_case）。

    ⚠ AdMob v1beta 实测**仅支持** patch 这些顶层字段：
      - displayName / display_name
      - state
      - targeting

    `mediationGroupLines` **不能** 通过 PATCH 修改（mask 里出现该字段会报
    "Update mask contains fields that do not exist..."）。要改 lines，必须走
    `create_mediation_ab_experiment` + `stop_mediation_ab_experiment(VARIANT_CHOICE_B)`
    流程把新 lines 写回 group。"""
    try:
        from auth import get_admob_service_v1beta
        from admob_api import update_mediation_group as _update

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        body = _parse_json_arg("body_json", body_json)
        result = _update(
            service, aid, mediation_group_id, body,
            update_mask=update_mask or None,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("update_mediation_group failed")
        return _tool_error(e)


@mcp.tool()
def create_mediation_ab_experiment(
    mediation_group_id: str,
    body_json: str,
    account_id: str = "",
) -> str:
    """在指定 Mediation Group 下创建 A/B 实验。需要 admob.monetization scope。

    body_json 关键字段（MediationAbExperiment）：
      - displayName (str)
      - treatmentMediationLines: **list of {mediationGroupLine: MediationGroupLine}**
        （注意每条 line 必须包一层 `mediationGroupLine`），且**不要**给 line 写 `id`，
        AdMob 会自动分配；写了会报 "Treatment mediation lines shouldn't specify an Id"
      - treatmentTrafficPercentage: 字符串 "1"–"99"
      - variantLeader: "CONTROL" | "TREATMENT" | "VARIANT_LEADER_UNSPECIFIED"
        （实验自然结束时默认胜出方）

    ⚠ controlMediationLines 是 readOnly 字段，AdMob 会自动从 parent group 当前 lines
    继承，**不要**在 body 里传，否则 schema 会报 unknown field。

    最小 body 示例：
      {"displayName":"exp1",
       "treatmentMediationLines":[{"mediationGroupLine":{"displayName":"l","adSourceId":"...","cpmMode":"LIVE","state":"ENABLED"}}],
       "treatmentTrafficPercentage":"1",
       "variantLeader":"CONTROL"}"""
    try:
        from auth import get_admob_service_v1beta
        from admob_api import create_mediation_ab_experiment as _create

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        body = _parse_json_arg("body_json", body_json)
        result = _create(service, aid, mediation_group_id, body)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("create_mediation_ab_experiment failed")
        return _tool_error(e)


@mcp.tool()
def stop_mediation_ab_experiment(
    mediation_group_id: str,
    variant_choice: str = "",
    account_id: str = "",
) -> str:
    """停止指定 Mediation Group 上正在运行的 A/B 实验。需要 admob.monetization scope。

    AdMob v1beta 的 stop 端点路径只到 `mediationAbExperiments`，不带 experiment id
    （每个 group 同一时刻仅允许 1 个实验在跑），因此无需也不能传 experiment_id。

    variant_choice 可选枚举：
      - 'VARIANT_CHOICE_A'：保留对照组（control，原 lines）
      - 'VARIANT_CHOICE_B'：采用实验组（treatment lines）写回 group
      - 留空：不指定（仅在实验已自然结束时合法）"""
    try:
        from auth import get_admob_service_v1beta
        from admob_api import stop_mediation_ab_experiment as _stop

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        result = _stop(
            service, aid, mediation_group_id,
            variant_choice=variant_choice or None,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("stop_mediation_ab_experiment failed")
        return _tool_error(e)


@mcp.tool()
def list_ad_unit_mappings(
    ad_unit_id: str,
    filter_expr: str = "",
    page_size: int = 0,
    account_id: str = "",
) -> str:
    """列出指定 Ad Unit 下所有 Ad Unit Mappings（第三方广告源映射）。
    ad_unit_id 为广告单元 ID（不含 accounts/.../adUnits/ 前缀）。
    filter_expr 例: 'STATE = "ENABLED"' 或 'ADAPTER_ID = "...". """
    try:
        from auth import get_admob_service_v1beta
        from admob_api import list_ad_unit_mappings as _list

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        result = _list(
            service, aid, ad_unit_id,
            filter_expr=filter_expr or None,
            page_size=page_size or None,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("list_ad_unit_mappings failed")
        return _tool_error(e)


@mcp.tool()
def create_ad_unit_mapping(
    ad_unit_id: str,
    body_json: str,
    account_id: str = "",
) -> str:
    """创建单个 Ad Unit Mapping。需要 admob.monetization scope。

    body_json 关键字段（AdUnitMapping）：
      - displayName (str)
      - adapterId (str)
      - adUnitConfigurations: map<string,string>，key 是 adapter 元数据里的
        adapterConfigMetadataId（如 AdMob Network Android 是 "118"），不是 label 名
      - state: 仅支持 "ENABLED"，AdMob v1beta 没有 "DISABLED" 枚举

    ⚠ AdMob 会按 (adapterId + adUnitConfigurations) 做去重——配置完全相同时二次创建
    会复用旧 mapping 的 id 并仅更新 displayName，不会创建新行。"""
    try:
        from auth import get_admob_service_v1beta
        from admob_api import create_ad_unit_mapping as _create

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        body = _parse_json_arg("body_json", body_json)
        result = _create(service, aid, ad_unit_id, body)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("create_ad_unit_mapping failed")
        return _tool_error(e)


@mcp.tool()
def batch_create_ad_unit_mappings(
    requests_json: str,
    account_id: str = "",
) -> str:
    """批量创建 Ad Unit Mappings。需要 admob.monetization scope。

    requests_json 为 JSON 数组，每项必须形如：
      {"parent":"accounts/pub-XXX/adUnits/123","adUnitMapping":{...}}

    ⚠ 字段名是 `parent`（**不是** `adUnitId`）。`adUnitMapping.state` 只接受
    "ENABLED"，传 "DISABLED" 会被拒绝为 invalid enum。同 create_ad_unit_mapping，
    AdMob 按 (adapterId + adUnitConfigurations) 去重，相同配置会复用旧 id。"""
    try:
        from auth import get_admob_service_v1beta
        from admob_api import batch_create_ad_unit_mappings as _batch

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        raw = (requests_json or "").strip()
        if not raw:
            raise ValueError("requests_json must be a non-empty JSON array")
        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("requests_json must be a JSON array")
        result = _batch(service, aid, items)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("batch_create_ad_unit_mappings failed")
        return _tool_error(e)


@mcp.tool()
def list_ad_sources(account_id: str = "") -> str:
    """列出账户可用的 Ad Sources（如 AdMob Network、Meta、AppLovin 等），
    返回的 adSourceId 用于查询 adapters 和构造 mediation lines。"""
    try:
        from auth import get_admob_service_v1beta
        from admob_api import list_ad_sources as _list

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        result = _list(service, aid)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("list_ad_sources failed")
        return _tool_error(e)


@mcp.tool()
def list_adapters(ad_source_id: str, account_id: str = "") -> str:
    """列出指定 Ad Source 下的 Adapters（按平台/广告格式划分）。
    返回 adapterId 与 adapterConfigMetadata（构造 AdUnitMapping.adUnitConfigurations 时需要的 key）。"""
    try:
        from auth import get_admob_service_v1beta
        from admob_api import list_adapters as _list

        service = get_admob_service_v1beta()
        aid = _get_account_id(account_id)
        result = _list(service, aid, ad_source_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("list_adapters failed")
        return _tool_error(e)


def _build_streamable_http_app(mcp_path: str = "/mcp"):
    """Build a raw ASGI app with Streamable HTTP transport.

    Uses is_json_response_enabled=True so POST responses return
    application/json instead of text/event-stream, which is required
    for Claude Code's MCP HTTP client.
    """
    import asyncio
    import uuid

    from starlette.requests import Request
    from starlette.responses import Response
    from mcp.server.streamable_http import StreamableHTTPServerTransport

    _sessions: dict[str, StreamableHTTPServerTransport] = {}
    _tasks: dict[str, asyncio.Task] = {}

    # Get the underlying low-level server from FastMCP
    _server = mcp._mcp_server

    async def _run_mcp_session(
        transport: StreamableHTTPServerTransport,
        session_id: str,
        ready_event: asyncio.Event,
    ):
        try:
            async with transport.connect() as (read_stream, write_stream):
                ready_event.set()
                await _server.run(
                    read_stream,
                    write_stream,
                    _server.create_initialization_options(),
                )
        except Exception:
            logger.exception("MCP session %s crashed", session_id)
        finally:
            ready_event.set()
            _sessions.pop(session_id, None)
            _tasks.pop(session_id, None)

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                msg = await receive()
                if msg["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif msg["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
            return

        if scope["type"] != "http":
            return

        request = Request(scope, receive, send)

        if scope["path"] != mcp_path:
            resp = Response("Not Found", status_code=404)
            await resp(scope, receive, send)
            return

        if request.method not in ("GET", "POST", "DELETE"):
            resp = Response("Method Not Allowed", status_code=405)
            await resp(scope, receive, send)
            return

        session_id = request.headers.get("mcp-session-id")

        if request.method == "GET":
            if session_id and session_id in _sessions:
                transport = _sessions[session_id]
                await transport.handle_request(scope, receive, send)
                return

        if request.method == "POST":
            if session_id and session_id in _sessions:
                transport = _sessions[session_id]
                await transport.handle_request(scope, receive, send)
                return

            # New session
            new_session_id = str(uuid.uuid4())
            transport = StreamableHTTPServerTransport(
                mcp_session_id=new_session_id,
                is_json_response_enabled=True,
            )
            _sessions[new_session_id] = transport
            ready_event = asyncio.Event()
            _tasks[new_session_id] = asyncio.create_task(
                _run_mcp_session(transport, new_session_id, ready_event)
            )
            await ready_event.wait()
            await transport.handle_request(scope, receive, send)
            return

        if request.method == "DELETE":
            if session_id and session_id in _sessions:
                transport = _sessions.pop(session_id, None)
                task = _tasks.pop(session_id, None)
                if transport:
                    transport.terminate()
                    await transport.handle_request(scope, receive, send)
                if task:
                    task.cancel()
                return

        resp = Response("Bad Request", status_code=400)
        await resp(scope, receive, send)

    return app


def main():
    parser = argparse.ArgumentParser(description="AdMob MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--host", default=None, help="Host override for HTTP transports",
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Port override for HTTP transports",
    )
    args = parser.parse_args()

    if args.transport == "streamable-http":
        import uvicorn

        host = args.host or os.getenv("MCP_HOST", "127.0.0.1")
        port = args.port or int(os.getenv("MCP_PORT", "8000"))
        app = _build_streamable_http_app()
        logger.info("Starting Streamable HTTP transport on %s:%d/mcp", host, port)
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
