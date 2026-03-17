"""
Handler for Excel files (.xlsx, .xls) containing HL7 messages.

Scans all sheets and all cells for content that looks like HL7 messages.
"""
import io
from typing import List

from app.file_handlers.base import BaseFileHandler


class ExcelHandler(BaseFileHandler):

    def can_handle(self, filename: str, content_type: str) -> bool:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in {".xlsx", ".xls"}

    def extract_messages(self, data: bytes, filename: str) -> List[str]:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".xlsx"

        if ext == ".xls":
            return self._read_xls(data)
        return self._read_xlsx(data)

    def _read_xlsx(self, data: bytes) -> List[str]:
        try:
            import openpyxl
        except ImportError:
            raise ValueError("openpyxl is required to read .xlsx files.")

        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:
            raise ValueError(f"Could not open Excel file: {exc}") from exc

        messages = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                for cell_val in row:
                    if cell_val is None:
                        continue
                    text = str(cell_val).strip()
                    if text.upper().startswith("MSH|"):
                        messages.append(text)
                        break  # one message per row

        if not messages:
            raise ValueError(
                "No HL7 messages found in Excel file. "
                "Cells should contain HL7 messages starting with MSH|."
            )
        return messages

    def _read_xls(self, data: bytes) -> List[str]:
        try:
            import xlrd
        except ImportError:
            raise ValueError("xlrd is required to read .xls files.")

        try:
            wb = xlrd.open_workbook(file_contents=data)
        except Exception as exc:
            raise ValueError(f"Could not open .xls file: {exc}") from exc

        messages = []
        for sheet in wb.sheets():
            for row_idx in range(sheet.nrows):
                for col_idx in range(sheet.ncols):
                    cell_val = sheet.cell_value(row_idx, col_idx)
                    if not cell_val:
                        continue
                    text = str(cell_val).strip()
                    if text.upper().startswith("MSH|"):
                        messages.append(text)
                        break

        if not messages:
            raise ValueError("No HL7 messages found in .xls file.")
        return messages
