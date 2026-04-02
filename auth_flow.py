"""One-time OAuth2 authorization flow.

Usage:
    1. Create an OAuth Client ID (Desktop app) in Google Cloud Console
    2. Download the JSON and save as credentials/client_secret.json
    3. Run: python auth_flow.py
    4. Follow the browser prompt to authorize
    5. token.json will be saved to credentials/token.json
"""

import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/admob.readonly"]


def main():
    client_secret_path = Path(
        os.getenv(
            "GOOGLE_CLIENT_SECRET",
            str(BASE_DIR / "credentials" / "client_secret.json"),
        )
    ).expanduser()

    if not client_secret_path.exists():
        print(
            "Error: client_secret.json not found.\n"
            "Download from Google Cloud Console → APIs & Services → Credentials → "
            "Create OAuth client ID (Desktop app), then save as credentials/client_secret.json"
        )
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = BASE_DIR / "credentials" / "token.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    print(f"Authorization successful! Token saved to {token_path}")


if __name__ == "__main__":
    main()
