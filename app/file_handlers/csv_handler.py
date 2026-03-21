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
        ehr_lines = []
        
        valid_ehr_types = {"PATIENT", "ENCOUNTER", "ALLERGY", "DIAGNOSIS", "LAB_ORDER", "LAB_RESULT", "VITAL", "IMMUNIZATION", "INSURANCE", "NK1", "CHIEF_COMPLAINT", "SYMPTOM", "PROCEDURE", "MEDICATION", "CLINICAL_NOTE"}

        for row_num, row in enumerate(reader, start=1):
            if not row or not any(c.strip() for c in row):
                continue
                
            first_cell = row[0].strip().upper()
            
            # Check if this row is an EHR segment
            if first_cell in valid_ehr_types or "PATIENT|" in row[0]:
                str_row = [str(c).strip() for c in row]
                ehr_lines.append("|".join(str_row))
                continue

            for cell in row:
                cell = cell.strip()
                if cell.upper().startswith("MSH|"):
                    messages.append(cell)
                    break  # only one HL7 per row

        if ehr_lines:
            # We found EHR-style rows; group them into a single big message
            messages.append("\n".join(ehr_lines))

        if not messages:
            raise ValueError(
                "No HL7 or EHR messages found in CSV file. "
                "Each row should contain an HL7 message starting with MSH|, or an EHR segment starting with PATIENT/ENCOUNTER/etc."
            )
        return messages
