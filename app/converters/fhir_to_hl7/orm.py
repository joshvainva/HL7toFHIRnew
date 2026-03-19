"""
FHIR Bundle → HL7 ORM^O01 converter.

Reads: Patient, ServiceRequest, Practitioner resources.
Produces: MSH, PID, ORC, OBR segments.
"""
from typing import Any, Dict, List, Optional

from app.converters.fhir_to_hl7.base import (
    BaseFHIRtoHL7Converter,
    encode_name,
    encode_coding,
    fmt_datetime,
    fmt_date,
    make_msh,
    GENDER_TO_HL7,
)


# FHIR ServiceRequest.status → ORC-1 order control
STATUS_CONTROL_MAP = {
    ("active", "order"): "NW",
    ("revoked", "order"): "CA",
    ("on-hold", "order"): "HD",
    ("active", "reflex-order"): "RE",
    ("draft", "proposal"): "SN",
    ("unknown", "order"): "UA",
    ("completed", "order"): "OC",
}

PRIORITY_MAP = {
    "stat": "S",
    "asap": "A",
    "routine": "R",
    "urgent": "P",
}


class ORMtoHL7Converter(BaseFHIRtoHL7Converter):

    def convert(self, bundle: Dict[str, Any]) -> str:
        patient = self._first(bundle, "Patient")
        service_requests = self._get_resources(bundle, "ServiceRequest")
        practitioners = self._get_resources(bundle, "Practitioner")

        org = self._first(bundle, "Organization")
        facility = org.get("name", "FACILITY") if org else "FACILITY"
        segments = [make_msh("FHIR_CONVERTER", facility, "ORM", "O01")]
        segments.append(self._build_pid(patient))

        if not service_requests:
            segments.append("ORC|NW")
            segments.append("OBR|1")
        else:
            for i, sr in enumerate(service_requests, 1):
                segments.extend(self._build_order(sr, patient, practitioners, i))

        return "\r".join(s for s in segments if s)

    def _build_pid(self, patient: Optional[Dict[str, Any]]) -> str:
        if not patient:
            return "PID|1"
        identifiers = patient.get("identifier", [])
        mrn = identifiers[0].get("value", "") if identifiers else ""
        pid3 = f"{mrn}^^^HOSP^MR" if mrn else ""
        names = patient.get("name", [])
        pid5 = encode_name(names[0]) if names else ""
        pid7 = fmt_date(patient.get("birthDate", ""))
        pid8 = GENDER_TO_HL7.get(patient.get("gender", "unknown"), "U")
        return f"PID|1||{pid3}||{pid5}||{pid7}|{pid8}"

    def _build_order(
        self,
        sr: Dict[str, Any],
        patient: Optional[Dict[str, Any]],
        practitioners: List[Dict[str, Any]],
        index: int,
    ) -> List[str]:
        status = sr.get("status", "active")
        intent = sr.get("intent", "order")
        orc1 = STATUS_CONTROL_MAP.get((status, intent), "NW")

        # Identifiers
        placer = ""
        filler = ""
        for ident in sr.get("identifier", []):
            itype = ident.get("type", {}).get("coding", [{}])[0].get("code", "")
            val = ident.get("value", "")
            if itype == "PLAC":
                placer = val
            elif itype == "FILL":
                filler = val

        # ORC-9: authored on
        authored = fmt_datetime(sr.get("authoredOn", ""))

        # ORC-12: requester
        requester_xcn = ""
        req_ref = sr.get("requester", {}).get("reference", "").replace("Practitioner/", "")
        if req_ref:
            for p in practitioners:
                if p.get("id") == req_ref:
                    npi = (p.get("identifier") or [{}])[0].get("value", "")
                    names = p.get("name", [])
                    name_hl7 = encode_name(names[0]) if names else ""
                    requester_xcn = f"{npi}^{name_hl7}".strip("^")
                    break

        # ORC segment
        orc_fields = ["ORC", orc1, placer, filler, "", "", "", "", "", authored, "", "", requester_xcn]
        orc_seg = "|".join(orc_fields).rstrip("|")

        # OBR segment
        code_str = encode_coding(sr.get("code", {}))
        priority = PRIORITY_MAP.get(sr.get("priority", "routine"), "R")
        obr_fields = [
            "OBR", str(index), placer, filler, code_str,
            priority,  # OBR-5
        ]
        obr_seg = "|".join(obr_fields).rstrip("|")

        return [orc_seg, obr_seg]
