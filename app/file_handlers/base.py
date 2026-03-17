"""
Base file handler — defines the interface all handlers must implement.
"""
from abc import ABC, abstractmethod
from typing import List


class BaseFileHandler(ABC):
    """
    Abstract base for file handlers.

    Each handler accepts raw bytes and returns a list of HL7 message strings.
    Multiple messages may be present in a single file (batch/multi-message files).
    """

    @abstractmethod
    def can_handle(self, filename: str, content_type: str) -> bool:
        """Return True if this handler supports the given file."""

    @abstractmethod
    def extract_messages(self, data: bytes, filename: str) -> List[str]:
        """
        Extract one or more HL7 message strings from file bytes.

        Raises ValueError with a descriptive message on parsing failure.
        """
