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

MDM_EVENT_STATUS = {
    "T01": "current",
    "T02": "current",
    "T03": "superseded",
    "T04": "current",
    "T05": "current",
    "T06": "current",
    "T07": "current",
    "T08": "current",
    "T09": "current",
    "T10": "current",
    "T11": "entered-in-error",
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


class MDMConverter(BaseConverter):
    """Converts HL7 MDM messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[ResourceMapping]]:
        resources = []
        warnings = []
        field_mappings = []

        patient_id = make_id()
        document_id = make_id()
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

        # Build DocumentReference + Practitioners
        document, practitioners, doc_mappings, prac_mappings_list = self._build_document_reference(
            parsed_msg, document_id, patient_id, org_id if org else None, warnings
        )
        resources.extend(practitioners)
        resources.append(document)

        for i, prac in enumerate(practitioners):
            if i < len(prac_mappings_list) and prac_mappings_list[i]:
                field_mappings.append(ResourceMapping(
                    resource_type="Practitioner",
                    resource_id=prac["id"],
                    field_mappings=prac_mappings_list[i]
                ))

        if doc_mappings:
            field_mappings.append(ResourceMapping(
                resource_type="DocumentReference",
                resource_id=document_id,
                field_mappings=doc_mappings
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
    def _build_document_reference(
        self,
        msg: ParsedHL7Message,
        document_id: str,
        patient_id: str,
        org_id: str | None,
        warnings: list,
    ) -> Tuple[Dict, List[Dict], List[FieldMapping], List[List[FieldMapping]]]:
        txa = _seg(msg, "TXA")
        mappings: List[FieldMapping] = []
        practitioners: List[Dict] = []
        prac_mappings_list: List[List[FieldMapping]] = []

        status = MDM_EVENT_STATUS.get(msg.message_event, "current")
        mappings.append(FieldMapping(
            fhir_field="status",
            hl7_segment="MSH",
            hl7_field="9",
            hl7_value=msg.message_event,
            description=f"Document status from event ({status})"
        ))

        document: Dict[str, Any] = {
            "resourceType": "DocumentReference",
            "id": document_id,
            "status": status,
            "subject": {"reference": f"Patient/{patient_id}"},
            "content": [{"attachment": {"contentType": "text/plain"}}],
        }

        if txa is None:
            warnings.append("TXA segment missing — DocumentReference will be incomplete.")
            return document, practitioners, mappings, prac_mappings_list

        # Document type (TXA-2)
        doc_type = _field(txa, 2)
        if doc_type:
            document["type"] = {"coding": [extract_coding(doc_type, "http://loinc.org")]}
            mappings.append(FieldMapping(
                fhir_field="type",
                hl7_segment="TXA",
                hl7_field="2",
                hl7_value=doc_type,
                description="Document type code"
            ))

        # Document content type (TXA-3)
        content_type = _field(txa, 3) or "text/plain"
        mappings.append(FieldMapping(
            fhir_field="content.attachment.contentType",
            hl7_segment="TXA",
            hl7_field="3",
            hl7_value=content_type,
            description="Document content type"
        ))

        # Activity date/time (TXA-4)
        activity_dt_raw = _field(txa, 4)
        activity_dt = parse_hl7_datetime(activity_dt_raw) if activity_dt_raw else None
        if activity_dt:
            document["date"] = activity_dt
            document["content"] = [{"attachment": {
                "contentType": content_type,
                "creation": activity_dt,
            }}]
            mappings.append(FieldMapping(
                fhir_field="date",
                hl7_segment="TXA",
                hl7_field="4",
                hl7_value=activity_dt_raw,
                description="Document activity date/time"
            ))
        else:
            document["content"] = [{"attachment": {"contentType": content_type}}]

        # Document unique ID (TXA-12)
        doc_uid = _field(txa, 12)
        if doc_uid:
            document["identifier"] = [{"system": "urn:ietf:rfc:3986", "value": doc_uid}]
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="TXA",
                hl7_field="12",
                hl7_value=doc_uid,
                description="Document unique ID"
            ))

        # Category (TXA-1 — set ID, used as category sequence)
        txa1 = _field(txa, 1)
        if txa1:
            document["category"] = [{"coding": [{"code": txa1, "display": "Document"}]}]
            mappings.append(FieldMapping(
                fhir_field="category",
                hl7_segment="TXA",
                hl7_field="1",
                hl7_value=txa1,
                description="Document set ID / category"
            ))

        # Organization custodian
        if org_id:
            document["custodian"] = {"reference": f"Organization/{org_id}"}
            mappings.append(FieldMapping(
                fhir_field="custodian",
                hl7_segment="MSH",
                hl7_field="4",
                hl7_value=msg.sending_facility,
                description="Document custodian (sending facility)"
            ))

        # Authors from TXA-9 (primary) and TXA-10 (co-author)
        document["author"] = []
        for field_idx, role_desc in [(9, "Primary author"), (10, "Co-author")]:
            try:
                raw = _field(txa, field_idx)
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
                        hl7_segment="TXA",
                        hl7_field=str(field_idx),
                        hl7_value=npi,
                        description=f"{role_desc} NPI"
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
                        hl7_segment="TXA",
                        hl7_field=str(field_idx),
                        hl7_value=raw,
                        description=f"{role_desc} name"
                    ))
                practitioners.append(prac)
                prac_mappings_list.append(prac_maps)
                document["author"].append({"reference": f"Practitioner/{prac_id}"})
                mappings.append(FieldMapping(
                    fhir_field="author",
                    hl7_segment="TXA",
                    hl7_field=str(field_idx),
                    hl7_value=raw,
                    description=f"{role_desc}"
                ))
            except Exception:
                continue

        # Authenticator (TXA-22)
        try:
            auth_raw = _field(txa, 22)
            if auth_raw:
                parts = auth_raw.split("^")
                auth_npi = parts[0].strip()
                auth_family = parts[1].strip() if len(parts) > 1 else ""
                auth_given = parts[2].strip() if len(parts) > 2 else ""
                auth_id = make_id()
                auth_prac: Dict[str, Any] = {"resourceType": "Practitioner", "id": auth_id}
                auth_maps: List[FieldMapping] = []
                if auth_npi:
                    auth_prac["identifier"] = [{"system": "http://hl7.org/fhir/sid/us-npi", "value": auth_npi}]
                    auth_maps.append(FieldMapping(
                        fhir_field="identifier",
                        hl7_segment="TXA",
                        hl7_field="22",
                        hl7_value=auth_npi,
                        description="Authenticator NPI"
                    ))
                a_name: Dict[str, Any] = {"use": "official"}
                if auth_family:
                    a_name["family"] = auth_family
                if auth_given:
                    a_name["given"] = [auth_given]
                auth_prac["name"] = [a_name]
                if auth_family or auth_given:
                    auth_maps.append(FieldMapping(
                        fhir_field="name",
                        hl7_segment="TXA",
                        hl7_field="22",
                        hl7_value=auth_raw,
                        description="Authenticator name"
                    ))
                practitioners.append(auth_prac)
                prac_mappings_list.append(auth_maps)
                document["authenticator"] = {"reference": f"Practitioner/{auth_id}"}
                mappings.append(FieldMapping(
                    fhir_field="authenticator",
                    hl7_segment="TXA",
                    hl7_field="22",
                    hl7_value=auth_raw,
                    description="Document authenticator"
                ))
        except Exception:
            pass

        return document, practitioners, mappings, prac_mappings_list

    def _map_gender(self, gender_field: Any) -> str:
        gender = safe_str(gender_field).upper()
        return GENDER_MAP.get(gender, "unknown")
