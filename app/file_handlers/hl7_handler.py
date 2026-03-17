"""
Handler for .hl7 and .txt files containing HL7 messages.
"""
import re
from typing import List

from app.file_handlers.base import BaseFileHandler


class HL7TextHandler(BaseFileHandler):
    """Reads .hl7 and .txt files — handles single and batch messages."""

    SUPPORTED_EXTENSIONS = {".hl7", ".txt"}

    def can_handle(self, filename: str, content_type: str) -> bool:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in self.SUPPORTED_EXTENSIONS

    def extract_messages(self, data: bytes, filename: str) -> List[str]:
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception as exc:
            raise ValueError(f"Could not decode file as UTF-8: {exc}") from exc

        return self._split_messages(text)

    def _split_messages(self, text: str) -> List[str]:
        """
        Split a text blob into individual HL7 messages.
        Each message starts with an MSH segment.
        """
        # Normalize line endings
        text = text.replace("\r\n", "\r").replace("\n", "\r")

        # Split by MSH boundaries (batch files contain multiple MSH segments)
        parts = re.split(r"(?=MSH\|)", text, flags=re.IGNORECASE)
        messages = [p.strip() for p in parts if p.strip() and p.strip().upper().startswith("MSH")]

        if not messages:
            raise ValueError(
                "No valid HL7 messages found. "
                "File must contain at least one MSH segment."
            )
        return messages
