"""
VXU (Vaccination Update) message converter.

Produces: Patient, Immunization, Practitioner, Organization resources.
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


class VXUConverter(BaseConverter):
    """Converts HL7 VXU messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str]]:
        resources = []
        warnings = []

        patient_id = make_id()

        # Build Patient
        patient = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)

        # Build Immunization resources from RXA segments
        for rxa in parsed_msg.get_all_segments("RXA"):
            immunization_id = make_id()
            immunization, additional_resources = self._build_immunization(parsed_msg, immunization_id, patient_id, rxa, warnings)
            resources.append(immunization)
            resources.extend(additional_resources)

        return resources, warnings

    def _build_patient(self, parsed_msg: ParsedHL7Message, patient_id: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR Patient resource from PID segment."""
        pid = parsed_msg.get_segment("PID")
        if not pid:
            warnings.append("VXU message missing PID segment")
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

    def _build_immunization(self, parsed_msg: ParsedHL7Message, immunization_id: str, patient_id: str, rxa: Any, warnings: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build FHIR Immunization resource from RXA segment."""
        if not rxa:
            warnings.append("VXU message missing RXA segment")
            return {
                "resourceType": "Immunization",
                "id": immunization_id,
                "status": "completed",
                "patient": {"reference": f"Patient/{patient_id}"},
                "vaccineCode": {"coding": [{"system": "http://hl7.org/fhir/sid/cvx", "code": "unknown"}]},
                "occurrenceDateTime": parse_hl7_datetime(safe_str(None)),
            }, []

        # Map VXU event to immunization status
        status_map = {
            "V04": "completed",   # Unsolicited vaccination record update
        }
        status = status_map.get(parsed_msg.message_event, "completed")

        immunization = {
            "resourceType": "Immunization",
            "id": immunization_id,
            "status": status,
            "vaccineCode": {"coding": [extract_coding(rxa[5])]},  # Administered code
            "patient": {"reference": f"Patient/{patient_id}"},
            "occurrenceDateTime": parse_hl7_datetime(safe_str(rxa[3])),  # Date/time start of administration
            "primarySource": True,
            "lotNumber": safe_str(rxa[15]),
            "site": {"coding": [extract_coding(rxa[9])]},  # Administration site
            "route": {"coding": [extract_coding(rxa[10])]},  # Administration route
            "doseQuantity": {
                "value": float(safe_str(rxa[6]) or "1"),  # Administered amount
                "unit": safe_str(rxa[7]),  # Administered units
            },
        }

        additional_resources = []

        # Add manufacturer from RXA
        if rxa[17]:  # Manufacturer
            manufacturer_id = make_id()
            manufacturer = {
                "resourceType": "Organization",
                "id": manufacturer_id,
                "identifier": [extract_identifier(rxa[17])],
                "name": safe_str(rxa[17]),
            }
            additional_resources.append(manufacturer)
            immunization["manufacturer"] = {"reference": f"Organization/{manufacturer_id}"}

        # Add performer from RXA
        if rxa[10]:  # Administering provider
            performer_id = make_id()
            performer = {
                "resourceType": "Practitioner",
                "id": performer_id,
                "identifier": [extract_identifier(rxa[10])],
                "name": [extract_name(rxa[10])],
            }
            additional_resources.append(performer)
            immunization["performer"] = [{"actor": {"reference": f"Practitioner/{performer_id}"}}]

        return immunization, additional_resources

    def _map_gender(self, gender_field: Any) -> str:
        """Map HL7 gender codes to FHIR gender."""
        gender_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}
        gender = safe_str(gender_field).upper()
        return gender_map.get(gender, "unknown")