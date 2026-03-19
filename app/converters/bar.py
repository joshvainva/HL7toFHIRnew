"""
BAR (Add/Change Billing Account) message converter.
Common Epic message type for financial/billing events.

BAR^P01 — Add patient accounts
BAR^P02 — Purge patient accounts
BAR^P05 — Update account
BAR^P06 — End account
BAR^P10 — Transmit ambulatory payment classification groups

Produces: Patient, Account, Coverage, Organization, Encounter resources.
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


# BAR event → Account status
BAR_EVENT_STATUS = {
    "P01": "active",
    "P02": "inactive",
    "P05": "active",
    "P06": "inactive",
    "P10": "active",
}

GENDER_MAP = {
    "M": "male", "F": "female", "O": "other",
    "U": "unknown", "A": "other", "N": "unknown",
}


def _seg(parsed_msg: ParsedHL7Message, name: str):
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


class BARConverter(BaseConverter):
    """Converts HL7 BAR messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[ResourceMapping]]:
        resources = []
        warnings = []
        field_mappings = []

        patient_id = make_id()
        org_id     = make_id()
        account_id = make_id()

        # Patient
        patient, patient_maps = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)
        if patient_maps:
            field_mappings.append(ResourceMapping(
                resource_type="Patient", resource_id=patient_id, field_mappings=patient_maps
            ))

        # Organization (MSH-4)
        org, org_maps = self._build_organization(parsed_msg, org_id)
        if org:
            resources.append(org)
            if org_maps:
                field_mappings.append(ResourceMapping(
                    resource_type="Organization", resource_id=org_id, field_mappings=org_maps
                ))

        # Account (PV1 visit + BAR event)
        account, account_maps = self._build_account(parsed_msg, account_id, patient_id, org_id if org else None)
        resources.append(account)
        if account_maps:
            field_mappings.append(ResourceMapping(
                resource_type="Account", resource_id=account_id, field_mappings=account_maps
            ))

        # Coverage / Insurance (IN1 segments)
        for in1 in parsed_msg.get_all_segments("IN1"):
            cov_id = make_id()
            coverage, cov_maps = self._build_coverage(in1, cov_id, patient_id)
            if coverage:
                resources.append(coverage)
                if cov_maps:
                    field_mappings.append(ResourceMapping(
                        resource_type="Coverage", resource_id=cov_id, field_mappings=cov_maps
                    ))

        return resources, warnings, field_mappings

    # ------------------------------------------------------------------
    def _build_patient(self, msg: ParsedHL7Message, patient_id: str, warnings: list) -> Tuple[Dict, List[FieldMapping]]:
        pid = _seg(msg, "PID")
        resource: Dict[str, Any] = {"resourceType": "Patient", "id": patient_id}
        mappings: List[FieldMapping] = []

        if pid is None:
            warnings.append("PID segment missing in BAR message.")
            return resource, mappings

        # PID-3 identifiers (repeating — handles Epic EPI, MRN etc.)
        identifiers = []
        for raw in str(pid[3]).split("~"):
            if raw.strip():
                identifiers.append(extract_identifier(raw.strip(), "http://hospital.example.org/mrn"))
                mappings.append(FieldMapping(
                    fhir_field="identifier", hl7_segment="PID", hl7_field="3",
                    hl7_value=raw.strip(), description="Patient identifier"
                ))
        # PID-2 alternate (Epic EPI)
        pid2_raw = safe_str(pid[2]) if len(pid) > 2 else ""
        if pid2_raw:
            identifiers.append(extract_identifier(pid2_raw, "http://hospital.example.org/patid"))
            mappings.append(FieldMapping(
                fhir_field="identifier", hl7_segment="PID", hl7_field="2",
                hl7_value=pid2_raw, description="Alternate patient ID (Epic EPI/Enterprise)"
            ))
        if identifiers:
            resource["identifier"] = identifiers

        # Name (PID-5)
        pid5 = safe_str(pid[5])
        if pid5:
            resource["name"] = [extract_name(pid5)]
            mappings.append(FieldMapping(
                fhir_field="name", hl7_segment="PID", hl7_field="5",
                hl7_value=pid5, description="Patient name"
            ))

        # DOB (PID-7)
        dob = parse_hl7_date(_field(pid, 7))
        if dob:
            resource["birthDate"] = dob
            mappings.append(FieldMapping(
                fhir_field="birthDate", hl7_segment="PID", hl7_field="7",
                hl7_value=_field(pid, 7), description="Date of birth"
            ))

        # Gender (PID-8)
        sex = _field(pid, 8).upper()
        resource["gender"] = GENDER_MAP.get(sex, "unknown")
        if sex:
            mappings.append(FieldMapping(
                fhir_field="gender", hl7_segment="PID", hl7_field="8",
                hl7_value=sex, description="Administrative sex"
            ))

        # Address (PID-11)
        addr_raw = safe_str(pid[11]) if len(pid) > 11 else ""
        if addr_raw:
            addr = extract_address(addr_raw)
            if addr:
                resource["address"] = [addr]
                mappings.append(FieldMapping(
                    fhir_field="address", hl7_segment="PID", hl7_field="11",
                    hl7_value=addr_raw, description="Patient address"
                ))

        # Telecom (PID-13/14)
        try:
            telecoms = extract_telecom(
                pid[13] if len(pid) > 13 else "",
                pid[14] if len(pid) > 14 else ""
            )
            if telecoms:
                resource["telecom"] = telecoms
                mappings.append(FieldMapping(
                    fhir_field="telecom", hl7_segment="PID", hl7_field="13",
                    hl7_value=safe_str(pid[13]) if len(pid) > 13 else "",
                    description="Contact phone/email"
                ))
        except Exception:
            pass

        # Z-segment extensions
        z_ext = map_z_segments_to_extensions(msg)
        if z_ext:
            resource["extension"] = z_ext
            mappings.append(FieldMapping(
                fhir_field="extension", hl7_segment="Z-segments", hl7_field="*",
                hl7_value=f"{len(z_ext)} proprietary field(s)",
                description="Epic/EHR Z-segment data"
            ))

        return resource, mappings

    # ------------------------------------------------------------------
    def _build_organization(self, msg: ParsedHL7Message, org_id: str) -> Tuple[Dict | None, List[FieldMapping]]:
        msh = _seg(msg, "MSH")
        org_name = _field(msh, 4, 1) or msg.sending_facility
        if not org_name:
            return None, []
        org = {"resourceType": "Organization", "id": org_id, "name": org_name}
        mappings = [FieldMapping(
            fhir_field="name", hl7_segment="MSH", hl7_field="4",
            hl7_value=org_name, description="Sending facility"
        )]
        # SFT segment (Epic software info)
        sft = _seg(msg, "SFT")
        if sft is not None:
            vendor = _field(sft, 1)
            version = _field(sft, 2)
            if vendor:
                org["extension"] = [
                    {"url": "urn:ehr:sft:vendor",  "valueString": vendor},
                    {"url": "urn:ehr:sft:version", "valueString": version},
                ]
                mappings.append(FieldMapping(
                    fhir_field="extension", hl7_segment="SFT", hl7_field="1-2",
                    hl7_value=f"{vendor} {version}".strip(),
                    description="EHR software vendor/version"
                ))
        return org, mappings

    # ------------------------------------------------------------------
    def _build_account(
        self, msg: ParsedHL7Message, account_id: str, patient_id: str, org_id: str | None
    ) -> Tuple[Dict, List[FieldMapping]]:
        pv1 = _seg(msg, "PV1")
        event = msg.message_event
        status = BAR_EVENT_STATUS.get(event, "active")

        account: Dict[str, Any] = {
            "resourceType": "Account",
            "id": account_id,
            "status": status,
            "subject": [{"reference": f"Patient/{patient_id}"}],
        }
        mappings: List[FieldMapping] = []

        mappings.append(FieldMapping(
            fhir_field="status", hl7_segment="MSH", hl7_field="9",
            hl7_value=event, description=f"Account status from BAR event ({event})"
        ))

        # Account number (PV1-19 visit number)
        if pv1 is not None:
            visit_num = _field(pv1, 19)
            if visit_num:
                account["identifier"] = [{"system": "http://hospital.example.org/account", "value": visit_num}]
                mappings.append(FieldMapping(
                    fhir_field="identifier", hl7_segment="PV1", hl7_field="19",
                    hl7_value=visit_num, description="Visit/account number"
                ))

            # Admission date → servicePeriod.start
            admit_raw = _field(pv1, 44)
            discharge_raw = _field(pv1, 45)
            period = {}
            if admit_raw:
                dt = parse_hl7_datetime(admit_raw)
                if dt:
                    period["start"] = dt
                    mappings.append(FieldMapping(
                        fhir_field="servicePeriod.start", hl7_segment="PV1", hl7_field="44",
                        hl7_value=admit_raw, description="Service period start (admission)"
                    ))
            if discharge_raw:
                dt = parse_hl7_datetime(discharge_raw)
                if dt:
                    period["end"] = dt
                    mappings.append(FieldMapping(
                        fhir_field="servicePeriod.end", hl7_segment="PV1", hl7_field="45",
                        hl7_value=discharge_raw, description="Service period end (discharge)"
                    ))
            if period:
                account["servicePeriod"] = period

        # Guarantor (GT1 segment)
        gt1 = _seg(msg, "GT1")
        if gt1 is not None:
            gt_name = _field(gt1, 3)
            if gt_name:
                account["guarantor"] = [{"party": {"display": gt_name}}]
                mappings.append(FieldMapping(
                    fhir_field="guarantor", hl7_segment="GT1", hl7_field="3",
                    hl7_value=gt_name, description="Guarantor name"
                ))

        if org_id:
            account["owner"] = {"reference": f"Organization/{org_id}"}

        return account, mappings

    # ------------------------------------------------------------------
    def _build_coverage(self, in1: Any, cov_id: str, patient_id: str) -> Tuple[Dict | None, List[FieldMapping]]:
        mappings: List[FieldMapping] = []

        plan_id   = _field(in1, 2)
        plan_name = _field(in1, 4)
        group_num = _field(in1, 8)
        member_id = _field(in1, 49) if len(in1) > 49 else ""

        if not plan_id and not plan_name:
            return None, []

        coverage: Dict[str, Any] = {
            "resourceType": "Coverage",
            "id": cov_id,
            "status": "active",
            "beneficiary": {"reference": f"Patient/{patient_id}"},
        }

        if plan_id:
            coverage["identifier"] = [{"system": "http://hospital.example.org/plan", "value": plan_id}]
            mappings.append(FieldMapping(
                fhir_field="identifier", hl7_segment="IN1", hl7_field="2",
                hl7_value=plan_id, description="Insurance plan ID"
            ))

        if plan_name:
            coverage["payor"] = [{"display": plan_name}]
            mappings.append(FieldMapping(
                fhir_field="payor", hl7_segment="IN1", hl7_field="4",
                hl7_value=plan_name, description="Insurance company name"
            ))

        if group_num:
            coverage["class"] = [{"type": {"coding": [{"code": "group"}]}, "value": group_num, "name": "Group"}]
            mappings.append(FieldMapping(
                fhir_field="class", hl7_segment="IN1", hl7_field="8",
                hl7_value=group_num, description="Insurance group number"
            ))

        if member_id:
            if "identifier" not in coverage:
                coverage["identifier"] = []
            coverage["identifier"].append({"system": "http://hospital.example.org/member", "value": member_id})
            mappings.append(FieldMapping(
                fhir_field="identifier", hl7_segment="IN1", hl7_field="49",
                hl7_value=member_id, description="Insurance member ID"
            ))

        return coverage, mappings
