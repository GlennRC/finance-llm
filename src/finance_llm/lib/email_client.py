"""Gmail email client — OAuth2-based email fetching and CSV extraction.

Connects to Gmail, searches for bank statement emails, downloads
CSV attachments, and saves them to import/raw/.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from finance_llm.lib.state import SeenEmails

# Gmail API scopes needed
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Default search query for bank statement emails
DEFAULT_QUERY = "has:attachment filename:csv (statement OR transactions OR activity)"


class GmailClient:
    """Gmail API client for fetching bank statement CSV attachments."""

    def __init__(
        self,
        credentials_path: Path,
        token_path: Path,
        seen_db: SeenEmails,
    ) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.seen_db = seen_db
        self._service = None

    def _get_service(self):  # noqa: ANN202
        """Build or refresh the Gmail API service."""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            self.token_path.write_text(creds.to_json())

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    @property
    def service(self):  # noqa: ANN202
        if self._service is None:
            return self._get_service()
        return self._service

    def search_messages(self, query: str = DEFAULT_QUERY, max_results: int = 50) -> list[dict]:
        """Search Gmail for messages matching the query."""
        results = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return results.get("messages", [])

    def get_message(self, message_id: str) -> dict:
        """Get full message details."""
        return (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    def get_csv_attachments(self, message_id: str) -> list[tuple[str, bytes]]:
        """Extract CSV attachments from a message.

        Returns list of (filename, content_bytes) tuples.
        """
        msg = self.get_message(message_id)
        attachments = []

        for part in msg.get("payload", {}).get("parts", []):
            filename = part.get("filename", "")
            if not filename.lower().endswith(".csv"):
                continue

            attachment_id = part.get("body", {}).get("attachmentId")
            if not attachment_id:
                continue

            att = (
                self.service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )
            data = base64.urlsafe_b64decode(att["data"])
            attachments.append((filename, data))

        return attachments

    def detect_institution(self, sender: str, subject: str) -> str | None:
        """Guess institution from email sender/subject.

        Override this method or extend with a config file for
        institution detection rules.
        """
        patterns = {
            "chase": r"chase",
            "amex": r"american express|amex",
            "bofa": r"bank of america",
            "citi": r"citibank|citi",
            "wells": r"wells fargo",
            "capital_one": r"capital one",
        }
        text = f"{sender} {subject}".lower()
        for institution, pattern in patterns.items():
            if re.search(pattern, text):
                return institution
        return None

    def fetch_new_csvs(
        self,
        output_dir: Path,
        query: str = DEFAULT_QUERY,
    ) -> list[dict]:
        """Fetch new CSV attachments from Gmail.

        Returns list of dicts with keys: message_id, institution, file_path, filename
        """
        messages = self.search_messages(query)
        results = []

        for msg_info in messages:
            msg_id = msg_info["id"]
            if self.seen_db.is_seen(msg_id):
                continue

            msg = self.get_message(msg_id)
            headers = {
                h["name"].lower(): h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }
            sender = headers.get("from", "")
            subject = headers.get("subject", "")
            institution = self.detect_institution(sender, subject) or "unknown"

            attachments = self.get_csv_attachments(msg_id)
            for filename, data in attachments:
                from datetime import datetime
                from hashlib import sha256

                month = datetime.now().strftime("%Y-%m")
                file_hash = sha256(data).hexdigest()[:16]
                dest_dir = output_dir / institution / month
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / f"sha256_{file_hash}.csv"
                dest_path.write_bytes(data)

                self.seen_db.mark_seen(msg_id, institution, str(dest_path))
                results.append({
                    "message_id": msg_id,
                    "institution": institution,
                    "file_path": str(dest_path),
                    "filename": filename,
                })

        return results
