"""
ADT (Admit/Discharge/Transfer) message converter.

Produces: Patient, Encounter, Practitioner, Organization resources.
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


# Maps HL7 administrative sex codes to FHIR gender values
GENDER_MAP = {
    "M": "male",
    "F": "female",
    "O": "other",
    "U": "unknown",
    "A": "other",
    "N": "unknown",
}

# Maps ADT event codes to FHIR Encounter status
ADT_EVENT_STATUS = {
    "A01": "in-progress",   # Admit
    "A02": "in-progress",   # Transfer
    "A03": "finished",      # Discharge
    "A04": "in-progress",   # Register
    "A05": "planned",       # Pre-admit
    "A06": "in-progress",   # Change patient class
    "A07": "in-progress",
    "A08": "in-progress",   # Update patient info
    "A09": "in-progress",
    "A10": "in-progress",
    "A11": "cancelled",     # Cancel admit
    "A12": "cancelled",     # Cancel transfer
    "A13": "cancelled",     # Cancel discharge
    "A28": "in-progress",   # Add person
    "A31": "in-progress",   # Update person
    "A40": "in-progress",   # Merge patient
}

# Maps HL7 patient class (PV1-2) to FHIR Encounter class
PATIENT_CLASS_MAP = {
    "I": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP", "display": "inpatient encounter"},
    "O": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
    "E": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "EMER", "display": "emergency"},
    "P": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "PRENC", "display": "pre-admission"},
    "R": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP", "display": "recurring patient"},
    "B": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP", "display": "obstetrics"},
    "C": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP", "display": "commercial account"},
    "N": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "not applicable"},
    "U": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "unknown"},
}


def _seg(parsed_msg: ParsedHL7Message, name: str):
    return parsed_msg.get_segment(name)


def _field(seg, idx: int, component: int = 1) -> str:
    """Safely get a field/component from a segment."""
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


class ADTConverter(BaseConverter):
    """Converts HL7 ADT messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str]]:
        resources = []
        warnings = []

        patient_id = make_id()
        encounter_id = make_id()
        org_id = make_id()

        # Build Patient
        patient = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)

        # Build Organization from sending facility (MSH-4)
        org = self._build_organization(parsed_msg, org_id)
        if org:
            resources.append(org)

        # Build Practitioners from PV1
        practitioners = self._build_practitioners(parsed_msg)
        resources.extend(practitioners)

        # Build Encounter
        encounter = self._build_encounter(
            parsed_msg,
            encounter_id,
            patient_id,
            org_id if org else None,
            practitioners,
            warnings,
        )
        resources.append(encounter)

        return resources, warnings

    # ------------------------------------------------------------------
    def _build_patient(self, msg: ParsedHL7Message, patient_id: str, warnings: list) -> Dict:
        pid = _seg(msg, "PID")
        resource: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": patient_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Patient"]
            },
        }

        if pid is None:
            warnings.append("PID segment missing — Patient resource will be incomplete.")
            return resource

        # Identifiers (PID-3 repeating, PID-2 alternate, PID-4 alt account)
        identifiers = []
        for pid3 in str(pid[3]).split("~"):  # repeating field
            if pid3.strip():
                ident = extract_identifier(pid3, "http://hospital.example.org/mrn")
                identifiers.append(ident)
        pid2 = _field(pid, 2)
        if pid2:
            identifiers.append({"system": "http://hospital.example.org/patid", "value": pid2})
        if identifiers:
            resource["identifier"] = identifiers

        # Name (PID-5 repeating, PID-9 alias)
        names = []
        for name_raw in str(pid[5]).split("~"):
            if name_raw.strip():
                names.append(extract_name(name_raw))
        alias_raw = safe_str(pid[9]) if len(pid) > 9 else ""
        if alias_raw:
            alias_name = extract_name(alias_raw)
            alias_name["use"] = "nickname"
            names.append(alias_name)
        if names:
            resource["name"] = names

        # Date of birth (PID-7)
        dob = parse_hl7_date(_field(pid, 7))
        if dob:
            resource["birthDate"] = dob

        # Gender (PID-8)
        sex_code = _field(pid, 8).upper()
        resource["gender"] = GENDER_MAP.get(sex_code, "unknown")

        # Address (PID-11)
        try:
            addr_raw = str(pid[11]).strip()
            if addr_raw:
                addr = extract_address(addr_raw)
                if addr:
                    resource["address"] = [addr]
        except Exception:
            pass

        # Telecom (PID-13 home phone, PID-14 work phone)
        try:
            telecoms = extract_telecom(
                pid[13] if len(pid) > 13 else "",
                pid[14] if len(pid) > 14 else ""
            )
            if telecoms:
                if len(telecoms) > 1:
                    telecoms[1]["use"] = "work"
                resource["telecom"] = telecoms
        except Exception:
            pass

        # Marital status (PID-16)
        try:
            marital = _field(pid, 16)
            if marital:
                resource["maritalStatus"] = extract_coding(
                    marital, "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus"
                )
        except Exception:
            pass

        # Language (PID-15)
        try:
            lang = _field(pid, 15)
            if lang:
                resource["communication"] = [{"language": {"text": lang}, "preferred": True}]
        except Exception:
            pass

        # Death indicator (PID-30, PID-29)
        try:
            deceased_flag = _field(pid, 30).upper()
            if deceased_flag == "Y":
                resource["deceasedBoolean"] = True
            elif deceased_flag == "N":
                resource["deceasedBoolean"] = False
            else:
                death_dt = parse_hl7_datetime(_field(pid, 29))
                if death_dt:
                    resource["deceasedDateTime"] = death_dt
        except Exception:
            pass

        return resource

    # ------------------------------------------------------------------
    def _build_organization(self, msg: ParsedHL7Message, org_id: str) -> Dict | None:
        facility = msg.sending_facility
        msh = _seg(msg, "MSH")
        org_name = _field(msh, 4, 1)
        if not org_name:
            org_name = facility

        if not org_name:
            return None

        return {
            "resourceType": "Organization",
            "id": org_id,
            "name": org_name,
        }

    # ------------------------------------------------------------------
    def _build_practitioners(self, msg: ParsedHL7Message) -> List[Dict]:
        pv1 = _seg(msg, "PV1")
        practitioners = []
        if pv1 is None:
            return practitioners

        # PV1-7 Attending, PV1-8 Referring, PV1-9 Consulting, PV1-17 Admitting
        roles = [
            (7, "attending", "Attending Physician"),
            (8, "referring", "Referring Physician"),
            (9, "consultant", "Consulting Physician"),
            (17, "admitting", "Admitting Physician"),
        ]
        for field_idx, role_code, role_display in roles:
            try:
                raw = str(pv1[field_idx]).strip() if len(pv1) > field_idx else ""
                if not raw:
                    continue
                parts = raw.split("^")
                npi = parts[0].strip()
                family = parts[1].strip() if len(parts) > 1 else ""
                given = parts[2].strip() if len(parts) > 2 else ""

                prac: Dict[str, Any] = {
                    "resourceType": "Practitioner",
                    "id": make_id(),
                }
                if npi:
                    prac["identifier"] = [{"system": "http://hl7.org/fhir/sid/us-npi", "value": npi}]
                name: Dict[str, Any] = {"use": "official"}
                if family:
                    name["family"] = family
                if given:
                    name["given"] = [given]
                prac["name"] = [name]
                # Store role for reference building
                prac["_role"] = {"code": role_code, "display": role_display}
                practitioners.append(prac)
            except Exception:
                continue

        return practitioners

    # ------------------------------------------------------------------
    def _build_encounter(
        self,
        msg: ParsedHL7Message,
        encounter_id: str,
        patient_id: str,
        org_id: str | None,
        practitioners: List[Dict],
        warnings: list,
    ) -> Dict:
        pv1 = _seg(msg, "PV1")
        evn = _seg(msg, "EVN")

        status = ADT_EVENT_STATUS.get(msg.message_event, "unknown")
        encounter: Dict[str, Any] = {
            "resourceType": "Encounter",
            "id": encounter_id,
            "status": status,
            "subject": {"reference": f"Patient/{patient_id}"},
        }

        # Class (PV1-2)
        if pv1 is not None:
            try:
                patient_class = _field(pv1, 2).upper()
                class_coding = PATIENT_CLASS_MAP.get(
                    patient_class,
                    {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"}
                )
                encounter["class"] = class_coding
            except Exception:
                encounter["class"] = {"code": "AMB"}
        else:
            encounter["class"] = {"code": "AMB"}

        # Visit number (PV1-19)
        if pv1 is not None:
            try:
                visit_num = _field(pv1, 19)
                if visit_num:
                    encounter["identifier"] = [
                        {"system": "http://hospital.example.org/visit", "value": visit_num}
                    ]
            except Exception:
                pass

        # Admission/discharge times
        period = {}
        if pv1 is not None:
            try:
                admit_raw = _field(pv1, 44)
                if admit_raw:
                    admit_dt = parse_hl7_datetime(admit_raw)
                    if admit_dt:
                        period["start"] = admit_dt
                discharge_raw = _field(pv1, 45)
                if discharge_raw:
                    discharge_dt = parse_hl7_datetime(discharge_raw)
                    if discharge_dt:
                        period["end"] = discharge_dt
            except Exception:
                pass
        # Fallback to EVN-2 if no admit time
        if not period.get("start") and evn is not None:
            try:
                evn2 = _field(evn, 2)
                if evn2:
                    dt = parse_hl7_datetime(evn2)
                    if dt:
                        period["start"] = dt
            except Exception:
                pass
        if period:
            encounter["period"] = period

        # Service provider (organization)
        if org_id:
            encounter["serviceProvider"] = {"reference": f"Organization/{org_id}"}

        # Practitioners as participants
        participants = []
        for prac in practitioners:
            role_info = prac.pop("_role", None)
            if role_info:
                participants.append({
                    "type": [{
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                            "code": role_info["code"],
                            "display": role_info["display"],
                        }]
                    }],
                    "individual": {"reference": f"Practitioner/{prac['id']}"},
                })
        if participants:
            encounter["participant"] = participants

        # Discharge disposition (PV1-36)
        if pv1 is not None:
            try:
                dispo = _field(pv1, 36)
                if dispo:
                    encounter["hospitalization"] = {
                        "dischargeDisposition": extract_coding(
                            dispo,
                            "http://terminology.hl7.org/CodeSystem/discharge-disposition"
                        )
                    }
            except Exception:
                pass

        # Reason for visit / admission diagnosis (DG1 segment)
        dg1 = _seg(msg, "DG1")
        if dg1 is not None:
            try:
                diag_code = str(dg1[3]).strip()
                if diag_code:
                    encounter["reasonCode"] = [extract_coding(diag_code, "http://hl7.org/fhir/sid/icd-10")]
            except Exception:
                pass

        return encounter
