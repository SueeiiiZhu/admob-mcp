import os
import logging
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

SCOPES = [
    "https://www.googleapis.com/auth/admob.readonly",
]


def _get_credentials() -> service_account.Credentials:
    """Load Service Account credentials from JSON key file."""
    key_path = Path(
        os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_KEY",
            str(BASE_DIR / "credentials" / "service_account.json"),
        )
    ).expanduser()
    if not key_path.exists():
        raise FileNotFoundError(
            "Service account key file not found. "
            "Download from Google Cloud Console and place at the configured path, "
            "or set GOOGLE_SERVICE_ACCOUNT_KEY env var."
        )
    return service_account.Credentials.from_service_account_file(
        str(key_path), scopes=SCOPES
    )


def get_admob_service():
    """Build and return AdMob API v1 service."""
    return build("admob", "v1", credentials=_get_credentials())
