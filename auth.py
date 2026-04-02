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
