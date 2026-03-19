"""
Routes a FHIR Bundle to the appropriate HL7 converter.
"""
import logging
from typing import Any, Dict, Tuple

from app.converters.fhir_to_hl7.adt import ADTtoHL7Converter
from app.converters.fhir_to_hl7.oru import ORUtoHL7Converter
from app.converters.fhir_to_hl7.orm import ORMtoHL7Converter

logger = logging.getLogger(__name__)

FHIR_CONVERTER_REGISTRY = {
    "ADT": ADTtoHL7Converter,
    "ORU": ORUtoHL7Converter,
    "ORM": ORMtoHL7Converter,
}


def detect_message_type(bundle: Dict[str, Any]) -> str:
    """
    Detect the most appropriate HL7 message type for a FHIR Bundle.

    Heuristics (in priority order):
      - Has DiagnosticReport → ORU
      - Has ServiceRequest   → ORM
      - Has Encounter        → ADT
      - Default              → ADT
    """
    resource_types = {
        e.get("resource", {}).get("resourceType", "")
        for e in bundle.get("entry", [])
    }

    if "DiagnosticReport" in resource_types or "Observation" in resource_types:
        return "ORU"
    if "ServiceRequest" in resource_types:
        return "ORM"
    return "ADT"


class FHIRtoHL7Mapper:
    """Maps a FHIR Bundle dict to an HL7 v2.x message string."""

    def map(self, bundle: Dict[str, Any]) -> Tuple[str, str, str]:
        """
        Returns (hl7_message, message_type, warnings_str).
        """
        msg_type = detect_message_type(bundle)
        converter_class = FHIR_CONVERTER_REGISTRY.get(msg_type, ADTtoHL7Converter)
        converter = converter_class()

        try:
            hl7_message = converter.convert(bundle)
            return hl7_message, msg_type, ""
        except Exception as exc:
            logger.exception("FHIR→HL7 conversion error")
            return "", msg_type, str(exc)
