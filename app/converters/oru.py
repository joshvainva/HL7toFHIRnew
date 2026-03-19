"""
ORU (Observation Result Unsolicited) message converter.

Produces: Patient, Encounter, Organization, Practitioner, Coverage, AllergyIntolerance,
Condition, Procedure, Immunization, DiagnosticReport, Observation resources.
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


# Maps HL7 result status to FHIR observation status
OBX_STATUS_MAP = {
    "F": "final",
    "P": "preliminary",
    "C": "corrected",
    "X": "cancelled",
    "I": "registered",
    "R": "registered",
    "S": "registered",
    "U": "unknown",
    "W": "entered-in-error",
    "A": "amended",
    "D": "entered-in-error",
    "N": "registered",
}

# Maps HL7 observation value type to FHIR quantity/type hints
OBX_VALUE_TYPES = {
    "NM": "numeric",
    "ST": "string",
    "TX": "text",
    "CE": "coded",
    "CWE": "coded",
    "DT": "date",
    "TM": "time",
    "TS": "datetime",
    "SN": "structured_numeric",
    "CX": "identifier",
    "XON": "organization_name",
    "RP": "attachment",
    "ED": "attachment",
}


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


class ORUConverter(BaseConverter):
    """Converts HL7 ORU^R01 messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[ResourceMapping]]:
        resources = []
        warnings = []
        field_mappings = []

        # Generate IDs
        patient_id = make_id()
        encounter_id = make_id()
        org_id = make_id()

        # Build Patient and related resources
        patient, patient_mappings = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)
        field_mappings.append(ResourceMapping(
            resource_type="Patient",
            resource_id=patient_id,
            field_mappings=patient_mappings
        ))

        # Build Organization
        org, org_mappings = self._build_organization(parsed_msg, org_id)
        if org:
            resources.append(org)
            field_mappings.append(ResourceMapping(
                resource_type="Organization",
                resource_id=org_id,
                field_mappings=org_mappings
            ))

        # Build Encounter
        encounter, encounter_mappings = self._build_encounter(parsed_msg, encounter_id, patient_id, org_id, warnings)
        if encounter:
            resources.append(encounter)
            field_mappings.append(ResourceMapping(
                resource_type="Encounter",
                resource_id=encounter_id,
                field_mappings=encounter_mappings
            ))

        # Build Practitioners
        practitioners, practitioner_mappings = self._build_practitioners(parsed_msg)
        resources.extend(practitioners)
        for i, prac_mapping in enumerate(practitioner_mappings):
            if prac_mapping and i < len(practitioners):
                field_mappings.append(ResourceMapping(
                    resource_type="Practitioner",
                    resource_id=practitioners[i]["id"],
                    field_mappings=prac_mapping
                ))

        # Build Coverage (Insurance)
        coverages, coverage_mappings = self._build_coverages(parsed_msg, patient_id)
        resources.extend(coverages)
        for i, cov_mapping in enumerate(coverage_mappings):
            if cov_mapping and i < len(coverages):
                field_mappings.append(ResourceMapping(
                    resource_type="Coverage",
                    resource_id=coverages[i]["id"],
                    field_mappings=cov_mapping
                ))

        # Build AllergyIntolerances
        allergies, allergy_mappings = self._build_allergies(parsed_msg, patient_id)
        resources.extend(allergies)
        for i, allergy_mapping in enumerate(allergy_mappings):
            if allergy_mapping and i < len(allergies):
                field_mappings.append(ResourceMapping(
                    resource_type="AllergyIntolerance",
                    resource_id=allergies[i]["id"],
                    field_mappings=allergy_mapping
                ))

        # Build Conditions
        conditions, condition_mappings = self._build_conditions(parsed_msg, patient_id, encounter_id)
        resources.extend(conditions)
        for i, cond_mapping in enumerate(condition_mappings):
            if cond_mapping and i < len(conditions):
                field_mappings.append(ResourceMapping(
                    resource_type="Condition",
                    resource_id=conditions[i]["id"],
                    field_mappings=cond_mapping
                ))

        # Build Procedures
        procedures, procedure_mappings = self._build_procedures(parsed_msg, patient_id, encounter_id)
        resources.extend(procedures)
        for i, proc_mapping in enumerate(procedure_mappings):
            if proc_mapping and i < len(procedures):
                field_mappings.append(ResourceMapping(
                    resource_type="Procedure",
                    resource_id=procedures[i]["id"],
                    field_mappings=proc_mapping
                ))

        # Build Immunizations
        immunizations, immunization_mappings = self._build_immunizations(parsed_msg, patient_id)
        resources.extend(immunizations)
        for i, imm_mapping in enumerate(immunization_mappings):
            if imm_mapping and i < len(immunizations):
                field_mappings.append(ResourceMapping(
                    resource_type="Immunization",
                    resource_id=immunizations[i]["id"],
                    field_mappings=imm_mapping
                ))

        # Build DiagnosticReports and Observations
        diagnostic_reports, observations, dr_mappings, obs_mappings = self._build_diagnostic_reports_and_observations(
            parsed_msg, patient_id, encounter_id, warnings
        )
        resources.extend(diagnostic_reports)
        resources.extend(observations)

        for dr_mapping in dr_mappings:
            field_mappings.append(dr_mapping)
        for obs_mapping in obs_mappings:
            field_mappings.append(obs_mapping)

        return resources, warnings, field_mappings

    # ------------------------------------------------------------------
    def _build_patient(self, msg: ParsedHL7Message, patient_id: str, warnings: list) -> Tuple[Dict, List[FieldMapping]]:
        pid = msg.get_segment("PID")
        pd1 = msg.get_segment("PD1")
        nk1_segments = msg.get_all_segments("NK1")

        resource: Dict[str, Any] = {"resourceType": "Patient", "id": patient_id}
        mappings = []

        if pid is None:
            warnings.append("PID segment missing — Patient resource will be minimal.")
            return resource, mappings

        # Identifiers (PID-3, PID-2, PID-19)
        identifiers = []
        pid3 = safe_str(pid[3])
        if pid3:
            identifiers.append(extract_identifier(pid3, "http://hospital.example.org/mrn"))
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="PID",
                hl7_field="3",
                hl7_value=pid3,
                description="Patient identifiers (MRN)"
            ))

        pid2 = safe_str(pid[2])
        if pid2:
            identifiers.append(extract_identifier(pid2, "http://hospital.example.org/patient-id"))
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="PID",
                hl7_field="2",
                hl7_value=pid2,
                description="Patient ID"
            ))

        pid19 = safe_str(pid[19]) if len(pid) > 19 else ""
        if pid19:
            identifiers.append({"system": "http://hl7.org/fhir/sid/us-ssn", "value": pid19})
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="PID",
                hl7_field="19",
                hl7_value=pid19,
                description="SSN"
            ))

        if identifiers:
            resource["identifier"] = identifiers

        # Name (PID-5)
        pid5 = safe_str(pid[5])
        if pid5:
            resource["name"] = [extract_name(pid5)]
            mappings.append(FieldMapping(
                fhir_field="name",
                hl7_segment="PID",
                hl7_field="5",
                hl7_value=pid5,
                description="Patient name"
            ))

        # DOB (PID-7)
        dob = parse_hl7_date(_field(pid, 7))
        if dob:
            resource["birthDate"] = dob
            mappings.append(FieldMapping(
                fhir_field="birthDate",
                hl7_segment="PID",
                hl7_field="7",
                hl7_value=_field(pid, 7),
                description="Date of birth"
            ))

        # Gender (PID-8)
        gender_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}
        gender = safe_str(pid[8]).upper()
        if gender in gender_map:
            resource["gender"] = gender_map[gender]
            mappings.append(FieldMapping(
                fhir_field="gender",
                hl7_segment="PID",
                hl7_field="8",
                hl7_value=gender,
                description="Administrative sex"
            ))

        # Address (PID-11)
        pid11 = safe_str(pid[11]) if len(pid) > 11 else ""
        if pid11:
            resource["address"] = [extract_address(pid11)]
            mappings.append(FieldMapping(
                fhir_field="address",
                hl7_segment="PID",
                hl7_field="11",
                hl7_value=pid11,
                description="Patient address"
            ))

        # Telecom (PID-13, PID-14)
        telecoms = []
        pid13 = safe_str(pid[13]) if len(pid) > 13 else ""
        if pid13:
            telecoms.extend(extract_telecom(pid13, "home"))
            mappings.append(FieldMapping(
                fhir_field="telecom",
                hl7_segment="PID",
                hl7_field="13",
                hl7_value=pid13,
                description="Home phone"
            ))

        pid14 = safe_str(pid[14]) if len(pid) > 14 else ""
        if pid14:
            telecoms.extend(extract_telecom(pid14, "work"))
            mappings.append(FieldMapping(
                fhir_field="telecom",
                hl7_segment="PID",
                hl7_field="14",
                hl7_value=pid14,
                description="Work phone"
            ))

        if telecoms:
            resource["telecom"] = telecoms

        # Marital Status (PID-16)
        marital_status = safe_str(pid[16]) if len(pid) > 16 else ""
        if marital_status:
            resource["maritalStatus"] = extract_coding(marital_status, "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus")
            mappings.append(FieldMapping(
                fhir_field="maritalStatus",
                hl7_segment="PID",
                hl7_field="16",
                hl7_value=marital_status,
                description="Marital status"
            ))

        # Communication/Language (PID-15)
        language = safe_str(pid[15]) if len(pid) > 15 else ""
        if language:
            resource["communication"] = [{"language": {"text": language}, "preferred": True}]
            mappings.append(FieldMapping(
                fhir_field="communication",
                hl7_segment="PID",
                hl7_field="15",
                hl7_value=language,
                description="Primary language"
            ))

        # Multiple Birth (PID-24)
        multiple_birth = safe_str(pid[24]) if len(pid) > 24 else ""
        if multiple_birth:
            if multiple_birth.isdigit():
                resource["multipleBirthInteger"] = int(multiple_birth)
            else:
                resource["multipleBirthBoolean"] = multiple_birth.upper() == "Y"
            mappings.append(FieldMapping(
                fhir_field="multipleBirthInteger",
                hl7_segment="PID",
                hl7_field="24",
                hl7_value=multiple_birth,
                description="Multiple birth indicator"
            ))

        # Deceased (PID-29, PID-30)
        deceased_date = parse_hl7_datetime(_field(pid, 29)) if len(pid) > 29 else None
        deceased_flag = safe_str(pid[30]) if len(pid) > 30 else ""

        if deceased_date:
            resource["deceasedDateTime"] = deceased_date
            mappings.append(FieldMapping(
                fhir_field="deceasedDateTime",
                hl7_segment="PID",
                hl7_field="29",
                hl7_value=_field(pid, 29),
                description="Date/time of death"
            ))
        elif deceased_flag == "Y":
            resource["deceasedBoolean"] = True
            mappings.append(FieldMapping(
                fhir_field="deceasedBoolean",
                hl7_segment="PID",
                hl7_field="30",
                hl7_value=deceased_flag,
                description="Patient deceased"
            ))

        # Contact (NK1 segments)
        if nk1_segments:
            contacts = []
            for nk1 in nk1_segments:
                contact = self._build_patient_contact(nk1)
                if contact:
                    contacts.append(contact)
            if contacts:
                resource["contact"] = contacts

        # General Practitioner (PD1-4, or PD1-3 if PD1-4 is empty)
        if pd1 is not None:
            gp_ref = ""
            if len(pd1) > 4:
                gp_ref = safe_str(pd1[4])
            if not gp_ref and len(pd1) > 3:
                gp_ref = safe_str(pd1[3])

            if gp_ref:
                # Extract provider ID from complex field
                provider_id = gp_ref.split('^')[0] if '^' in gp_ref else gp_ref
                if provider_id:
                    resource["generalPractitioner"] = [{"reference": f"Practitioner/{provider_id}"}]
                    mappings.append(FieldMapping(
                        fhir_field="generalPractitioner",
                        hl7_segment="PD1",
                        hl7_field="4",
                        hl7_value=gp_ref,
                        description="Primary care provider"
                    ))

        return resource, mappings

    # ------------------------------------------------------------------
    def _build_patient_contact(self, nk1) -> Dict | None:
        """Build patient contact from NK1 segment."""
        if not nk1:
            return None

        contact = {}

        # Name (NK1-2)
        name_raw = safe_str(nk1[2])
        if name_raw:
            contact["name"] = extract_name(name_raw)

        # Relationship (NK1-3)
        relationship = safe_str(nk1[3])
        if relationship:
            contact["relationship"] = [extract_coding(relationship, "http://terminology.hl7.org/CodeSystem/v3-RoleCode")]

        # Telecom (NK1-5)
        telecom_raw = safe_str(nk1[5]) if len(nk1) > 5 else ""
        if telecom_raw:
            contact["telecom"] = extract_telecom(telecom_raw, "home")

        # Address (NK1-4)
        address_raw = safe_str(nk1[4])
        if address_raw:
            contact["address"] = extract_address(address_raw)

        return contact if contact else None

    # ------------------------------------------------------------------
    def _build_organization(self, msg: ParsedHL7Message, org_id: str) -> Tuple[Dict | None, List[FieldMapping]]:
        facility = msg.sending_facility
        msh = msg.get_segment("MSH")

        mappings = []
        if not facility and msh:
            facility = _field(msh, 4, 1)

        if not facility:
            return None, mappings

        mappings.append(FieldMapping(
            fhir_field="name",
            hl7_segment="MSH",
            hl7_field="4",
            hl7_value=facility,
            description="Sending facility/organization name"
        ))

        return {
            "resourceType": "Organization",
            "id": org_id,
            "name": facility,
        }, mappings

    # ------------------------------------------------------------------
    def _build_encounter(self, msg: ParsedHL7Message, encounter_id: str, patient_id: str, org_id: str | None, warnings: list) -> Tuple[Dict | None, List[FieldMapping]]:
        pv1 = msg.get_segment("PV1")
        pv2 = msg.get_segment("PV2")

        if not pv1:
            return None, []

        mappings = []
        encounter: Dict[str, Any] = {
            "resourceType": "Encounter",
            "id": encounter_id,
            "subject": {"reference": f"Patient/{patient_id}"},
        }

        # Status: PV1-40 if available, else default to "in-progress" for ORU
        encounter_status = "in-progress"
        if len(pv1) > 40:
            raw_status = safe_str(pv1[40]).upper()
            if raw_status:
                status_map = {
                    "ACTIVE": "in-progress",
                    "IN PROGRESS": "in-progress",
                    "COMPLETED": "finished",
                    "CANCELLED": "cancelled"
                }
                encounter_status = status_map.get(raw_status, "in-progress")
                mappings.append(FieldMapping(
                    fhir_field="status",
                    hl7_segment="PV1",
                    hl7_field="40",
                    hl7_value=raw_status,
                    description="Encounter status"
                ))
        encounter["status"] = encounter_status

        # Class (PV1-2)
        patient_class = safe_str(_field(pv1, 2)).upper()
        if patient_class:
            class_map = {
                "I": {"code": "IMP", "display": "inpatient encounter"},
                "O": {"code": "AMB", "display": "ambulatory"},
                "E": {"code": "EMER", "display": "emergency"},
                "P": {"code": "PRENC", "display": "pre-admission"}
            }
            encounter["class"] = class_map.get(patient_class, {"code": "AMB", "display": "ambulatory"})
            mappings.append(FieldMapping(
                fhir_field="class",
                hl7_segment="PV1",
                hl7_field="2",
                hl7_value=patient_class,
                description="Patient class"
            ))

        # Period (PV1-44, PV1-45)
        period = {}
        admit_date = parse_hl7_datetime(_field(pv1, 44))
        if admit_date:
            period["start"] = admit_date
            mappings.append(FieldMapping(
                fhir_field="period.start",
                hl7_segment="PV1",
                hl7_field="44",
                hl7_value=_field(pv1, 44),
                description="Admission date/time"
            ))

        discharge_date = parse_hl7_datetime(_field(pv1, 45))
        if discharge_date:
            period["end"] = discharge_date
            mappings.append(FieldMapping(
                fhir_field="period.end",
                hl7_segment="PV1",
                hl7_field="45",
                hl7_value=_field(pv1, 45),
                description="Discharge date/time"
            ))

        if period:
            encounter["period"] = period

        # Service Provider
        if org_id:
            encounter["serviceProvider"] = {"reference": f"Organization/{org_id}"}

        # Location (PV1-3)
        location = safe_str(_field(pv1, 3))
        if location:
            # Parse location components
            parts = location.split("^")
            if len(parts) >= 4:
                encounter["location"] = [{
                    "location": {
                        "identifier": {"value": parts[0]},
                        "display": f"{parts[1]} {parts[2]} {parts[3]}"
                    }
                }]
                mappings.append(FieldMapping(
                    fhir_field="location",
                    hl7_segment="PV1",
                    hl7_field="3",
                    hl7_value=location,
                    description="Assigned patient location"
                ))

        # Type (PV2-1)
        if pv2:
            visit_type = safe_str(_field(pv2, 1))
            if visit_type:
                encounter["type"] = [extract_coding(visit_type, "http://terminology.hl7.org/CodeSystem/v2-0004")]
                mappings.append(FieldMapping(
                    fhir_field="type",
                    hl7_segment="PV2",
                    hl7_field="1",
                    hl7_value=visit_type,
                    description="Visit type"
                ))

        return encounter, mappings

    # ------------------------------------------------------------------
    def _build_practitioners(self, msg: ParsedHL7Message) -> Tuple[List[Dict], List[List[FieldMapping]]]:
        practitioners = []
        practitioner_mappings = []

        # From PV1 segments
        pv1 = msg.get_segment("PV1")
        if pv1:
            # Attending (PV1-7), Referring (PV1-8), Consulting (PV1-9), Admitting (PV1-17)
            roles = [
                (7, "attending", "Attending Physician"),
                (8, "referring", "Referring Physician"),
                (9, "consultant", "Consulting Physician"),
                (17, "admitting", "Admitting Physician"),
            ]

            for field_idx, role_code, role_display in roles:
                prac_raw = safe_str(_field(pv1, field_idx))
                if prac_raw:
                    prac, mappings = self._build_practitioner_from_field(prac_raw, role_display)
                    if prac:
                        practitioners.append(prac)
                        practitioner_mappings.append(mappings)

        # From ORC segments
        orc_segments = msg.get_all_segments("ORC")
        for orc in orc_segments:
            # Ordering Provider (ORC-12); also try ORC-11 if ORC-12 absent
            provider_raw = safe_str(orc[12]) if len(orc) > 12 else ""
            if not provider_raw:
                # Fallback: ORC-11 (Verified By / Ordering Provider in shorter segments)
                candidate = safe_str(orc[11]) if len(orc) > 11 else ""
                first_cmp = candidate.split("^")[0].strip()
                if candidate and not (first_cmp.isdigit() and 8 <= len(first_cmp) <= 14):
                    provider_raw = candidate
            if provider_raw:
                prac, mappings = self._build_practitioner_from_field(provider_raw, "Ordering Provider")
                if prac:
                    practitioners.append(prac)
                    practitioner_mappings.append(mappings)

        return practitioners, practitioner_mappings

    # ------------------------------------------------------------------
    def _build_practitioner_from_field(self, prac_raw: str, role: str) -> Tuple[Dict | None, List[FieldMapping]]:
        mappings = []
        if not prac_raw:
            return None, mappings

        parts = prac_raw.split("^")
        prac: Dict[str, Any] = {
            "resourceType": "Practitioner",
            "id": make_id(),
        }

        # ID (NPI)
        npi = parts[0].strip()
        if npi:
            prac["identifier"] = [{"system": "http://hl7.org/fhir/sid/us-npi", "value": npi}]
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="PV1",  # This will be overridden by caller
                hl7_field="7",     # This will be overridden by caller
                hl7_value=npi,
                description=f"{role} NPI"
            ))

        # Name
        family = parts[1].strip() if len(parts) > 1 else ""
        given = parts[2].strip() if len(parts) > 2 else ""
        middle = parts[3].strip() if len(parts) > 3 else ""
        suffix = parts[4].strip() if len(parts) > 4 else ""
        prefix = parts[5].strip() if len(parts) > 5 else ""

        name = {}
        if family:
            name["family"] = family
        if given or middle:
            name["given"] = [g for g in [given, middle] if g]
        if suffix:
            name["suffix"] = [suffix]
        if prefix:
            name["prefix"] = [prefix]

        if name:
            prac["name"] = [name]

        return prac if prac.get("identifier") or prac.get("name") else None, mappings

    # ------------------------------------------------------------------
    def _build_coverages(self, msg: ParsedHL7Message, patient_id: str) -> Tuple[List[Dict], List[List[FieldMapping]]]:
        coverages = []
        coverage_mappings = []

        in1_segments = msg.get_all_segments("IN1")
        for in1 in in1_segments:
            coverage, mappings = self._build_coverage_from_in1(in1, patient_id)
            if coverage:
                coverages.append(coverage)
                coverage_mappings.append(mappings)

        return coverages, coverage_mappings

    # ------------------------------------------------------------------
    def _build_coverage_from_in1(self, in1, patient_id: str) -> Tuple[Dict | None, List[FieldMapping]]:
        mappings = []
        if not in1:
            return None, mappings

        coverage: Dict[str, Any] = {
            "resourceType": "Coverage",
            "id": make_id(),
            "status": "active",
            "beneficiary": {"reference": f"Patient/{patient_id}"},
        }

        # Insurance Plan ID (IN1-2)
        plan_id = safe_str(in1[2])
        if plan_id:
            coverage["identifier"] = [{"value": plan_id}]
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="IN1",
                hl7_field="2",
                hl7_value=plan_id,
                description="Insurance plan ID"
            ))

        # Insurance Company Name (IN1-4)
        company_name = safe_str(in1[4])
        if company_name:
            coverage["payor"] = [{"display": company_name}]
            mappings.append(FieldMapping(
                fhir_field="payor",
                hl7_segment="IN1",
                hl7_field="4",
                hl7_value=company_name,
                description="Insurance company name"
            ))

        # Group Number (IN1-8)
        group_num = safe_str(in1[8])
        if group_num:
            coverage["class"] = [{"type": {"text": "group"}, "value": group_num}]
            mappings.append(FieldMapping(
                fhir_field="class",
                hl7_segment="IN1",
                hl7_field="8",
                hl7_value=group_num,
                description="Group number"
            ))

        # Policy Number (IN1-36)
        policy_num = safe_str(in1[36]) if len(in1) > 36 else ""
        if policy_num:
            if not coverage.get("identifier"):
                coverage["identifier"] = []
            coverage["identifier"].append({"value": policy_num})
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="IN1",
                hl7_field="36",
                hl7_value=policy_num,
                description="Policy number"
            ))

        return coverage, mappings

    # ------------------------------------------------------------------
    def _build_allergies(self, msg: ParsedHL7Message, patient_id: str) -> Tuple[List[Dict], List[List[FieldMapping]]]:
        allergies = []
        allergy_mappings = []

        al1_segments = msg.get_all_segments("AL1")
        for al1 in al1_segments:
            allergy, mappings = self._build_allergy_from_al1(al1, patient_id)
            if allergy:
                allergies.append(allergy)
                allergy_mappings.append(mappings)

        return allergies, allergy_mappings

    # ------------------------------------------------------------------
    def _build_allergy_from_al1(self, al1, patient_id: str) -> Tuple[Dict | None, List[FieldMapping]]:
        mappings = []
        if not al1:
            return None, mappings

        allergy: Dict[str, Any] = {
            "resourceType": "AllergyIntolerance",
            "id": make_id(),
            "patient": {"reference": f"Patient/{patient_id}"},
        }

        # Substance (AL1-3)
        substance = safe_str(al1[3])
        if substance:
            allergy["code"] = extract_coding(substance, "http://www.nlm.nih.gov/research/umls/rxnorm")
            mappings.append(FieldMapping(
                fhir_field="code",
                hl7_segment="AL1",
                hl7_field="3",
                hl7_value=substance,
                description="Allergen substance"
            ))

        # Severity (AL1-4)
        severity = safe_str(al1[4])
        if severity:
            severity_map = {
                "SV": "severe",
                "MO": "moderate",
                "MI": "mild"
            }
            severity_code = severity.split("^")[0].strip().upper()
            allergy["criticality"] = severity_map.get(severity_code, "unable-to-assess")
            mappings.append(FieldMapping(
                fhir_field="criticality",
                hl7_segment="AL1",
                hl7_field="4",
                hl7_value=severity,
                description="Allergy severity"
            ))

        # Reaction (AL1-5)
        reaction = safe_str(al1[5])
        if reaction:
            allergy["reaction"] = [{"manifestation": [extract_coding(reaction, "http://snomed.info/sct")]}]
            mappings.append(FieldMapping(
                fhir_field="reaction",
                hl7_segment="AL1",
                hl7_field="5",
                hl7_value=reaction,
                description="Allergy reaction"
            ))

        # Onset Date (AL1-6)
        onset_date = parse_hl7_date(_field(al1, 6))
        if onset_date:
            allergy["onsetDateTime"] = onset_date
            mappings.append(FieldMapping(
                fhir_field="onsetDateTime",
                hl7_segment="AL1",
                hl7_field="6",
                hl7_value=_field(al1, 6),
                description="Allergy onset date"
            ))

        return allergy, mappings

    # ------------------------------------------------------------------
    def _build_conditions(self, msg: ParsedHL7Message, patient_id: str, encounter_id: str | None) -> Tuple[List[Dict], List[List[FieldMapping]]]:
        conditions = []
        condition_mappings = []

        dg1_segments = msg.get_all_segments("DG1")
        for dg1 in dg1_segments:
            condition, mappings = self._build_condition_from_dg1(dg1, patient_id, encounter_id)
            if condition:
                conditions.append(condition)
                condition_mappings.append(mappings)

        return conditions, condition_mappings

    # ------------------------------------------------------------------
    def _build_condition_from_dg1(self, dg1, patient_id: str, encounter_id: str | None) -> Tuple[Dict | None, List[FieldMapping]]:
        mappings = []
        if not dg1:
            return None, mappings

        condition: Dict[str, Any] = {
            "resourceType": "Condition",
            "id": make_id(),
            "subject": {"reference": f"Patient/{patient_id}"},
        }

        if encounter_id:
            condition["encounter"] = {"reference": f"Encounter/{encounter_id}"}

        # Diagnosis Code (DG1-3)
        diagnosis_code = safe_str(dg1[3])
        if diagnosis_code:
            condition["code"] = extract_coding(diagnosis_code, "http://hl7.org/fhir/sid/icd-10")
            mappings.append(FieldMapping(
                fhir_field="code",
                hl7_segment="DG1",
                hl7_field="3",
                hl7_value=diagnosis_code,
                description="Diagnosis code"
            ))

        # Diagnosis Description (DG1-4)
        description = safe_str(dg1[4])
        if description:
            if not condition.get("code"):
                condition["code"] = {"text": description}
            mappings.append(FieldMapping(
                fhir_field="code",
                hl7_segment="DG1",
                hl7_field="4",
                hl7_value=description,
                description="Diagnosis description"
            ))

        # Onset Date (DG1-5)
        onset_date = parse_hl7_date(_field(dg1, 5))
        if onset_date:
            condition["onsetDateTime"] = onset_date
            mappings.append(FieldMapping(
                fhir_field="onsetDateTime",
                hl7_segment="DG1",
                hl7_field="5",
                hl7_value=_field(dg1, 5),
                description="Diagnosis onset date"
            ))

        return condition, mappings

    # ------------------------------------------------------------------
    def _build_procedures(self, msg: ParsedHL7Message, patient_id: str, encounter_id: str | None) -> Tuple[List[Dict], List[List[FieldMapping]]]:
        procedures = []
        procedure_mappings = []

        pr1_segments = msg.get_all_segments("PR1")
        for pr1 in pr1_segments:
            procedure, mappings = self._build_procedure_from_pr1(pr1, patient_id, encounter_id)
            if procedure:
                procedures.append(procedure)
                procedure_mappings.append(mappings)

        return procedures, procedure_mappings

    # ------------------------------------------------------------------
    def _build_procedure_from_pr1(self, pr1, patient_id: str, encounter_id: str | None) -> Tuple[Dict | None, List[FieldMapping]]:
        mappings = []
        if not pr1:
            return None, mappings

        procedure: Dict[str, Any] = {
            "resourceType": "Procedure",
            "id": make_id(),
            "subject": {"reference": f"Patient/{patient_id}"},
        }

        if encounter_id:
            procedure["encounter"] = {"reference": f"Encounter/{encounter_id}"}

        # Procedure Code (PR1-3)
        proc_code = safe_str(pr1[3])
        if proc_code:
            procedure["code"] = extract_coding(proc_code, "http://www.ama-assn.org/go/cpt")
            mappings.append(FieldMapping(
                fhir_field="code",
                hl7_segment="PR1",
                hl7_field="3",
                hl7_value=proc_code,
                description="Procedure code"
            ))

        # Procedure Date/Time (PR1-5)
        proc_date = parse_hl7_datetime(_field(pr1, 5))
        if proc_date:
            procedure["performedDateTime"] = proc_date
            mappings.append(FieldMapping(
                fhir_field="performedDateTime",
                hl7_segment="PR1",
                hl7_field="5",
                hl7_value=_field(pr1, 5),
                description="Procedure date/time"
            ))

        # Status (PR1-6)
        status = safe_str(pr1[6])
        if status:
            status_map = {
                "COMPLETED": "completed",
                "IN PROGRESS": "in-progress",
                "CANCELLED": "stopped"
            }
            procedure["status"] = status_map.get(status.upper(), "unknown")
            mappings.append(FieldMapping(
                fhir_field="status",
                hl7_segment="PR1",
                hl7_field="6",
                hl7_value=status,
                description="Procedure status"
            ))

        return procedure, mappings

    # ------------------------------------------------------------------
    def _build_immunizations(self, msg: ParsedHL7Message, patient_id: str) -> Tuple[List[Dict], List[List[FieldMapping]]]:
        immunizations = []
        immunization_mappings = []

        rxa_segments = msg.get_all_segments("RXA")
        for rxa in rxa_segments:
            immunization, mappings = self._build_immunization_from_rxa(rxa, patient_id, msg)
            if immunization:
                immunizations.append(immunization)
                immunization_mappings.append(mappings)

        return immunizations, immunization_mappings

    # ------------------------------------------------------------------
    def _build_immunization_from_rxa(self, rxa, patient_id: str, msg: ParsedHL7Message = None) -> Tuple[Dict | None, List[FieldMapping]]:
        mappings = []
        if not rxa:
            return None, mappings

        immunization: Dict[str, Any] = {
            "resourceType": "Immunization",
            "id": make_id(),
            "patient": {"reference": f"Patient/{patient_id}"},
        }

        # Vaccine Code (RXA-5)
        vaccine_code = safe_str(rxa[5])
        if vaccine_code:
            immunization["vaccineCode"] = extract_coding(vaccine_code, "http://hl7.org/fhir/sid/cvx")
            mappings.append(FieldMapping(
                fhir_field="vaccineCode",
                hl7_segment="RXA",
                hl7_field="5",
                hl7_value=vaccine_code,
                description="Vaccine administered"
            ))

        # Date/Time Administered (RXA-3)
        admin_date = parse_hl7_datetime(_field(rxa, 3))
        if admin_date:
            immunization["occurrenceDateTime"] = admin_date
            mappings.append(FieldMapping(
                fhir_field="occurrenceDateTime",
                hl7_segment="RXA",
                hl7_field="3",
                hl7_value=_field(rxa, 3),
                description="Administration date/time"
            ))

        # Dose Quantity (RXA-6)
        dose_qty = safe_str(rxa[6])
        if dose_qty:
            parts = dose_qty.split("^")
            if len(parts) >= 2:
                immunization["doseQuantity"] = {
                    "value": float(parts[0]) if parts[0].replace('.', '').isdigit() else None,
                    "unit": parts[1],
                    "system": "http://unitsofmeasure.org",
                    "code": parts[1]
                }
                mappings.append(FieldMapping(
                    fhir_field="doseQuantity",
                    hl7_segment="RXA",
                    hl7_field="6",
                    hl7_value=dose_qty,
                    description="Dose quantity"
                ))

        # Route (RXR-1)
        # Find corresponding RXR segment
        rxr_segments = msg.get_all_segments("RXR") if msg else []
        if rxr_segments:
            route = safe_str(rxr_segments[0][1])
            if route:
                immunization["route"] = extract_coding(route, "http://terminology.hl7.org/CodeSystem/v2-0162")
                mappings.append(FieldMapping(
                    fhir_field="route",
                    hl7_segment="RXR",
                    hl7_field="1",
                    hl7_value=route,
                    description="Administration route"
                ))

        # Status (RXA-20)
        status = safe_str(rxa[20]) if len(rxa) > 20 else ""
        if status:
            status_map = {
                "00": "completed",
                "01": "not-done"
            }
            immunization["status"] = status_map.get(status, "completed")
            mappings.append(FieldMapping(
                fhir_field="status",
                hl7_segment="RXA",
                hl7_field="20",
                hl7_value=status,
                description="Immunization status"
            ))

        return immunization, mappings

    # ------------------------------------------------------------------
    def _build_diagnostic_reports_and_observations(
        self, msg: ParsedHL7Message, patient_id: str, encounter_id: str | None, warnings: list
    ) -> Tuple[List[Dict], List[Dict], List[ResourceMapping], List[ResourceMapping]]:
        diagnostic_reports = []
        observations = []
        dr_mappings = []
        obs_mappings = []

        # Group OBX segments by OBR
        obr_segments = msg.get_all_segments("OBR")
        obx_segments = msg.get_all_segments("OBX")

        if not obr_segments:
            # Create single diagnostic report for all observations
            dr_id = make_id()
            dr, dr_mapping = self._build_diagnostic_report(None, dr_id, patient_id, encounter_id, [])
            diagnostic_reports.append(dr)
            dr_mappings.append(dr_mapping)

            for obx in obx_segments:
                obs, obs_mapping = self._build_observation(obx, patient_id, dr_id, warnings)
                if obs:
                    observations.append(obs)
                    obs_mappings.append(obs_mapping)
        else:
            # Associate OBX with OBR by order
            all_segs = msg.parsed
            current_obr = None
            current_obx_list = []
            obr_batches = []

            for seg in all_segs:
                seg_name = str(seg[0]).strip()
                if seg_name == "OBR":
                    if current_obr is not None:
                        obr_batches.append((current_obr, current_obx_list))
                    current_obr = seg
                    current_obx_list = []
                elif seg_name == "OBX" and current_obr is not None:
                    current_obx_list.append(seg)

            # Last batch
            if current_obr is not None:
                obr_batches.append((current_obr, current_obx_list))

            for obr, obx_list in obr_batches:
                dr_id = make_id()
                obs_ids = []

                # Create observations
                for obx in obx_list:
                    obs, obs_mapping = self._build_observation(obx, patient_id, dr_id, warnings)
                    if obs:
                        observations.append(obs)
                        obs_mappings.append(obs_mapping)
                        obs_ids.append(obs["id"])

                # Create diagnostic report
                dr, dr_mapping = self._build_diagnostic_report(obr, dr_id, patient_id, encounter_id, obs_ids)
                diagnostic_reports.append(dr)
                dr_mappings.append(dr_mapping)

        return diagnostic_reports, observations, dr_mappings, obs_mappings

    # ------------------------------------------------------------------
    def _build_diagnostic_report(
        self, obr, dr_id: str, patient_id: str, encounter_id: str | None, observation_ids: List[str]
    ) -> Tuple[Dict, ResourceMapping]:
        mappings = []
        resource: Dict[str, Any] = {
            "resourceType": "DiagnosticReport",
            "id": dr_id,
            "subject": {"reference": f"Patient/{patient_id}"},
            "result": [{"reference": f"Observation/{oid}"} for oid in observation_ids],
        }

        if encounter_id:
            resource["encounter"] = {"reference": f"Encounter/{encounter_id}"}

        if obr is None:
            resource["status"] = "unknown"
            resource["code"] = {"text": "Unknown order"}
            return resource, ResourceMapping(
                resource_type="DiagnosticReport",
                resource_id=dr_id,
                field_mappings=mappings
            )

        # Status from OBR-25
        status_raw = _field(obr, 25).upper()
        resource["status"] = OBX_STATUS_MAP.get(status_raw, "unknown")
        if status_raw:
            mappings.append(FieldMapping(
                fhir_field="status",
                hl7_segment="OBR",
                hl7_field="25",
                hl7_value=status_raw,
                description="Diagnostic report status"
            ))

        # Order/test code (OBR-4)
        code_raw = _field(obr, 4)
        if code_raw:
            resource["code"] = extract_coding(code_raw, "http://loinc.org")
            mappings.append(FieldMapping(
                fhir_field="code",
                hl7_segment="OBR",
                hl7_field="4",
                hl7_value=code_raw,
                description="Test ordered"
            ))
        else:
            resource["code"] = {"text": "Laboratory Result"}

        # Order number / identifiers (OBR-3, OBR-2)
        filler_order = _field(obr, 3)
        placer_order = _field(obr, 2)
        idents = []
        if filler_order:
            idents.append({"type": {"text": "FILL"}, "value": filler_order})
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="OBR",
                hl7_field="3",
                hl7_value=filler_order,
                description="Filler order number"
            ))
        if placer_order:
            idents.append({"type": {"text": "PLAC"}, "value": placer_order})
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="OBR",
                hl7_field="2",
                hl7_value=placer_order,
                description="Placer order number"
            ))
        if idents:
            resource["identifier"] = idents

        # Effective time (OBR-7 observation date)
        obs_dt = parse_hl7_datetime(_field(obr, 7))
        if obs_dt:
            resource["effectiveDateTime"] = obs_dt
            mappings.append(FieldMapping(
                fhir_field="effectiveDateTime",
                hl7_segment="OBR",
                hl7_field="7",
                hl7_value=_field(obr, 7),
                description="Observation date/time"
            ))

        # Issued time (OBR-22 status change time)
        issued_dt = parse_hl7_datetime(_field(obr, 22))
        if issued_dt:
            resource["issued"] = issued_dt if "T" in issued_dt else issued_dt + "T00:00:00Z"
            mappings.append(FieldMapping(
                fhir_field="issued",
                hl7_segment="OBR",
                hl7_field="22",
                hl7_value=_field(obr, 22),
                description="Report issued date/time"
            ))

        # Category
        resource["category"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                "code": "LAB",
                "display": "Laboratory",
            }]
        }]

        return resource, ResourceMapping(
            resource_type="DiagnosticReport",
            resource_id=dr_id,
            field_mappings=mappings
        )

    # ------------------------------------------------------------------
    def _build_observation(self, obx, patient_id: str, dr_id: str, warnings: list) -> Tuple[Dict | None, ResourceMapping]:
        mappings = []
        if not obx:
            return None, ResourceMapping(resource_type="Observation", resource_id="", field_mappings=mappings)

        obs_id = make_id()
        resource: Dict[str, Any] = {
            "resourceType": "Observation",
            "id": obs_id,
            "subject": {"reference": f"Patient/{patient_id}"},
            "derivedFrom": [{"reference": f"DiagnosticReport/{dr_id}"}],
        }

        # Status (OBX-11)
        status_raw = _field(obx, 11).upper()
        resource["status"] = OBX_STATUS_MAP.get(status_raw, "unknown")
        if status_raw:
            mappings.append(FieldMapping(
                fhir_field="status",
                hl7_segment="OBX",
                hl7_field="11",
                hl7_value=status_raw,
                description="Observation status"
            ))

        # Observation code (OBX-3)
        obs_code = _field(obx, 3)
        if obs_code:
            resource["code"] = extract_coding(obs_code, "http://loinc.org")
            mappings.append(FieldMapping(
                fhir_field="code",
                hl7_segment="OBX",
                hl7_field="3",
                hl7_value=obs_code,
                description="Observation code"
            ))

        # Value and data type (OBX-2, OBX-5)
        value_type = _field(obx, 2)
        value_raw = _field(obx, 5)

        if value_raw:
            mappings.append(FieldMapping(
                fhir_field="value[x]",
                hl7_segment="OBX",
                hl7_field="5",
                hl7_value=value_raw,
                description="Observation value"
            ))

            if value_type == "NM":  # Numeric
                try:
                    num_val = float(value_raw)
                    units = _field(obx, 6)
                    resource["valueQuantity"] = {
                        "value": num_val,
                        "unit": units or "unit",
                        "system": "http://unitsofmeasure.org",
                        "code": units or "unit"
                    }
                    if units:
                        mappings.append(FieldMapping(
                            fhir_field="valueQuantity.unit",
                            hl7_segment="OBX",
                            hl7_field="6",
                            hl7_value=units,
                            description="Units"
                        ))
                except ValueError:
                    resource["valueString"] = value_raw

            elif value_type in ["ST", "TX"]:  # String/Text
                resource["valueString"] = value_raw

            elif value_type == "CE" or value_type == "CWE":  # Coded
                resource["valueCodeableConcept"] = extract_coding(value_raw, "http://snomed.info/sct")

            elif value_type == "DT":  # Date
                dt = parse_hl7_date(value_raw)
                if dt:
                    resource["valueDateTime"] = dt

            elif value_type == "TM":  # Time
                resource["valueTime"] = value_raw

            elif value_type == "TS":  # DateTime
                dt = parse_hl7_datetime(value_raw)
                if dt:
                    resource["valueDateTime"] = dt

            elif value_type == "SN":  # Structured Numeric
                # Handle structured numeric (e.g., "1.2:3.4")
                resource["valueString"] = value_raw

            elif value_type == "CX":  # Identifier
                resource["valueString"] = value_raw

            elif value_type == "RP":  # Reference Pointer (attachment)
                resource["valueAttachment"] = {
                    "contentType": "application/octet-stream",
                    "title": value_raw.split("^")[0] if "^" in value_raw else value_raw
                }

            elif value_type == "ED":  # Encapsulated Data
                resource["valueAttachment"] = {
                    "contentType": "text/plain",
                    "data": value_raw  # In real implementation, this would be base64 decoded
                }

            else:
                # Default to string
                resource["valueString"] = value_raw

        # Reference range (OBX-7)
        ref_range = _field(obx, 7)
        if ref_range:
            resource["referenceRange"] = [{"text": ref_range}]
            mappings.append(FieldMapping(
                fhir_field="referenceRange",
                hl7_segment="OBX",
                hl7_field="7",
                hl7_value=ref_range,
                description="Reference range"
            ))

        # Interpretation (OBX-8)
        interpretation = _field(obx, 8)
        if interpretation:
            interp_map = {
                "N": "normal",
                "H": "high",
                "L": "low",
                "A": "abnormal",
                "AA": "critically-abnormal"
            }
            resource["interpretation"] = [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                    "code": interp_map.get(interpretation.upper(), interpretation.lower()),
                    "display": interpretation
                }]
            }]
            mappings.append(FieldMapping(
                fhir_field="interpretation",
                hl7_segment="OBX",
                hl7_field="8",
                hl7_value=interpretation,
                description="Result interpretation"
            ))

        # Observation date/time (OBX-14)
        obs_dt = parse_hl7_datetime(_field(obx, 14))
        if obs_dt:
            resource["effectiveDateTime"] = obs_dt
            mappings.append(FieldMapping(
                fhir_field="effectiveDateTime",
                hl7_segment="OBX",
                hl7_field="14",
                hl7_value=_field(obx, 14),
                description="Observation date/time"
            ))

        # Method (OBX-17)
        method = _field(obx, 17)
        if method:
            resource["method"] = extract_coding(method, "http://snomed.info/sct")
            mappings.append(FieldMapping(
                fhir_field="method",
                hl7_segment="OBX",
                hl7_field="17",
                hl7_value=method,
                description="Observation method"
            ))

        return resource, ResourceMapping(
            resource_type="Observation",
            resource_id=obs_id,
            field_mappings=mappings
        )
