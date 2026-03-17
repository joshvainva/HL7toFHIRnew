"""
Handler for .csv files containing HL7 messages in cells.

Supports two layouts:
1. Single-column: each row contains one full HL7 message
2. Multi-column: first column is a key/ID, second column is the message
"""
import csv
import io
from typing import List

from app.file_handlers.base import BaseFileHandler


class CSVHandler(BaseFileHandler):

    def can_handle(self, filename: str, content_type: str) -> bool:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext == ".csv" or content_type in ("text/csv", "application/csv")

    def extract_messages(self, data: bytes, filename: str) -> List[str]:
        try:
            text = data.decode("utf-8-sig", errors="replace")  # handle BOM
        except Exception as exc:
            raise ValueError(f"Could not decode CSV file: {exc}") from exc

        reader = csv.reader(io.StringIO(text))
        messages = []

        for row_num, row in enumerate(reader, start=1):
            for cell in row:
                cell = cell.strip()
                if cell.upper().startswith("MSH|"):
                    messages.append(cell)
                    break  # only one message per row

        if not messages:
            raise ValueError(
                "No HL7 messages found in CSV file. "
                "Each row should contain an HL7 message starting with MSH|."
            )
        return messages
