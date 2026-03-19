"""
Generic fallback converter for unrecognized or partially supported message types.

Extracts whatever structured data is available and wraps it into a
FHIR Parameters resource for transparency, plus a minimal Patient if PID exists.
"""
from typing import Any, Dict, List, Tuple

from app.converters.base import (
    BaseConverter,
    make_id,
    safe_str,
    extract_name,
    extract_identifier,
)
from app.core.parser import ParsedHL7Message


class GenericConverter(BaseConverter):
    """Fallback converter for unsupported message types."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[Any]]:
        resources = []
        warnings = [
            f"Message type '{parsed_msg.message_type}' does not have a dedicated converter. "
            "A best-effort conversion has been performed."
        ]
        field_mappings = []

        # Try to extract a Patient if PID exists
        pid = parsed_msg.get_segment("PID")
        if pid is not None:
            patient_id = make_id()
            patient: Dict[str, Any] = {"resourceType": "Patient", "id": patient_id}
            try:
                pid3 = safe_str(pid[3])
                if pid3:
                    patient["identifier"] = [extract_identifier(pid3, "http://hospital.example.org/mrn")]
            except Exception:
                pass
            try:
                pid5 = safe_str(pid[5])
                if pid5:
                    patient["name"] = [extract_name(pid5)]
            except Exception:
                pass
            resources.append(patient)

        # Encode the raw message as a FHIR Parameters resource (audit trail)
        param_resource: Dict[str, Any] = {
            "resourceType": "Parameters",
            "id": make_id(),
            "parameter": [
                {"name": "hl7MessageType", "valueString": parsed_msg.message_type},
                {"name": "hl7Event", "valueString": parsed_msg.message_event},
                {"name": "hl7Version", "valueString": parsed_msg.version},
                {"name": "rawMessage", "valueString": parsed_msg.raw},
            ],
        }
        resources.append(param_resource)

        return resources, warnings, field_mappings
