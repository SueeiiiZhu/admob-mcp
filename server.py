import argparse
import os
import re
import sys
import json
import logging
from decimal import Decimal

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
