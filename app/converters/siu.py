"""
SIU (Scheduling Information Unsolicited) message converter.

Produces: Patient, Appointment, Encounter, Practitioner, Organization resources.
"""
from typing import Any, Dict, List, Tuple

from app.converters.base import (
    BaseConverter,
    make_id,
    safe_str,
    parse_hl7_datetime,
    parse_hl7_date,
    extract_name,
    extract_address,
    extract_telecom,
    extract_identifier,
    extract_coding,
)
from app.core.parser import ParsedHL7Message
from app.models.schemas import FieldMapping, ResourceMapping


GENDER_MAP = {
    "M": "male",
    "F": "female",
    "O": "other",
    "U": "unknown",
    "A": "other",
    "N": "unknown",
}

SIU_APPOINTMENT_STATUS = {
    "S12": "booked",
    "S13": "booked",
    "S14": "pending",
    "S15": "cancelled",
    "S16": "noshow",
    "S17": "arrived",
    "S18": "waitlist",
    "S19": "cancelled",
    "S20": "cancelled",
    "S21": "cancelled",
    "S22": "cancelled",
    "S23": "booked",
    "S24": "booked",
    "S25": "booked",
    "S26": "cancelled",
}


def _seg(parsed_msg, name):
    return parsed_msg.get_segment(name)


def _field(seg, idx: int, component: int = 1) -> str:
    if seg is None:
        return ""
    try:
        val = str(seg[idx]).strip()
        if component > 1:
            parts = val.split("^")
            return parts[component - 1].strip() if len(parts) >= component else ""
        return val
    except Exception:
        return ""


