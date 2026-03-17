"""
DFT (Detailed Financial Transaction) message converter.

Produces: Patient, Claim, Organization, Practitioner resources.
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


class DFTConverter(BaseConverter):
    """Converts HL7 DFT messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str]]:
        resources = []
        warnings = []

        patient_id = make_id()
        claim_id = make_id()

        # Build Patient
        patient = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)

        # Build Claim
        claim, additional_resources = self._build_claim(parsed_msg, claim_id, patient_id, warnings)
        resources.append(claim)
        resources.extend(additional_resources)

        return resources, warnings

    def _build_patient(self, parsed_msg: ParsedHL7Message, patient_id: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR Patient resource from PID segment."""
        pid = parsed_msg.get_segment("PID")
        if not pid:
            warnings.append("DFT message missing PID segment")
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

    def _build_claim(self, parsed_msg: ParsedHL7Message, claim_id: str, patient_id: str, warnings: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build FHIR Claim resource from FT1 and other segments."""
        ft1 = parsed_msg.get_segment("FT1")
        if not ft1:
            warnings.append("DFT message missing FT1 segment")
            return {
                "resourceType": "Claim",
                "id": claim_id,
                "status": "active",
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type", "code": "institutional"}]},
                "patient": {"reference": f"Patient/{patient_id}"},
                "created": parse_hl7_datetime(safe_str(None)),
            }, []

        # Map DFT event to claim status
        status_map = {
            "P03": "active",      # Post detail financial transaction
            "P04": "cancelled",   # Generate bill and reverse/adjust on previous bill
        }
        status = status_map.get(parsed_msg.message_event, "active")

        claim = {
            "resourceType": "Claim",
            "id": claim_id,
            "status": status,
            "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type", "code": "institutional"}]},
            "subType": {"coding": [extract_coding(ft1[6])]},  # Transaction type
            "use": "claim",
            "patient": {"reference": f"Patient/{patient_id}"},
            "created": parse_hl7_datetime(safe_str(ft1[4])),  # Transaction date
            "provider": {},
            "priority": {"coding": [{"code": "normal"}]},
            "item": [],
        }

        # Add claim items from FT1
        if ft1[7]:  # Transaction amount
            item = {
                "sequence": 1,
                "productOrService": {"coding": [extract_coding(ft1[25])]},  # Procedure code
                "net": {"value": float(safe_str(ft1[7]) or "0"), "currency": safe_str(ft1[8]) or "USD"},
            }
            claim["item"].append(item)

        additional_resources = []

        # Add provider from PV1
        pv1 = parsed_msg.get_segment("PV1")
        if pv1 and pv1[8]:  # Attending doctor
            practitioner_id = make_id()
            practitioner = {
                "resourceType": "Practitioner",
                "id": practitioner_id,
                "identifier": [extract_identifier(pv1[8])],
                "name": [extract_name(pv1[8])],
            }
            additional_resources.append(practitioner)
            claim["provider"] = {"reference": f"Practitioner/{practitioner_id}"}

        return claim, additional_resources

    def _map_gender(self, gender_field: Any) -> str:
        """Map HL7 gender codes to FHIR gender."""
        gender_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}
        gender = safe_str(gender_field).upper()
        return gender_map.get(gender, "unknown")