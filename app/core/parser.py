"""
HL7 Parser — detects version, message type, and parses segments.

Supports HL7 v2.x messages with any segment structure including Z-segments.
"""
import re
from typing import Dict, List, Optional, Tuple
import hl7


class HL7ParseError(Exception):
    pass


class ParsedHL7Message:
    """Holds parsed HL7 message components."""

    def __init__(self):
        self.raw: str = ""
        self.version: str = ""
        self.message_type: str = ""
        self.message_event: str = ""
        self.message_control_id: str = ""
        self.sending_application: str = ""
        self.sending_facility: str = ""
        self.receiving_application: str = ""
        self.receiving_facility: str = ""
        self.datetime: str = ""
        self.segments: Dict[str, List] = {}
        self.segment_order: List[str] = []
        self.parsed: Optional[hl7.Message] = None

    def get_segment(self, name: str) -> Optional[hl7.Segment]:
        """Return the first occurrence of a named segment."""
        try:
            return self.parsed.segment(name)
        except Exception:
            return None

    def get_all_segments(self, name: str) -> List[hl7.Segment]:
        """Return all occurrences of a named segment."""
        return [seg for seg in self.parsed if str(seg[0]) == name]

    def field(self, segment_name: str, field_index: int, component: int = 1,
               subcomponent: int = 1) -> str:
        """Safely extract a field value, returning empty string on any error."""
        try:
            seg = self.get_segment(segment_name)
            if seg is None:
                return ""
            val = seg[field_index]
            if component > 1:
                parts = str(val).split("^")
                val = parts[component - 1] if len(parts) >= component else ""
            if subcomponent > 1:
                parts = str(val).split("&")
                val = parts[subcomponent - 1] if len(parts) >= subcomponent else ""
            return str(val).strip() if val else ""
        except Exception:
            return ""


class HL7Parser:
    """
    Parses HL7 v2.x messages and extracts structured data.

    Handles:
    - Multiple segment delimiter styles (\\r, \\n, \\r\\n)
    - Repeating fields
    - Custom Z-segments
    - Missing optional fields
    """

    # Known message types and their primary events
    MESSAGE_TYPE_MAP = {
        "ADT": "Admit/Discharge/Transfer",
        "ORU": "Observation Result",
        "ORM": "Order Message",
        "MDM": "Medical Document Management",
        "SIU": "Scheduling Information Unsolicited",
        "BAR": "Add/Change Billing Account",
        "DFT": "Detail Financial Transaction",
        "MFN": "Master Files Notification",
        "PPR": "Patient Problem",
        "RAS": "Pharmacy/Treatment Administration",
        "RDE": "Pharmacy/Treatment Encoded Order",
        "VXU": "Unsolicited Vaccination Record Update",
        "ACK": "Acknowledgment",
    }

    def normalize(self, raw: str) -> str:
        """Normalize line endings to \\r for the hl7 library."""
        # Replace CRLF then lone LF with CR
        text = raw.replace("\r\n", "\r").replace("\n", "\r")
        # Strip leading/trailing whitespace but preserve internal structure
        text = text.strip()
        return text

    def validate_msh(self, normalized: str) -> None:
        """Verify that the message begins with a valid MSH segment."""
        if not normalized.upper().startswith("MSH"):
            raise HL7ParseError(
                "HL7 message must begin with an MSH segment. "
                "Received: " + repr(normalized[:40])
            )
        # Check field separator character at position 3
        if len(normalized) < 8:
            raise HL7ParseError("MSH segment is too short to be valid.")

    def detect_version(self, msg: hl7.Message) -> str:
        """Extract version string from MSH-12."""
        try:
            version = str(msg["MSH.F12.R1.C1"]).strip()
            return version if version else "unknown"
        except Exception:
            try:
                return str(msg.segment("MSH")[12]).strip()
            except Exception:
                return "unknown"

    def detect_message_type(self, msg: hl7.Message) -> Tuple[str, str]:
        """Return (message_type, trigger_event) from MSH-9."""
        try:
            msh9 = str(msg["MSH.F9.R1.C1"]).strip()
            event = str(msg["MSH.F9.R1.C2"]).strip()
            return msh9, event
        except Exception:
            try:
                msh9_raw = str(msg.segment("MSH")[9])
                parts = msh9_raw.split("^")
                msg_type = parts[0].strip() if parts else "unknown"
                event = parts[1].strip() if len(parts) > 1 else ""
                return msg_type, event
            except Exception:
                return "unknown", ""

    def parse(self, raw_message: str) -> ParsedHL7Message:
        """
        Parse a raw HL7 message string into a ParsedHL7Message.

        Raises HL7ParseError on malformed input.
        """
        if not raw_message or not raw_message.strip():
            raise HL7ParseError("Empty HL7 message provided.")

        normalized = self.normalize(raw_message)
        self.validate_msh(normalized)

        try:
            parsed = hl7.parse(normalized)
        except Exception as exc:
            raise HL7ParseError(f"Failed to parse HL7 message: {exc}") from exc

        result = ParsedHL7Message()
        result.raw = raw_message
        result.parsed = parsed
        result.version = self.detect_version(parsed)
        result.message_type, result.message_event = self.detect_message_type(parsed)

        # Extract common MSH fields
        try:
            msh = parsed.segment("MSH")
            result.sending_application = str(msh[3]).split("^")[0].strip()
            result.sending_facility = str(msh[4]).split("^")[0].strip()
            result.receiving_application = str(msh[5]).split("^")[0].strip()
            result.receiving_facility = str(msh[6]).split("^")[0].strip()
            result.datetime = str(msh[7]).strip()
            result.message_control_id = str(msh[10]).strip()
        except Exception:
            pass  # Non-critical — populate what we can

        # Build segment inventory
        for segment in parsed:
            seg_name = str(segment[0]).strip()
            if seg_name not in result.segments:
                result.segments[seg_name] = []
            result.segments[seg_name].append(segment)
            result.segment_order.append(seg_name)

        return result
