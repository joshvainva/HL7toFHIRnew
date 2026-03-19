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
    map_z_segments_to_extensions,
)
from app.core.parser import ParsedHL7Message
from app.models.schemas import FieldMapping, ResourceMapping


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

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[ResourceMapping]]:
        resources = []
        warnings = []
        field_mappings = []

        patient_id = make_id()
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

        # Build Organization from sending facility (MSH-4)
        org, org_mappings = self._build_organization(parsed_msg, org_id)
        if org:
            resources.append(org)
            if org_mappings:
                field_mappings.append(ResourceMapping(
                    resource_type="Organization",
                    resource_id=org_id,
                    field_mappings=org_mappings
                ))

        # Build Practitioners from PV1
        practitioners, practitioner_mappings = self._build_practitioners(parsed_msg)
        resources.extend(practitioners)
        for i, prac_mapping in enumerate(practitioner_mappings):
            if prac_mapping and i < len(practitioners):
                field_mappings.append(ResourceMapping(
                    resource_type="Practitioner",
                    resource_id=practitioners[i]["id"],
                    field_mappings=prac_mapping
                ))

        # Build Encounter
        encounter, encounter_mappings = self._build_encounter(
            parsed_msg,
            encounter_id,
            patient_id,
            org_id if org else None,
            practitioners,
            warnings,
        )
        resources.append(encounter)
        if encounter_mappings:
            field_mappings.append(ResourceMapping(
                resource_type="Encounter",
                resource_id=encounter_id,
                field_mappings=encounter_mappings
            ))

        return resources, warnings, field_mappings

    # ------------------------------------------------------------------
    def _build_patient(self, msg: ParsedHL7Message, patient_id: str, warnings: list) -> Tuple[Dict, List[FieldMapping]]:
        pid = _seg(msg, "PID")
        resource: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": patient_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Patient"]
            },
        }
        mappings = []

        if pid is None:
            warnings.append("PID segment missing — Patient resource will be incomplete.")
            return resource, mappings

        # Identifiers (PID-3 repeating, PID-2 alternate, PID-4 alt account)
        identifiers = []
        for pid3 in str(pid[3]).split("~"):  # repeating field
            if pid3.strip():
                ident = extract_identifier(pid3, "http://hospital.example.org/mrn")
                identifiers.append(ident)
                mappings.append(FieldMapping(
                    fhir_field="identifier",
                    hl7_segment="PID",
                    hl7_field="3",
                    hl7_value=pid3.strip(),
                    description="Patient identifier/MRN"
                ))
        # PID-2: alternate patient ID — often Epic EPI or enterprise ID (may be repeating with ~)
        pid2_raw = safe_str(pid[2]) if len(pid) > 2 else ""
        for pid2_rep in pid2_raw.split("~"):
            pid2_rep = pid2_rep.strip()
            if pid2_rep:
                identifiers.append(extract_identifier(pid2_rep, "http://hospital.example.org/patid"))
                mappings.append(FieldMapping(
                    fhir_field="identifier",
                    hl7_segment="PID",
                    hl7_field="2",
                    hl7_value=pid2_rep,
                    description="Alternate patient ID (Epic EPI / Enterprise)"
                ))
        if identifiers:
            resource["identifier"] = identifiers

        # Name (PID-5 repeating, PID-9 alias)
        names = []
        for name_raw in str(pid[5]).split("~"):
            if name_raw.strip():
                names.append(extract_name(name_raw))
                mappings.append(FieldMapping(
                    fhir_field="name",
                    hl7_segment="PID",
                    hl7_field="5",
                    hl7_value=name_raw.strip(),
                    description="Patient name (family^given^middle^suffix^prefix)"
                ))
        alias_raw = safe_str(pid[9]) if len(pid) > 9 else ""
        if alias_raw:
            alias_name = extract_name(alias_raw)
            alias_name["use"] = "nickname"
            names.append(alias_name)
            mappings.append(FieldMapping(
                fhir_field="name",
                hl7_segment="PID",
                hl7_field="9",
                hl7_value=alias_raw,
                description="Patient alias name"
            ))
        if names:
            resource["name"] = names

        # Date of birth (PID-7)
        dob = parse_hl7_date(_field(pid, 7))
        if dob:
            resource["birthDate"] = dob
            mappings.append(FieldMapping(
                fhir_field="birthDate",
                hl7_segment="PID",
                hl7_field="7",
                hl7_value=_field(pid, 7),
                description="Date of birth (YYYYMMDD)"
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
                description=f"Administrative sex ({sex_code})"
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
                        description="Patient address (street^other^city^state^zip^country)"
                    ))
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
                if len(pid) > 13 and pid[13]:
                    mappings.append(FieldMapping(
                        fhir_field="telecom",
                        hl7_segment="PID",
                        hl7_field="13",
                        hl7_value=str(pid[13]),
                        description="Home phone number"
                    ))
                if len(pid) > 14 and pid[14]:
                    mappings.append(FieldMapping(
                        fhir_field="telecom",
                        hl7_segment="PID",
                        hl7_field="14",
                        hl7_value=str(pid[14]),
                        description="Work phone number"
                    ))
        except Exception:
            pass

        # Marital status (PID-16)
        try:
            marital = _field(pid, 16)
            if marital:
                resource["maritalStatus"] = extract_coding(
                    marital, "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus"
                )
                mappings.append(FieldMapping(
                    fhir_field="maritalStatus",
                    hl7_segment="PID",
                    hl7_field="16",
                    hl7_value=marital,
                    description="Marital status code"
                ))
        except Exception:
            pass

        # Language (PID-15)
        try:
            lang = _field(pid, 15)
            if lang:
                resource["communication"] = [{"language": {"text": lang}, "preferred": True}]
                mappings.append(FieldMapping(
                    fhir_field="communication",
                    hl7_segment="PID",
                    hl7_field="15",
                    hl7_value=lang,
                    description="Primary language"
                ))
        except Exception:
            pass

        # Death indicator (PID-30, PID-29)
        try:
            deceased_flag = _field(pid, 30).upper()
            if deceased_flag == "Y":
                resource["deceasedBoolean"] = True
                mappings.append(FieldMapping(
                    fhir_field="deceasedBoolean",
                    hl7_segment="PID",
                    hl7_field="30",
                    hl7_value=deceased_flag,
                    description="Patient deceased indicator"
                ))
            elif deceased_flag == "N":
                resource["deceasedBoolean"] = False
            else:
                death_dt = parse_hl7_datetime(_field(pid, 29))
                if death_dt:
                    resource["deceasedDateTime"] = death_dt
                    mappings.append(FieldMapping(
                        fhir_field="deceasedDateTime",
                        hl7_segment="PID",
                        hl7_field="29",
                        hl7_value=_field(pid, 29),
                        description="Date/time of death"
                    ))
        except Exception:
            pass

        # Z-segment extensions (Epic/EHR proprietary fields: ZPD, ZEP, etc.)
        z_extensions = map_z_segments_to_extensions(msg)
        if z_extensions:
            resource["extension"] = z_extensions
            mappings.append(FieldMapping(
                fhir_field="extension",
                hl7_segment="Z-segments",
                hl7_field="*",
                hl7_value=f"{len(z_extensions)} field(s) from proprietary Z-segments",
                description="Epic/EHR proprietary Z-segment data mapped to FHIR extensions"
            ))

        return resource, mappings

    # ------------------------------------------------------------------
    def _build_organization(self, msg: ParsedHL7Message, org_id: str) -> Tuple[Dict | None, List[FieldMapping]]:
        facility = msg.sending_facility
        msh = _seg(msg, "MSH")
        org_name = _field(msh, 4, 1)
        if not org_name:
            org_name = facility

        if not org_name:
            return None, []

        mappings = []
        if org_name:
            mappings.append(FieldMapping(
                fhir_field="name",
                hl7_segment="MSH",
                hl7_field="4",
                hl7_value=org_name,
                description="Sending facility/organization name"
            ))

        org: Dict[str, Any] = {"resourceType": "Organization", "id": org_id, "name": org_name}

        # SFT segment — Epic/EHR software info → Organization.extension
        sft = _seg(msg, "SFT")
        if sft is not None:
            sft_vendor  = _field(sft, 1)
            sft_version = _field(sft, 2)
            sft_product = _field(sft, 3)
            if sft_vendor or sft_version:
                org["extension"] = [
                    {"url": "urn:ehr:sft:vendor",  "valueString": sft_vendor},
                    {"url": "urn:ehr:sft:version", "valueString": sft_version},
                    {"url": "urn:ehr:sft:product", "valueString": sft_product},
                ]
                mappings.append(FieldMapping(
                    fhir_field="extension",
                    hl7_segment="SFT",
                    hl7_field="1-3",
                    hl7_value=f"{sft_vendor} {sft_version}".strip(),
                    description="EHR/Epic software vendor and version (SFT segment)"
                ))

        return org, mappings

    # ------------------------------------------------------------------
    def _build_practitioners(self, msg: ParsedHL7Message) -> Tuple[List[Dict], List[List[FieldMapping]]]:
        pv1 = _seg(msg, "PV1")
        practitioners = []
        practitioner_mappings = []
        if pv1 is None:
            return practitioners, practitioner_mappings

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

                mappings = []
                prac: Dict[str, Any] = {
                    "resourceType": "Practitioner",
                    "id": make_id(),
                }
                if npi:
                    prac["identifier"] = [{"system": "http://hl7.org/fhir/sid/us-npi", "value": npi}]
                    mappings.append(FieldMapping(
                        fhir_field="identifier",
                        hl7_segment="PV1",
                        hl7_field=str(field_idx),
                        hl7_value=npi,
                        description=f"{role_display} NPI"
                    ))
                name: Dict[str, Any] = {"use": "official"}
                if family:
                    name["family"] = family
                if given:
                    name["given"] = [given]
                prac["name"] = [name]
                if family or given:
                    mappings.append(FieldMapping(
                        fhir_field="name",
                        hl7_segment="PV1",
                        hl7_field=str(field_idx),
                        hl7_value=raw,
                        description=f"{role_display} name (family^given)"
                    ))
                # Store role for reference building
                prac["_role"] = {"code": role_code, "display": role_display}
                practitioners.append(prac)
                practitioner_mappings.append(mappings)
            except Exception:
                continue

        return practitioners, practitioner_mappings

    # ------------------------------------------------------------------
    def _build_encounter(
        self,
        msg: ParsedHL7Message,
        encounter_id: str,
        patient_id: str,
        org_id: str | None,
        practitioners: List[Dict],
        warnings: list,
    ) -> Tuple[Dict, List[FieldMapping]]:
        pv1 = _seg(msg, "PV1")
        evn = _seg(msg, "EVN")

        status = ADT_EVENT_STATUS.get(msg.message_event, "unknown")
        encounter: Dict[str, Any] = {
            "resourceType": "Encounter",
            "id": encounter_id,
            "status": status,
            "subject": {"reference": f"Patient/{patient_id}"},
        }
        mappings = []

        # Status from message event
        mappings.append(FieldMapping(
            fhir_field="status",
            hl7_segment="MSH",
            hl7_field="9",
            hl7_value=msg.message_event,
            description=f"Encounter status ({status})"
        ))

        # Class (PV1-2)
        if pv1 is not None:
            try:
                patient_class = _field(pv1, 2).upper()
                class_coding = PATIENT_CLASS_MAP.get(
                    patient_class,
                    {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"}
                )
                encounter["class"] = class_coding
                if patient_class:
                    mappings.append(FieldMapping(
                        fhir_field="class",
                        hl7_segment="PV1",
                        hl7_field="2",
                        hl7_value=patient_class,
                        description=f"Patient class ({class_coding.get('display', 'unknown')})"
                    ))
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
                    mappings.append(FieldMapping(
                        fhir_field="identifier",
                        hl7_segment="PV1",
                        hl7_field="19",
                        hl7_value=visit_num,
                        description="Visit number"
                    ))
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
                        mappings.append(FieldMapping(
                            fhir_field="period.start",
                            hl7_segment="PV1",
                            hl7_field="44",
                            hl7_value=admit_raw,
                            description="Admission date/time"
                        ))
                discharge_raw = _field(pv1, 45)
                if discharge_raw:
                    discharge_dt = parse_hl7_datetime(discharge_raw)
                    if discharge_dt:
                        period["end"] = discharge_dt
                        mappings.append(FieldMapping(
                            fhir_field="period.end",
                            hl7_segment="PV1",
                            hl7_field="45",
                            hl7_value=discharge_raw,
                            description="Discharge date/time"
                        ))
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
                        mappings.append(FieldMapping(
                            fhir_field="period.start",
                            hl7_segment="EVN",
                            hl7_field="2",
                            hl7_value=evn2,
                            description="Event date/time (fallback for admission)"
                        ))
            except Exception:
                pass
        if period:
            encounter["period"] = period

        # Service provider (organization)
        if org_id:
            encounter["serviceProvider"] = {"reference": f"Organization/{org_id}"}
            mappings.append(FieldMapping(
                fhir_field="serviceProvider",
                hl7_segment="MSH",
                hl7_field="4",
                hl7_value=msg.sending_facility,
                description="Sending facility/organization"
            ))

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
                    mappings.append(FieldMapping(
                        fhir_field="hospitalization.dischargeDisposition",
                        hl7_segment="PV1",
                        hl7_field="36",
                        hl7_value=dispo,
                        description="Discharge disposition"
                    ))
            except Exception:
                pass

        # Reason for visit / admission diagnosis (DG1 segment)
        dg1 = _seg(msg, "DG1")
        if dg1 is not None:
            try:
                diag_code = str(dg1[3]).strip()
                if diag_code:
                    encounter["reasonCode"] = [extract_coding(diag_code, "http://hl7.org/fhir/sid/icd-10")]
                    mappings.append(FieldMapping(
                        fhir_field="reasonCode",
                        hl7_segment="DG1",
                        hl7_field="3",
                        hl7_value=diag_code,
                        description="Diagnosis code"
                    ))
            except Exception:
                pass

        return encounter, mappings