class SIUConverter(BaseConverter):
    """Converts HL7 SIU messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[ResourceMapping]]:
        resources = []
        warnings = []
        field_mappings = []

        patient_id = make_id()
        appointment_id = make_id()
        encounter_id = make_id()
        org_id = make_id()

        # Build Patient
        patient, patient_mappings = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)
        if patient_mappings:
            field_mappings.append(ResourceMapping(
                resource_type="Patient",
                resource_id=patient_id,
                field_mappings=patient_mappings
            ))

        # Build Organization from MSH-4
        org, org_mappings = self._build_organization(parsed_msg, org_id)
        if org:
            resources.append(org)
            if org_mappings:
                field_mappings.append(ResourceMapping(
                    resource_type="Organization",
                    resource_id=org_id,
                    field_mappings=org_mappings
                ))

        # Build Appointment + Practitioners
        appointment, practitioners, appt_mappings, prac_mappings_list = self._build_appointment(
            parsed_msg, appointment_id, patient_id, org_id if org else None, warnings
        )
        resources.extend(practitioners)
        resources.append(appointment)

        for i, prac in enumerate(practitioners):
            if i < len(prac_mappings_list) and prac_mappings_list[i]:
                field_mappings.append(ResourceMapping(
                    resource_type="Practitioner",
                    resource_id=prac["id"],
                    field_mappings=prac_mappings_list[i]
                ))

        if appt_mappings:
            field_mappings.append(ResourceMapping(
                resource_type="Appointment",
                resource_id=appointment_id,
                field_mappings=appt_mappings
            ))

        # Build Encounter for relevant event types
        if parsed_msg.message_event in ["S12", "S13", "S14", "S15", "S16", "S17"]:
            encounter, enc_mappings = self._build_encounter(parsed_msg, encounter_id, patient_id, warnings)
            resources.append(encounter)
            if enc_mappings:
                field_mappings.append(ResourceMapping(
                    resource_type="Encounter",
                    resource_id=encounter_id,
                    field_mappings=enc_mappings
                ))

        return resources, warnings, field_mappings

    # ------------------------------------------------------------------
    def _build_patient(self, msg: ParsedHL7Message, patient_id: str, warnings: list) -> Tuple[Dict, List[FieldMapping]]:
        pid = _seg(msg, "PID")
        resource: Dict[str, Any] = {"resourceType": "Patient", "id": patient_id}
        mappings: List[FieldMapping] = []

        if pid is None:
            warnings.append("PID segment missing — Patient resource will be incomplete.")
            return resource, mappings

        # Identifiers (PID-3)
        identifiers = []
        for pid3 in str(pid[3]).split("~"):
            if pid3.strip():
                identifiers.append(extract_identifier(pid3, "http://hospital.example.org/mrn"))
                mappings.append(FieldMapping(
                    fhir_field="identifier",
                    hl7_segment="PID",
                    hl7_field="3",
                    hl7_value=pid3.strip(),
                    description="Patient identifier/MRN"
                ))
        if identifiers:
            resource["identifier"] = identifiers

        # Name (PID-5)
        names = []
        for name_raw in str(pid[5]).split("~"):
            if name_raw.strip():
                names.append(extract_name(name_raw))
                mappings.append(FieldMapping(
                    fhir_field="name",
                    hl7_segment="PID",
                    hl7_field="5",
                    hl7_value=name_raw.strip(),
                    description="Patient name"
                ))
        if names:
            resource["name"] = names

        # DOB (PID-7)
        dob_raw = _field(pid, 7)
        dob = parse_hl7_date(dob_raw)
        if dob:
            resource["birthDate"] = dob
            mappings.append(FieldMapping(
                fhir_field="birthDate",
                hl7_segment="PID",
                hl7_field="7",
                hl7_value=dob_raw,
                description="Date of birth"
            ))

        # Gender (PID-8)
        sex_code = _field(pid, 8).upper()
        resource["gender"] = GENDER_MAP.get(sex_code, "unknown")
        if sex_code:
            mappings.append(FieldMapping(
                fhir_field="gender",
                hl7_segment="PID",
                hl7_field="8",
                hl7_value=sex_code,
                description="Administrative sex"
            ))

        # Address (PID-11)
        try:
            addr_raw = str(pid[11]).strip()
            if addr_raw:
                addr = extract_address(addr_raw)
                if addr:
                    resource["address"] = [addr]
                    mappings.append(FieldMapping(
                        fhir_field="address",
                        hl7_segment="PID",
                        hl7_field="11",
                        hl7_value=addr_raw,
                        description="Patient address"
                    ))
        except Exception:
            pass

        # Telecom
        try:
            telecoms = extract_telecom(
                pid[13] if len(pid) > 13 else "",
                pid[14] if len(pid) > 14 else ""
            )
            if telecoms:
                if len(telecoms) > 1:
                    telecoms[1]["use"] = "work"
                resource["telecom"] = telecoms
                if len(pid) > 13 and pid[13]:
                    mappings.append(FieldMapping(
                        fhir_field="telecom",
                        hl7_segment="PID",
                        hl7_field="13",
                        hl7_value=str(pid[13]),
                        description="Home phone number"
                    ))
        except Exception:
            pass

        return resource, mappings

    # ------------------------------------------------------------------
    def _build_organization(self, msg: ParsedHL7Message, org_id: str) -> Tuple[Dict | None, List[FieldMapping]]:
        msh = _seg(msg, "MSH")
        org_name = _field(msh, 4, 1) or msg.sending_facility
        if not org_name:
            return None, []
        mappings = [FieldMapping(
            fhir_field="name",
            hl7_segment="MSH",
            hl7_field="4",
            hl7_value=org_name,
            description="Sending facility/organization name"
        )]
        return {"resourceType": "Organization", "id": org_id, "name": org_name}, mappings

    # ------------------------------------------------------------------
    def _build_appointment(
        self,
        msg: ParsedHL7Message,
        appointment_id: str,
        patient_id: str,
        org_id: str | None,
        warnings: list,
    ) -> Tuple[Dict, List[Dict], List[FieldMapping], List[List[FieldMapping]]]:
        sch = _seg(msg, "SCH")
        mappings: List[FieldMapping] = []
        practitioners: List[Dict] = []
        prac_mappings_list: List[List[FieldMapping]] = []

        status = SIU_APPOINTMENT_STATUS.get(msg.message_event, "proposed")
        mappings.append(FieldMapping(
            fhir_field="status",
            hl7_segment="MSH",
            hl7_field="9",
            hl7_value=msg.message_event,
            description=f"Appointment status from event ({status})"
        ))

        appointment: Dict[str, Any] = {
            "resourceType": "Appointment",
            "id": appointment_id,
            "status": status,
            "participant": [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}],
        }

        if sch is None:
            warnings.append("SCH segment missing — Appointment will be incomplete.")
            return appointment, practitioners, mappings, prac_mappings_list

        # Appointment ID (SCH-1)
        appt_id_raw = _field(sch, 1)
        if appt_id_raw:
            appointment["identifier"] = [{"system": "http://hospital.example.org/appointment", "value": appt_id_raw}]
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="SCH",
                hl7_field="1",
                hl7_value=appt_id_raw,
                description="Appointment placer ID"
            ))

        # Service type (SCH-7 / SCH-8)
        svc_type = _field(sch, 7)
        if svc_type:
            appointment["serviceType"] = [{"coding": [extract_coding(svc_type, "http://snomed.info/sct")]}]
            mappings.append(FieldMapping(
                fhir_field="serviceType",
                hl7_segment="SCH",
                hl7_field="7",
                hl7_value=svc_type,
                description="Appointment service type"
            ))

        # Reason code (SCH-6)
        reason = _field(sch, 6)
        if reason:
            appointment["reasonCode"] = [{"coding": [extract_coding(reason, "http://snomed.info/sct")]}]
            mappings.append(FieldMapping(
                fhir_field="reasonCode",
                hl7_segment="SCH",
                hl7_field="6",
                hl7_value=reason,
                description="Appointment reason"
            ))

        # Description (SCH-8)
        description = _field(sch, 8)
        if description:
            appointment["description"] = description
            mappings.append(FieldMapping(
                fhir_field="description",
                hl7_segment="SCH",
                hl7_field="8",
                hl7_value=description,
                description="Appointment description"
            ))

        # Duration (SCH-9 = duration, SCH-10 = duration units)
        duration_raw = _field(sch, 9)
        if duration_raw:
            try:
                appointment["minutesDuration"] = int(float(duration_raw))
                mappings.append(FieldMapping(
                    fhir_field="minutesDuration",
                    hl7_segment="SCH",
                    hl7_field="9",
                    hl7_value=duration_raw,
                    description="Appointment duration"
                ))
            except Exception:
                pass

        # Start time (SCH-11) — TQ1-style: repeat pattern^explicit time^...
        start_raw = _field(sch, 11)
        if start_raw:
            # SCH-11 is a timing quantity; component 4 = start date/time
            parts = start_raw.split("^")
            start_dt_str = parts[3].strip() if len(parts) > 3 else parts[0].strip()
            start_dt = parse_hl7_datetime(start_dt_str)
            if start_dt:
                appointment["start"] = start_dt
                mappings.append(FieldMapping(
                    fhir_field="start",
                    hl7_segment="SCH",
                    hl7_field="11",
                    hl7_value=start_raw,
                    description="Appointment start date/time"
                ))

        # End time (SCH-12)
        end_raw = _field(sch, 12)
        if end_raw:
            end_dt = parse_hl7_datetime(end_raw)
            if end_dt:
                appointment["end"] = end_dt
                mappings.append(FieldMapping(
                    fhir_field="end",
                    hl7_segment="SCH",
                    hl7_field="12",
                    hl7_value=end_raw,
                    description="Appointment end date/time"
                ))

        # Practitioners from AIP segments (individual resource participants)
        for aip in msg.get_all_segments("AIP"):
            try:
                raw = str(aip[3]).strip() if len(aip) > 3 else ""
                if not raw:
                    continue
                parts = raw.split("^")
                npi = parts[0].strip()
                family = parts[1].strip() if len(parts) > 1 else ""
                given = parts[2].strip() if len(parts) > 2 else ""
                prac_id = make_id()
                prac: Dict[str, Any] = {"resourceType": "Practitioner", "id": prac_id}
                prac_maps: List[FieldMapping] = []
                if npi:
                    prac["identifier"] = [{"system": "http://hl7.org/fhir/sid/us-npi", "value": npi}]
                    prac_maps.append(FieldMapping(
                        fhir_field="identifier",
                        hl7_segment="AIP",
                        hl7_field="3",
                        hl7_value=npi,
                        description="Practitioner NPI"
                    ))
                name: Dict[str, Any] = {"use": "official"}
                if family:
                    name["family"] = family
                if given:
                    name["given"] = [given]
                prac["name"] = [name]
                if family or given:
                    prac_maps.append(FieldMapping(
                        fhir_field="name",
                        hl7_segment="AIP",
                        hl7_field="3",
                        hl7_value=raw,
                        description="Practitioner name"
                    ))
                practitioners.append(prac)
                prac_mappings_list.append(prac_maps)
                appointment["participant"].append({
                    "actor": {"reference": f"Practitioner/{prac_id}"},
                    "status": "accepted"
                })
                mappings.append(FieldMapping(
                    fhir_field="participant",
                    hl7_segment="AIP",
                    hl7_field="3",
                    hl7_value=raw,
                    description="Appointment participant practitioner"
                ))
            except Exception:
                continue

        # Location participants from AIL segments
        for ail in msg.get_all_segments("AIL"):
            try:
                loc_raw = str(ail[3]).strip() if len(ail) > 3 else ""
                if not loc_raw:
                    continue
                loc_id = make_id()
                location: Dict[str, Any] = {
                    "resourceType": "Location",
                    "id": loc_id,
                    "name": loc_raw,
                }
                # Attach location as a participant (not standard but common practice)
                appointment["participant"].append({
                    "actor": {"reference": f"Location/{loc_id}"},
                    "status": "accepted"
                })
                mappings.append(FieldMapping(
                    fhir_field="participant",
                    hl7_segment="AIL",
                    hl7_field="3",
                    hl7_value=loc_raw,
                    description="Appointment location"
                ))
            except Exception:
                continue

        return appointment, practitioners, mappings, prac_mappings_list

    # ------------------------------------------------------------------
    def _build_encounter(
        self,
        msg: ParsedHL7Message,
        encounter_id: str,
        patient_id: str,
        warnings: list,
    ) -> Tuple[Dict, List[FieldMapping]]:
        pv1 = _seg(msg, "PV1")
        mappings: List[FieldMapping] = []

        encounter: Dict[str, Any] = {
            "resourceType": "Encounter",
            "id": encounter_id,
            "status": "in-progress",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "AMB",
                "display": "ambulatory",
            },
            "subject": {"reference": f"Patient/{patient_id}"},
        }
        mappings.append(FieldMapping(
            fhir_field="status",
            hl7_segment="MSH",
            hl7_field="9",
            hl7_value=msg.message_event,
            description="Encounter status (in-progress for scheduling events)"
        ))

        if pv1 is not None:
            admit_raw = _field(pv1, 44)
            if admit_raw:
                admit_dt = parse_hl7_datetime(admit_raw)
                if admit_dt:
                    encounter["period"] = {"start": admit_dt}
                    mappings.append(FieldMapping(
                        fhir_field="period.start",
                        hl7_segment="PV1",
                        hl7_field="44",
                        hl7_value=admit_raw,
                        description="Admission date/time"
                    ))

        return encounter, mappings

    def _map_gender(self, gender_field: Any) -> str:
        gender = safe_str(gender_field).upper()
        return GENDER_MAP.get(gender, "unknown")
