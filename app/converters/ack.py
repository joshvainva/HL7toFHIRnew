"""
ACK (Acknowledgment) message converter.

Produces: OperationOutcome resource.
"""
from typing import Any, Dict, List, Tuple

from app.converters.base import (
    BaseConverter,
    make_id,
    safe_str,
    parse_hl7_datetime,
    extract_name,
    extract_address,
    extract_telecom,
    extract_identifier,
    extract_coding,
)
from app.core.parser import ParsedHL7Message


class ACKConverter(BaseConverter):
    """Converts HL7 ACK messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[Any]]:
        resources = []
        warnings = []
        field_mappings = []

        operation_outcome_id = make_id()

        # Build OperationOutcome
        operation_outcome = self._build_operation_outcome(parsed_msg, operation_outcome_id, warnings)
        resources.append(operation_outcome)

        return resources, warnings, field_mappings

    def _build_operation_outcome(self, parsed_msg: ParsedHL7Message, operation_outcome_id: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR OperationOutcome resource from MSA segment."""
        msa = parsed_msg.get_segment("MSA")
        if not msa:
            warnings.append("ACK message missing MSA segment")
            return {
                "resourceType": "OperationOutcome",
                "id": operation_outcome_id,
                "issue": [{"severity": "information", "code": "informational"}],
            }

        # Map ACK acknowledgment code to OperationOutcome issue severity
        ack_code = safe_str(msa[1])  # MSA-1: Acknowledgment code
        severity_map = {
            "AA": "information",   # Application Accept
            "AE": "error",         # Application Error
            "AR": "error",         # Application Reject
            "CA": "information",   # Commit Accept
            "CE": "error",         # Commit Error
            "CR": "error",         # Commit Reject
        }
        severity = severity_map.get(ack_code, "information")

        # Map to issue code
        code_map = {
            "AA": "informational",
            "AE": "processing",
            "AR": "invalid",
            "CA": "informational",
            "CE": "processing",
            "CR": "invalid",
        }
        code = code_map.get(ack_code, "informational")

        operation_outcome = {
            "resourceType": "OperationOutcome",
            "id": operation_outcome_id,
            "issue": [{
                "severity": severity,
                "code": code,
                "details": {
                    "text": safe_str(msa[3]) or f"HL7 ACK: {ack_code}"
                },
            }],
        }

        # Add message control ID reference
        if msa[2]:  # MSA-2: Message control ID
            operation_outcome["issue"][0]["diagnostics"] = f"Original Message Control ID: {safe_str(msa[2])}"

        return operation_outcome