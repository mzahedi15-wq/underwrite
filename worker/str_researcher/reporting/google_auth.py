"""Google OAuth2 / service account authentication management."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import gspread
from googleapiclient.discovery import build

from str_researcher.utils.logging import get_logger

logger = get_logger("google_auth")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]

TOKEN_PATH = Path.home() / ".str_researcher" / "google_token.json"


class GoogleAuthManager:
    """Manages Google API authentication for Sheets and Docs."""

    def __init__(self, credentials_path: str):
        self._credentials_path = Path(credentials_path)
        self._creds: Optional[Credentials | UserCredentials] = None

    def authenticate(self, interactive: bool = True) -> None:
        """Authenticate with Google APIs.

        Supports both service account JSON and OAuth2 client credentials.

        Args:
            interactive: If True, allow browser-based OAuth popup.
                         If False, only use saved tokens (no browser popup).
                         Set to False when running in background threads.
        """
        if not self._credentials_path.exists():
            raise FileNotFoundError(
                f"Google credentials file not found: {self._credentials_path}. "
                "Download from Google Cloud Console."
            )

        creds_data = self._credentials_path.read_text()

        # Detect credential type
        if '"type": "service_account"' in creds_data:
            self._creds = Credentials.from_service_account_file(
                str(self._credentials_path), scopes=SCOPES
            )
            logger.info("Authenticated with service account")
        else:
            # OAuth2 client credentials flow
            self._creds = self._oauth2_flow(interactive=interactive)
            logger.info("Authenticated with OAuth2")

    def _oauth2_flow(self, interactive: bool = True) -> UserCredentials:
        """Run OAuth2 flow for user credentials.

        Args:
            interactive: If True, open browser for OAuth consent.
                         If False, only use existing saved tokens.
        """
        creds = None

        # Check for saved token
        if TOKEN_PATH.exists():
            creds = UserCredentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

        # Refresh or get new credentials
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            if not interactive:
                raise RuntimeError(
                    "No saved Google token found. Please authenticate first via "
                    "the Settings page, then re-run analysis."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self._credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

            # Save for future use
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(creds.to_json())
            logger.info("Saved OAuth2 token to %s", TOKEN_PATH)

        return creds

    def get_gspread_client(self) -> gspread.Client:
        """Get an authenticated gspread client."""
        if self._creds is None:
            self.authenticate()
        return gspread.authorize(self._creds)

    def get_docs_service(self):
        """Get an authenticated Google Docs API service."""
        if self._creds is None:
            self.authenticate()
        return build("docs", "v1", credentials=self._creds)

    def get_drive_service(self):
        """Get an authenticated Google Drive API service."""
        if self._creds is None:
            self.authenticate()
        return build("drive", "v3", credentials=self._creds)
