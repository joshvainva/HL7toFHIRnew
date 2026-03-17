"""
Validation layer — validates parsed HL7 input and FHIR output.
"""
import re
from typing import List, Tuple

from app.core.parser import ParsedHL7Message


class ValidationResult:
    def __init__(self):
        self.valid: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)


class HL7Validator:
    """Validates a parsed HL7 message for completeness and consistency."""

    REQUIRED_SEGMENTS = ["MSH"]

    MESSAGE_REQUIRED_SEGMENTS = {
        "ADT": ["MSH", "EVN", "PID"],
        "ORU": ["MSH", "PID", "OBR", "OBX"],
        "ORM": ["MSH", "PID", "ORC"],
        "MDM": ["MSH", "EVN", "PID", "TXA"],
        "SIU": ["MSH", "SCH", "PID"],
        "VXU": ["MSH", "PID", "RXA"],
    }

    def validate(self, msg: ParsedHL7Message) -> ValidationResult:
        result = ValidationResult()

        # MSH presence
        if "MSH" not in msg.segments:
            result.add_error("MSH segment is missing.")
            return result

        # Version check
        if msg.version == "unknown":
            result.add_warning("Could not determine HL7 version from MSH-12.")
        elif not re.match(r"2\.\d+", msg.version):
            result.add_warning(
                f"HL7 version '{msg.version}' may not be fully supported. "
                "Supported: 2.x"
            )

        # Message type
        if msg.message_type == "unknown":
            result.add_warning("Could not determine message type from MSH-9.")

        # Required segments per message type
        required = self.MESSAGE_REQUIRED_SEGMENTS.get(msg.message_type, [])
        for seg_name in required:
            if seg_name not in msg.segments:
                result.add_warning(
                    f"Expected segment '{seg_name}' for {msg.message_type} message "
                    "but it is not present."
                )

        # PID validation for patient-centric messages
        if "PID" in msg.segments:
            pid = msg.segments["PID"][0]
            try:
                patient_name = str(pid[5]).strip()
                if not patient_name:
                    result.add_warning("PID-5 (patient name) is empty.")
            except Exception:
                result.add_warning("Could not read PID-5 (patient name).")

        return result
