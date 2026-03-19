"""
ORM (Order Message) converter.

Produces: Patient, ServiceRequest, Practitioner resources.
"""
from typing import Any, Dict, List, Tuple

from app.converters.base import (
    BaseConverter,
    make_id,
    safe_str,
    parse_hl7_datetime,
    parse_hl7_date,
    extract_name,
    extract_identifier,
    extract_coding,
)
from app.core.parser import ParsedHL7Message
from app.models.schemas import FieldMapping, ResourceMapping


# Maps ORC-1 order control code to FHIR ServiceRequest status/intent
ORDER_CONTROL_MAP = {
    "NW": ("active", "order"),
    "CA": ("revoked", "order"),
    "DC": ("revoked", "order"),
    "XO": ("active", "order"),
    "HD": ("on-hold", "order"),
    "RE": ("active", "reflex-order"),
    "RO": ("active", "reflex-order"),
    "RP": ("active", "order"),
    "RU": ("active", "order"),
    "SN": ("draft", "proposal"),
    "UA": ("unknown", "order"),
    "UN": ("unknown", "order"),
    "OC": ("active", "order"),
    "OF": ("active", "order"),
    "OK": ("active", "order"),
    "SC": ("active", "order"),
    "PA": ("active", "order"),
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


class ORMConverter(BaseConverter):
    """Converts HL7 ORM^O01 messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[ResourceMapping]]:
        resources = []
        warnings = []
        field_mappings: List[ResourceMapping] = []

        # Patient
        patient_id = make_id()
        patient, patient_mappings = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)
        if patient_mappings:
            field_mappings.append(ResourceMapping(
                resource_type="Patient",
                resource_id=patient_id,
                field_mappings=patient_mappings,
            ))

        # Practitioners
        practitioners, practitioner_mappings = self._build_practitioners(parsed_msg)
        resources.extend(practitioners)
        for i, prac_mappings in enumerate(practitioner_mappings):
            if prac_mappings and i < len(practitioners):
                field_mappings.append(ResourceMapping(
                    resource_type="Practitioner",
                    resource_id=practitioners[i]["id"],
                    field_mappings=prac_mappings,
                ))

        # ServiceRequest(s)
        orc_segments = parsed_msg.get_all_segments("ORC")
        obr_segments = parsed_msg.get_all_segments("OBR")
        max_orders = max(len(orc_segments), len(obr_segments), 1)
        for i in range(max_orders):
            orc = orc_segments[i] if i < len(orc_segments) else None
            obr = obr_segments[i] if i < len(obr_segments) else None
            sr, sr_mappings = self._build_service_request(
                orc, obr, patient_id, practitioners, warnings
            )
            resources.append(sr)
            if sr_mappings:
                field_mappings.append(ResourceMapping(
                    resource_type="ServiceRequest",
                    resource_id=sr["id"],
                    field_mappings=sr_mappings,
                ))

        return resources, warnings, field_mappings

    # ------------------------------------------------------------------
    def _build_patient(
        self, msg: ParsedHL7Message, patient_id: str, warnings: list
    ) -> Tuple[Dict[str, Any], List[FieldMapping]]:
        pid = msg.get_segment("PID")
        resource: Dict[str, Any] = {"resourceType": "Patient", "id": patient_id}
        mappings: List[FieldMapping] = []

        if pid is None:
            warnings.append("PID segment missing — Patient resource will be minimal.")
            return resource, mappings

        # Identifiers (PID-3, PID-2)
        identifiers = []
        pid3 = safe_str(pid[3])
        if pid3:
            identifiers.append(extract_identifier(pid3, "http://hospital.example.org/mrn"))
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="PID",
                hl7_field="3",
                hl7_value=pid3,
                description="Patient identifier (MRN)",
            ))

        pid2 = safe_str(pid[2])
        if pid2:
            identifiers.append(extract_identifier(pid2, "http://hospital.example.org/patient-id"))
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="PID",
                hl7_field="2",
                hl7_value=pid2,
                description="Alternate patient ID",
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
                description="Patient name (family^given^middle^suffix^prefix)",
            ))

        # Date of birth (PID-7)
        dob = parse_hl7_date(_field(pid, 7))
        if dob:
            resource["birthDate"] = dob
            mappings.append(FieldMapping(
                fhir_field="birthDate",
                hl7_segment="PID",
                hl7_field="7",
                hl7_value=_field(pid, 7),
                description="Date of birth (YYYYMMDD)",
            ))

        # Gender (PID-8)
        sex = _field(pid, 8).upper()
        if sex:
            resource["gender"] = sex.lower() if sex in ["M", "F", "O", "U"] else "unknown"
            mappings.append(FieldMapping(
                fhir_field="gender",
                hl7_segment="PID",
                hl7_field="8",
                hl7_value=sex,
                description="Administrative sex",
            ))

        return resource, mappings

    # ------------------------------------------------------------------
    def _build_practitioners(
        self, msg: ParsedHL7Message
    ) -> Tuple[List[Dict[str, Any]], List[List[FieldMapping]]]:
        practitioners = []
        mappings: List[List[FieldMapping]] = []
        orc_list = msg.get_all_segments("ORC")
        seen_ids = set()

        for orc in orc_list:
            # ORC-12 Ordering Provider, ORC-10 Entered By
            for field_idx, role in [(12, "orderer"), (10, "enterer")]:
                try:
                    raw = _field(orc, field_idx)
                    if not raw or raw in seen_ids:
                        continue
                    # Skip if field looks like a datetime (8, 12, or 14 digit numeric = YYYYMMDD / YYYYMMDDHHMM / YYYYMMDDHHMMSS)
                    # Do NOT skip 10-digit strings — those are valid NPIs
                    first_component = raw.split("^")[0].strip()
                    if first_component.isdigit() and len(first_component) in (8, 12, 14):
                        continue
                    seen_ids.add(raw)

                    parts = raw.split("^")
                    npi = parts[0].strip()
                    family = parts[1].strip() if len(parts) > 1 else ""
                    given = parts[2].strip() if len(parts) > 2 else ""

                    prac: Dict[str, Any] = {"resourceType": "Practitioner", "id": make_id()}
                    prac_mappings: List[FieldMapping] = []

                    if npi:
                        prac["identifier"] = [{"system": "http://hl7.org/fhir/sid/us-npi", "value": npi}]
                        prac_mappings.append(FieldMapping(
                            fhir_field="identifier",
                            hl7_segment="ORC",
                            hl7_field=str(field_idx),
                            hl7_value=npi,
                            description=f"{role.capitalize()} provider NPI",
                        ))

                    name_d: Dict[str, Any] = {"use": "official"}
                    if family:
                        name_d["family"] = family
                    if given:
                        name_d["given"] = [given]
                    if name_d:
                        prac["name"] = [name_d]
                        prac_mappings.append(FieldMapping(
                            fhir_field="name",
                            hl7_segment="ORC",
                            hl7_field=str(field_idx),
                            hl7_value=raw,
                            description=f"{role.capitalize()} provider name",
                        ))

                    practitioners.append(prac)
                    mappings.append(prac_mappings)
                except Exception:
                    continue

        return practitioners, mappings

    # ------------------------------------------------------------------
    def _build_service_request(
        self,
        orc,
        obr,
        patient_id: str,
        practitioners: List[Dict[str, Any]],
        warnings: list,
    ) -> Tuple[Dict[str, Any], List[FieldMapping]]:
        resource: Dict[str, Any] = {
            "resourceType": "ServiceRequest",
            "id": make_id(),
            "subject": {"reference": f"Patient/{patient_id}"},
        }
        mappings: List[FieldMapping] = []

        # Status and intent from ORC-1
        order_control = _field(orc, 1).upper() if orc else "NW"
        status, intent = ORDER_CONTROL_MAP.get(order_control, ("unknown", "order"))
        resource["status"] = status
        resource["intent"] = intent
        if order_control:
            mappings.append(FieldMapping(
                fhir_field="status",
                hl7_segment="ORC",
                hl7_field="1",
                hl7_value=order_control,
                description="Order control code",
            ))
            mappings.append(FieldMapping(
                fhir_field="intent",
                hl7_segment="ORC",
                hl7_field="1",
                hl7_value=order_control,
                description="Order intent derived from control code",
            ))

        # Order number
        identifiers = []
        if orc:
            placer = _field(orc, 2)
            filler = _field(orc, 3)
            if placer:
                identifiers.append({"type": {"coding": [{"code": "PLAC"}]}, "value": placer})
                mappings.append(FieldMapping(
                    fhir_field="identifier",
                    hl7_segment="ORC",
                    hl7_field="2",
                    hl7_value=placer,
                    description="Order placer number",
                ))
            if filler:
                identifiers.append({"type": {"coding": [{"code": "FILL"}]}, "value": filler})
                mappings.append(FieldMapping(
                    fhir_field="identifier",
                    hl7_segment="ORC",
                    hl7_field="3",
                    hl7_value=filler,
                    description="Order filler number",
                ))
        if obr:
            obr_placer = _field(obr, 2)
            obr_filler = _field(obr, 3)
            if obr_placer and obr_placer not in [i["value"] for i in identifiers]:
                identifiers.append({"type": {"coding": [{"code": "PLAC"}]}, "value": obr_placer})
                mappings.append(FieldMapping(
                    fhir_field="identifier",
                    hl7_segment="OBR",
                    hl7_field="2",
                    hl7_value=obr_placer,
                    description="Order placer number (OBR)",
                ))
            if obr_filler and obr_filler not in [i["value"] for i in identifiers]:
                identifiers.append({"type": {"coding": [{"code": "FILL"}]}, "value": obr_filler})
                mappings.append(FieldMapping(
                    fhir_field="identifier",
                    hl7_segment="OBR",
                    hl7_field="3",
                    hl7_value=obr_filler,
                    description="Order filler number (OBR)",
                ))
        if identifiers:
            resource["identifier"] = identifiers

        # Order code (OBR-4)
        if obr:
            code_raw = _field(obr, 4)
            if code_raw:
                resource["code"] = extract_coding(code_raw, "http://loinc.org")
                mappings.append(FieldMapping(
                    fhir_field="code",
                    hl7_segment="OBR",
                    hl7_field="4",
                    hl7_value=code_raw,
                    description="Order code (LOINC)",
                ))
            else:
                resource["code"] = {"text": "Order"}
        else:
            resource["code"] = {"text": "Order"}

        # Authored on (ORC-9)
        if orc:
            authored_raw = _field(orc, 9)
            if authored_raw:
                authored_dt = parse_hl7_datetime(authored_raw)
                if authored_dt:
                    resource["authoredOn"] = authored_dt
                    mappings.append(FieldMapping(
                        fhir_field="authoredOn",
                        hl7_segment="ORC",
                        hl7_field="9",
                        hl7_value=authored_raw,
                        description="Order date/time",
                    ))

        # Requester (first practitioner if any)
        if practitioners:
            resource["requester"] = {"reference": f"Practitioner/{practitioners[0]['id']}"}
            if orc:
                mappings.append(FieldMapping(
                    fhir_field="requester",
                    hl7_segment="ORC",
                    hl7_field="12",
                    hl7_value=_field(orc, 12),
                    description="Ordering provider",
                ))

        # Priority (OBR-5)
        if obr:
            priority_raw = _field(obr, 5).lower()
            priority_map = {
                "s": "stat",
                "stat": "stat",
                "a": "asap",
                "asap": "asap",
                "r": "routine",
                "routine": "routine",
                "p": "urgent",
                "urgent": "urgent",
            }
            if priority_raw in priority_map:
                resource["priority"] = priority_map[priority_raw]
                mappings.append(FieldMapping(
                    fhir_field="priority",
                    hl7_segment="OBR",
                    hl7_field="5",
                    hl7_value=priority_raw,
                    description="Order priority",
                ))

        # Clinical information / reason (OBR-13)
        if obr:
            reason_raw = _field(obr, 13)
            if reason_raw:
                resource["reasonCode"] = [{"text": reason_raw}]
                mappings.append(FieldMapping(
                    fhir_field="reasonCode",
                    hl7_segment="OBR",
                    hl7_field="13",
                    hl7_value=reason_raw,
                    description="Clinical reason for order",
                ))

        # Specimen (SPM segment if present)
        # (simplified — full specimen handling would need its own resource)
        if obr:
            specimen_raw = _field(obr, 15)
            if specimen_raw:
                resource["specimen"] = [{"display": specimen_raw}]
                mappings.append(FieldMapping(
                    fhir_field="specimen",
                    hl7_segment="OBR",
                    hl7_field="15",
                    hl7_value=specimen_raw,
                    description="Specimen description",
                ))

        return resource, mappings
