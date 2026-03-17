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
    extract_name,
    extract_identifier,
    extract_coding,
)
from app.core.parser import ParsedHL7Message


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

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str]]:
        resources = []
        warnings = []

        patient_id = make_id()
        patient = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)

        # Build practitioners from ORC ordering/entering providers
        practitioners = self._build_practitioners(parsed_msg)
        resources.extend(practitioners)

        # Build one ServiceRequest per ORC/OBR pair
        orc_segments = parsed_msg.get_all_segments("ORC")
        obr_segments = parsed_msg.get_all_segments("OBR")

        # Match ORC and OBR by position
        max_orders = max(len(orc_segments), len(obr_segments), 1)
        for i in range(max_orders):
            orc = orc_segments[i] if i < len(orc_segments) else None
            obr = obr_segments[i] if i < len(obr_segments) else None
            sr = self._build_service_request(
                orc, obr, patient_id, practitioners, warnings
            )
            resources.append(sr)

        return resources, warnings

    # ------------------------------------------------------------------
    def _build_patient(self, msg: ParsedHL7Message, patient_id: str, warnings: list) -> Dict:
        pid = msg.get_segment("PID")
        resource: Dict[str, Any] = {"resourceType": "Patient", "id": patient_id}
        if pid is None:
            warnings.append("PID segment missing — Patient resource will be minimal.")
            return resource

        pid3 = safe_str(pid[3])
        if pid3:
            resource["identifier"] = [extract_identifier(pid3, "http://hospital.example.org/mrn")]
        pid5 = safe_str(pid[5])
        if pid5:
            resource["name"] = [extract_name(pid5)]
        from app.converters.base import parse_hl7_date
        dob = parse_hl7_date(_field(pid, 7))
        if dob:
            resource["birthDate"] = dob
        return resource

    # ------------------------------------------------------------------
    def _build_practitioners(self, msg: ParsedHL7Message) -> List[Dict]:
        practitioners = []
        orc_list = msg.get_all_segments("ORC")
        seen_ids = set()
        for orc in orc_list:
            # ORC-12 Ordering Provider, ORC-10 Entered By
            for field_idx, role in [(12, "orderer"), (10, "enterer")]:
                try:
                    raw = _field(orc, field_idx)
                    if not raw or raw in seen_ids:
                        continue
                    seen_ids.add(raw)
                    parts = raw.split("^")
                    npi = parts[0].strip()
                    family = parts[1].strip() if len(parts) > 1 else ""
                    given = parts[2].strip() if len(parts) > 2 else ""
                    prac: Dict[str, Any] = {"resourceType": "Practitioner", "id": make_id()}
                    if npi:
                        prac["identifier"] = [{"system": "http://hl7.org/fhir/sid/us-npi", "value": npi}]
                    name_d: Dict[str, Any] = {"use": "official"}
                    if family:
                        name_d["family"] = family
                    if given:
                        name_d["given"] = [given]
                    prac["name"] = [name_d]
                    practitioners.append(prac)
                except Exception:
                    continue
        return practitioners

    # ------------------------------------------------------------------
    def _build_service_request(
        self,
        orc,
        obr,
        patient_id: str,
        practitioners: List[Dict],
        warnings: list,
    ) -> Dict:
        resource: Dict[str, Any] = {
            "resourceType": "ServiceRequest",
            "id": make_id(),
            "subject": {"reference": f"Patient/{patient_id}"},
        }

        # Status and intent from ORC-1
        order_control = _field(orc, 1).upper() if orc else "NW"
        status, intent = ORDER_CONTROL_MAP.get(order_control, ("unknown", "order"))
        resource["status"] = status
        resource["intent"] = intent

        # Order number
        identifiers = []
        if orc:
            placer = _field(orc, 2)
            filler = _field(orc, 3)
            if placer:
                identifiers.append({"type": {"coding": [{"code": "PLAC"}]}, "value": placer})
            if filler:
                identifiers.append({"type": {"coding": [{"code": "FILL"}]}, "value": filler})
        if obr:
            obr_placer = _field(obr, 2)
            obr_filler = _field(obr, 3)
            if obr_placer and obr_placer not in [i["value"] for i in identifiers]:
                identifiers.append({"type": {"coding": [{"code": "PLAC"}]}, "value": obr_placer})
            if obr_filler and obr_filler not in [i["value"] for i in identifiers]:
                identifiers.append({"type": {"coding": [{"code": "FILL"}]}, "value": obr_filler})
        if identifiers:
            resource["identifier"] = identifiers

        # Order code (OBR-4)
        if obr:
            code_raw = _field(obr, 4)
            if code_raw:
                resource["code"] = extract_coding(code_raw, "http://loinc.org")
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

        # Requester (first practitioner if any)
        if practitioners:
            resource["requester"] = {"reference": f"Practitioner/{practitioners[0]['id']}"}

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

        # Clinical information / reason (OBR-13)
        if obr:
            reason_raw = _field(obr, 13)
            if reason_raw:
                resource["reasonCode"] = [{"text": reason_raw}]

        # Specimen (SPM segment if present)
        # (simplified — full specimen handling would need its own resource)
        if obr:
            specimen_raw = _field(obr, 15)
            if specimen_raw:
                resource["specimen"] = [{"display": specimen_raw}]

        return resource
