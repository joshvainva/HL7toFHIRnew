"""
History management for HL7 to FHIR conversions.
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class HistoryItem:
    """Represents a single conversion in history."""
    id: str
    timestamp: str
    hl7_version: str
    message_type: str
    message_event: Optional[str]
    input_type: str  # 'text' or 'file'
    input_name: Optional[str]  # filename if uploaded
    success: bool
    hl7_content: str
    direction: str = "hl7_to_fhir"
    fhir_json: Optional[Dict] = None
    fhir_xml: Optional[str] = None
    human_readable: Optional[str] = None
    field_mappings: Optional[List] = None
    hl7_output: Optional[str] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'HistoryItem':
        """Create from dictionary."""
        return cls(**data)


class ConversionHistory:
    """Manages conversion history with a maximum size."""

    def __init__(self, max_items: int = 10):
        self.max_items = max_items
        self.items: List[HistoryItem] = []

    def add_conversion(self, item: HistoryItem) -> None:
        """Add a new conversion to history."""
        self.items.insert(0, item)  # Add to beginning
        if len(self.items) > self.max_items:
            self.items = self.items[:self.max_items]
        logger.info(f"Added conversion to history: {item.id}")

    def get_all(self) -> List[Dict]:
        """Get all history items as dictionaries."""
        return [item.to_dict() for item in self.items]

    def get_by_id(self, item_id: str) -> Optional[HistoryItem]:
        """Get a specific history item by ID."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def clear(self) -> None:
        """Clear all history."""
        self.items.clear()
        logger.info("History cleared")


# Global history instance
history = ConversionHistory()