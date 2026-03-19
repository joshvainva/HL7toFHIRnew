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

DFT_EVENT_STATUS = {
    "P03": "active",
    "P04": "cancelled",
    "P05": "active",
    "P06": "active",
    "P07": "active",
    "P08": "active",
    "P09": "active",
    "P10": "active",
    "P11": "active",
    "P12": "active",
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


class DFTConverter(BaseConverter):
    """Converts HL7 DFT messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[ResourceMapping]]:
        resources = []
        warnings = []
        field_mappings = []

        patient_id = make_id()
        claim_id = make_id()
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

        # Build Claim
        claim, practitioners, claim_mappings, prac_mappings_list = self._build_claim(
            parsed_msg, claim_id, patient_id, org_id if org else None, warnings
        )
        resources.extend(practitioners)
        resources.append(claim)
        for i, prac in enumerate(practitioners):
            if i < len(prac_mappings_list) and prac_mappings_list[i]:
                field_mappings.append(ResourceMapping(
                    resource_type="Practitioner",
                    resource_id=prac["id"],
                    field_mappings=prac_mappings_list[i]
                ))
        if claim_mappings:
            field_mappings.append(ResourceMapping(
                resource_type="Claim",
                resource_id=claim_id,
                field_mappings=claim_mappings
            ))

        return resources, warnings, field_mappings

    # ------------------------------------------------------------------
    def _build_patient(self, msg: ParsedHL7Message, patient_id: str, warnings: list) -> Tuple[Dict, List[FieldMapping]]:
        pid = _seg(msg, "PID")
        resource: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": patient_id,
        }
        mappings = []

        if pid is None:
            warnings.append("PID segment missing — Patient resource will be incomplete.")
            return resource, mappings

        # Identifier (PID-3)
        identifiers = []
        for pid3 in str(pid[3]).split("~"):
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

        # Telecom (PID-13, PID-14)
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
        org_name = _field(msh, 4, 1)
        if not org_name:
            org_name = msg.sending_facility
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
    def _build_claim(
        self,
        msg: ParsedHL7Message,
        claim_id: str,
        patient_id: str,
        org_id: str | None,
        warnings: list,
    ) -> Tuple[Dict, List[Dict], List[FieldMapping], List[List[FieldMapping]]]:
        ft1 = _seg(msg, "FT1")
        pv1 = _seg(msg, "PV1")
        mappings: List[FieldMapping] = []
        practitioners = []
        prac_mappings_list = []

        status = DFT_EVENT_STATUS.get(msg.message_event, "active")
        mappings.append(FieldMapping(
            fhir_field="status",
            hl7_segment="MSH",
            hl7_field="9",
            hl7_value=msg.message_event,
            description=f"Claim status from event ({status})"
        ))

        claim: Dict[str, Any] = {
            "resourceType": "Claim",
            "id": claim_id,
            "status": status,
            "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type", "code": "institutional"}]},
            "use": "claim",
            "patient": {"reference": f"Patient/{patient_id}"},
            "priority": {"coding": [{"code": "normal"}]},
            "item": [],
        }

        if org_id:
            claim["insurer"] = {"reference": f"Organization/{org_id}"}

        if ft1 is None:
            warnings.append("DFT message missing FT1 segment — Claim will be incomplete.")
            return claim, practitioners, mappings, prac_mappings_list

        # Transaction date (FT1-4)
        tx_date_raw = _field(ft1, 4)
        if tx_date_raw:
            dt = parse_hl7_datetime(tx_date_raw)
            if dt:
                claim["created"] = dt
                mappings.append(FieldMapping(
                    fhir_field="created",
                    hl7_segment="FT1",
                    hl7_field="4",
                    hl7_value=tx_date_raw,
                    description="Transaction date/time"
                ))

        # Transaction type (FT1-6)
        tx_type = _field(ft1, 6)
        if tx_type:
            claim["subType"] = {"coding": [extract_coding(tx_type, "http://terminology.hl7.org/CodeSystem/ex-claimsubtype")]}
            mappings.append(FieldMapping(
                fhir_field="subType",
                hl7_segment="FT1",
                hl7_field="6",
                hl7_value=tx_type,
                description="Transaction type"
            ))

        # Transaction amount (FT1-7) and units (FT1-8)
        tx_amount = _field(ft1, 7)
        tx_units = _field(ft1, 8) or "USD"
        if tx_amount:
            try:
                procedure_code = _field(ft1, 25)
                item: Dict[str, Any] = {
                    "sequence": 1,
                    "net": {"value": float(tx_amount), "currency": tx_units},
                }
                if procedure_code:
                    item["productOrService"] = {"coding": [extract_coding(procedure_code, "http://www.ama-assn.org/go/cpt")]}
                    mappings.append(FieldMapping(
                        fhir_field="item.productOrService",
                        hl7_segment="FT1",
                        hl7_field="25",
                        hl7_value=procedure_code,
                        description="Procedure code"
                    ))
                claim["item"].append(item)
                mappings.append(FieldMapping(
                    fhir_field="item.net",
                    hl7_segment="FT1",
                    hl7_field="7",
                    hl7_value=tx_amount,
                    description="Transaction amount"
                ))
            except Exception:
                pass

        # Diagnosis (FT1-19 / DG1)
        dg1 = _seg(msg, "DG1")
        if dg1 is not None:
            diag_code = _field(dg1, 3)
            if diag_code:
                claim["diagnosis"] = [{
                    "sequence": 1,
                    "diagnosisCodeableConcept": extract_coding(diag_code, "http://hl7.org/fhir/sid/icd-10")
                }]
                mappings.append(FieldMapping(
                    fhir_field="diagnosis.diagnosisCodeableConcept",
                    hl7_segment="DG1",
                    hl7_field="3",
                    hl7_value=diag_code,
                    description="Diagnosis code"
                ))

        # Provider practitioner from PV1-7 (attending)
        if pv1 is not None:
            raw = str(pv1[7]).strip() if len(pv1) > 7 else ""
            if raw:
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
                        hl7_segment="PV1",
                        hl7_field="7",
                        hl7_value=npi,
                        description="Attending physician NPI"
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
                        hl7_segment="PV1",
                        hl7_field="7",
                        hl7_value=raw,
                        description="Attending physician name"
                    ))
                practitioners.append(prac)
                prac_mappings_list.append(prac_maps)
                claim["provider"] = {"reference": f"Practitioner/{prac_id}"}
                mappings.append(FieldMapping(
                    fhir_field="provider",
                    hl7_segment="PV1",
                    hl7_field="7",
                    hl7_value=raw,
                    description="Attending physician (claim provider)"
                ))

        return claim, practitioners, mappings, prac_mappings_list

    def _map_gender(self, gender_field: Any) -> str:
        gender = safe_str(gender_field).upper()
        return GENDER_MAP.get(gender, "unknown")
