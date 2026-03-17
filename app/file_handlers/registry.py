"""
File handler registry — maps uploaded files to the correct handler.

New handlers can be added here without modifying any other module.
"""
from typing import List, Optional

from app.file_handlers.base import BaseFileHandler
from app.file_handlers.hl7_handler import HL7TextHandler
from app.file_handlers.csv_handler import CSVHandler
from app.file_handlers.excel_handler import ExcelHandler
from app.file_handlers.docx_handler import DocxHandler


# Ordered list of registered handlers — first match wins
_HANDLERS: List[BaseFileHandler] = [
    HL7TextHandler(),
    CSVHandler(),
    ExcelHandler(),
    DocxHandler(),
]


def get_handler(filename: str, content_type: str) -> Optional[BaseFileHandler]:
    """Return the first handler that can process the given file."""
    for handler in _HANDLERS:
        if handler.can_handle(filename, content_type):
            return handler
    return None


def supported_extensions() -> List[str]:
    """Return a flat list of all supported file extensions."""
    exts = []
    for handler in _HANDLERS:
        if hasattr(handler, "SUPPORTED_EXTENSIONS"):
            exts.extend(handler.SUPPORTED_EXTENSIONS)
    return sorted(set(exts))
