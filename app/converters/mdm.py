"""
MDM (Medical Document Management) message converter.

Produces: Patient, DocumentReference, Practitioner, Organization resources.
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


class MDMConverter(BaseConverter):
    """Converts HL7 MDM messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str]]:
        resources = []
        warnings = []

        patient_id = make_id()
        document_id = make_id()

        # Build Patient
        patient = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)

        # Build DocumentReference
        document, additional_resources = self._build_document_reference(parsed_msg, document_id, patient_id, warnings)
        resources.append(document)
        resources.extend(additional_resources)

        return resources, warnings

    def _build_patient(self, parsed_msg: ParsedHL7Message, patient_id: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR Patient resource from PID segment."""
        pid = parsed_msg.get_segment("PID")
        if not pid:
            warnings.append("MDM message missing PID segment")
            return {
                "resourceType": "Patient",
                "id": patient_id,
                "identifier": [{"system": "urn:hl7:id", "value": "unknown"}],
            }

        patient = {
            "resourceType": "Patient",
            "id": patient_id,
            "identifier": [extract_identifier(pid[3], "urn:hl7:id")],
            "name": [extract_name(pid[5])],
            "gender": self._map_gender(pid[8]),
            "birthDate": parse_hl7_datetime(safe_str(pid[7])),
        }

        # Address
        if pid[11]:
            patient["address"] = [extract_address(pid[11])]

        # Telecom
        telecom = extract_telecom(pid[13], pid[14])
        if telecom:
            patient["telecom"] = telecom

        return patient

    def _build_document_reference(self, parsed_msg: ParsedHL7Message, document_id: str, patient_id: str, warnings: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build FHIR DocumentReference resource from TXA segment."""
        txa = parsed_msg.get_segment("TXA")
        if not txa:
            warnings.append("MDM message missing TXA segment")
            return {
                "resourceType": "DocumentReference",
                "id": document_id,
                "status": "current",
                "subject": {"reference": f"Patient/{patient_id}"},
                "content": [{"attachment": {"contentType": "text/plain"}}],
            }, []

        # Map MDM event to document status
        status_map = {
            "T01": "current",     # Original document notification
            "T02": "current",     # Original document notification and content
            "T03": "superseded",  # Document status change notification
            "T04": "current",     # Document status change notification and content
            "T05": "current",     # Document addendum notification
            "T06": "current",     # Document addendum notification and content
            "T07": "current",     # Document edit notification
            "T08": "current",     # Document edit notification and content
            "T09": "current",     # Document replacement notification
            "T10": "current",     # Document replacement notification and content
            "T11": "current",     # Document cancel notification
        }
        status = status_map.get(parsed_msg.message_event, "current")

        document = {
            "resourceType": "DocumentReference",
            "id": document_id,
            "status": status,
            "type": {"coding": [extract_coding(txa[2])]},
            "category": [{"coding": [extract_coding(txa[1])]}],
            "subject": {"reference": f"Patient/{patient_id}"},
            "date": parse_hl7_datetime(safe_str(txa[4])),
            "author": [],
            "content": [{"attachment": {
                "contentType": safe_str(txa[3]) or "text/plain",
                "creation": parse_hl7_datetime(safe_str(txa[4])),
            }}],
        }

        additional_resources = []

        # Add practitioners from TXA author fields
        if txa[9]:  # Primary author
            practitioner_id = make_id()
            practitioner = {
                "resourceType": "Practitioner",
                "id": practitioner_id,
                "identifier": [extract_identifier(txa[9])],
                "name": [extract_name(txa[9])],
            }
            additional_resources.append(practitioner)
            document["author"].append({"reference": f"Practitioner/{practitioner_id}"})

        return document, additional_resources

    def _map_gender(self, gender_field: Any) -> str:
        """Map HL7 gender codes to FHIR gender."""
        gender_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}
        gender = safe_str(gender_field).upper()
        return gender_map.get(gender, "unknown")