"""
SIU (Scheduling Information Unsolicited) message converter.

Produces: Patient, Encounter, Practitioner, Organization, Appointment resources.
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


class SIUConverter(BaseConverter):
    """Converts HL7 SIU messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str]]:
        resources = []
        warnings = []

        patient_id = make_id()
        encounter_id = make_id()
        appointment_id = make_id()

        # Build Patient
        patient = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)

        # Build Appointment
        appointment, additional_resources = self._build_appointment(parsed_msg, appointment_id, patient_id, warnings)
        resources.append(appointment)
        resources.extend(additional_resources)

        # Build Encounter if applicable
        if parsed_msg.message_event in ["S12", "S13", "S14", "S15", "S16", "S17"]:
            encounter = self._build_encounter(parsed_msg, encounter_id, patient_id, warnings)
            resources.append(encounter)

        return resources, warnings

    def _build_patient(self, parsed_msg: ParsedHL7Message, patient_id: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR Patient resource from PID segment."""
        pid = parsed_msg.get_segment("PID")
        if not pid:
            warnings.append("SIU message missing PID segment")
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

    def _build_appointment(self, parsed_msg: ParsedHL7Message, appointment_id: str, patient_id: str, warnings: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build FHIR Appointment resource from SCH segment."""
        sch = parsed_msg.get_segment("SCH")
        if not sch:
            warnings.append("SIU message missing SCH segment")
            return {
                "resourceType": "Appointment",
                "id": appointment_id,
                "status": "proposed",
                "participant": [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}],
            }, []

        # Map SIU event to appointment status
        status_map = {
            "S12": "booked",      # New appointment
            "S13": "booked",      # New appointment
            "S14": "pending",     # Updated appointment
            "S15": "cancelled",   # Cancelled appointment
            "S16": "noshow",      # No show
            "S17": "arrived",     # Arrived
        }
        status = status_map.get(parsed_msg.message_event, "proposed")

        appointment = {
            "resourceType": "Appointment",
            "id": appointment_id,
            "status": status,
            "serviceType": [{"coding": [extract_coding(sch[1])]}],
            "reasonCode": [{"coding": [extract_coding(sch[7])]}],
            "description": safe_str(sch[8]),
            "start": parse_hl7_datetime(safe_str(sch[11])),
            "end": parse_hl7_datetime(safe_str(sch[12])),
            "participant": [
                {"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}
            ],
        }

        additional_resources = []

        # Add practitioners from AIP segments
        for aip in parsed_msg.get_all_segments("AIP"):
            if aip[3]:  # Resource ID
                practitioner_id = make_id()
                practitioner = {
                    "resourceType": "Practitioner",
                    "id": practitioner_id,
                    "identifier": [extract_identifier(aip[3])],
                    "name": [extract_name(aip[3])],
                }
                additional_resources.append(practitioner)
                appointment["participant"].append({
                    "actor": {"reference": f"Practitioner/{practitioner_id}"},
                    "status": "accepted"
                })

        return appointment, additional_resources

    def _build_encounter(self, parsed_msg: ParsedHL7Message, encounter_id: str, patient_id: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR Encounter resource."""
        pv1 = parsed_msg.get_segment("PV1")
        encounter = {
            "resourceType": "Encounter",
            "id": encounter_id,
            "status": "in-progress",
            "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
            "subject": {"reference": f"Patient/{patient_id}"},
        }

        if pv1:
            encounter["period"] = {"start": parse_hl7_datetime(safe_str(pv1[44]))}

        return encounter

    def _map_gender(self, gender_field: Any) -> str:
        """Map HL7 gender codes to FHIR gender."""
        gender_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}
        gender = safe_str(gender_field).upper()
        return gender_map.get(gender, "unknown")