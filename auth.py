import os
import pickle
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

SCOPES = [
    "https://www.googleapis.com/auth/admob.readonly",
    # 写入 Mediation Group / A/B 实验 / Ad Unit Mapping 需要 monetization scope。
    # 已有 token 仅用读权限时可继续使用，调用写接口前请重跑 auth_flow.py 重新授权。
    "https://www.googleapis.com/auth/admob.monetization",
]


def _get_credentials():
    """Load OAuth2 user credentials from token.pickle, auto-refreshing if needed."""
    token_path = Path(
        os.getenv(
            "GOOGLE_TOKEN_FILE",
            str(BASE_DIR / "credentials" / "token.pickle"),
        )
    ).expanduser()

    if not token_path.exists():
        raise FileNotFoundError(
            "OAuth token file not found. "
            "Place your token.pickle in credentials/ or set GOOGLE_TOKEN_FILE env var."
        )

    with open(token_path, "rb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        logger.info("Access token refreshed and saved.")

    return creds


def get_admob_service():
    """Build and return AdMob API v1 service."""
    return build("admob", "v1", credentials=_get_credentials())


def get_admob_service_v1beta():
    """Build and return AdMob API v1beta service.

    v1beta 暴露 Mediation Group、Mediation A/B 实验、Ad Unit Mapping、AdSource 等
    需要白名单的接口。读取使用 admob.readonly scope，写入需要 admob.monetization scope。
    """
    return build("admob", "v1beta", credentials=_get_credentials())
