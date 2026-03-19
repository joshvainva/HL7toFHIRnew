"""
FHIR Bundle → HL7 ADT converter.

Reads: Patient, Encounter, Practitioner, Organization resources.
Produces: MSH, EVN, PID, PV1 segments.
"""
from typing import Any, Dict, List, Optional

from app.converters.fhir_to_hl7.base import (
    BaseFHIRtoHL7Converter,
    encode_name,
    encode_address,
    fmt_datetime,
    fmt_date,
    make_msh,
    GENDER_TO_HL7,
)


# Map FHIR Encounter.class code → HL7 PV1-2 patient class
ENCOUNTER_CLASS_MAP = {
    "IMP": "I", "inpatient": "I",
    "AMB": "O", "ambulatory": "O", "outpatient": "O",
    "EMER": "E", "emergency": "E",
    "PRENC": "P", "pre-admission": "P",
    "VR": "R",
}


def _derive_event(status: str, class_code: str) -> str:
    """
    Derive HL7 ADT event code from FHIR Encounter status + class.

    in-progress + inpatient → A01 (Admit)
    in-progress + outpatient/ambulatory → A04 (Register)
    finished    → A03 (Discharge)
    cancelled   → A11 (Cancel Admit)
    onleave     → A21 (Patient Goes on Leave)
    arrived     → A04
    """
    cls = class_code.upper()
    if status == "finished":
        return "A03"
    if status == "cancelled":
        return "A11"
    if status == "onleave":
        return "A21"
    if status in ("in-progress", "arrived", "triaged"):
        if cls in ("IMP", "INPATIENT", "I"):
            return "A01"
        return "A04"
    return "A01"


def _encode_xcn(practitioner: Dict[str, Any]) -> str:
    """Build HL7 XCN string: NPI^family^given^middle^suffix^prefix from a Practitioner resource."""
    npi = ""
    ids = practitioner.get("identifier", [])
    if ids:
        npi = ids[0].get("value", "")

    names = practitioner.get("name", [])
    if not names:
        return npi

    n = names[0]
    family = n.get("family", "")
    given_list = n.get("given", [])
    given = given_list[0] if given_list else ""
    middle = given_list[1] if len(given_list) > 1 else ""
    suffix_list = n.get("suffix", [])
    suffix = suffix_list[0] if suffix_list else ""
    prefix_list = n.get("prefix", [])
    prefix = prefix_list[0] if prefix_list else ""

    # XCN: id^family^given^second^suffix^prefix^...
    xcn = f"{npi}^{family}^{given}^{middle}^{suffix}^{prefix}"
    return xcn.rstrip("^")


class ADTtoHL7Converter(BaseFHIRtoHL7Converter):

    def convert(self, bundle: Dict[str, Any]) -> str:
        patient      = self._first(bundle, "Patient")
        encounter    = self._first(bundle, "Encounter")
        practitioners = self._get_resources(bundle, "Practitioner")
        organization = self._first(bundle, "Organization")

        enc_status = encounter.get("status", "in-progress") if encounter else "in-progress"
        enc_class  = encounter.get("class", {}) if encounter else {}
        class_code = enc_class.get("code", "") if isinstance(enc_class, dict) else ""
        event = _derive_event(enc_status, class_code)

        sending_facility = organization.get("name", "UNKNOWN") if organization else "UNKNOWN"

        segments = [make_msh("FHIR_CONVERTER", sending_facility, "ADT", event)]
        segments.append(self._build_evn(event, encounter))
        segments.append(self._build_pid(patient))
        segments.append(self._build_pv1(event, encounter, practitioners))

        return "\r".join(s for s in segments if s)

    # ------------------------------------------------------------------
    def _build_evn(self, event: str, encounter: Optional[Dict]) -> str:
        """EVN|event_code|recorded_datetime"""
        event_time = ""
        if encounter:
            period = encounter.get("period", {})
            event_time = fmt_datetime(period.get("start", ""))
        return f"EVN|{event}|{event_time}"

    # ------------------------------------------------------------------
    def _build_pid(self, patient: Optional[Dict[str, Any]]) -> str:
        if not patient:
            return "PID|1"

        # PID-3: all identifiers joined with ~
        # Each FHIR identifier → value^^^authority^type_hint
        identifiers = patient.get("identifier", [])
        pid3_parts = []
        for i, ident in enumerate(identifiers):
            val = ident.get("value", "")
            if not val:
                continue
            system = ident.get("system", "")
            system_lower = system.lower()
            # Detect identifier type from system URI or value pattern
            # Detect type from explicit type coding first
            type_code = ""
            type_codings = ident.get("type", {}).get("coding", [])
            if type_codings:
                type_code = type_codings[0].get("code", "").upper()

            if type_code in ("EPI",):
                authority, id_type = "EPIC", "EPI"
            elif type_code in ("MR", "MRN"):
                authority, id_type = "HOSP", "MR"
            elif type_code in ("SS", "SSN"):
                authority, id_type = "SSA", "SS"
            elif type_code in ("NPI",):
                authority, id_type = "NPI", "NPI"
            elif type_code in ("AN",):
                authority, id_type = "HOSP", "AN"
            elif type_code in ("VN",):
                authority, id_type = "HOSP", "VN"
            elif "1.2.840.114350" in system_lower:   # Epic OID
                authority, id_type = "EPIC", "EPI"
            elif "npi" in system_lower:
                authority, id_type = "NPI", "NPI"
            elif "ssn" in system_lower or "ss" in system_lower or (val.replace("-", "").isdigit() and len(val.replace("-", "")) == 9):
                authority, id_type = "SSA", "SS"
            elif "mrn" in system_lower or "hospital" in system_lower:
                authority, id_type = "HOSP", "MR"
            else:
                authority, id_type = "", ""
            pid3_parts.append(f"{val}^^^{authority}^{id_type}".rstrip("^"))
        pid3 = "~".join(pid3_parts) if pid3_parts else ""

        # PID-5: name
        names = patient.get("name", [])
        pid5 = encode_name(names[0]) if names else ""

        # PID-7: DOB
        pid7 = fmt_date(patient.get("birthDate", ""))

        # PID-8: gender
        pid8 = GENDER_TO_HL7.get(patient.get("gender", "unknown"), "U")

        # PID-11: address
        addresses = patient.get("address", [])
        pid11 = encode_address(addresses[0]) if addresses else ""

        # PID-13: phone (with type components) and email as repeat
        telecoms = patient.get("telecom", [])
        pid13_parts = []
        for t in telecoms:
            sys = t.get("system", "")
            val = t.get("value", "")
            use = t.get("use", "")
            if not val:
                continue
            if sys == "phone":
                ttype = "PRN" if use == "home" else ("WPN" if use == "work" else "PRN")
                pid13_parts.append(f"{val}^{ttype}^PH")
            elif sys == "email":
                pid13_parts.append(f"{val}^NET^Internet")
        pid13 = "~".join(pid13_parts)

        # PID-15: preferred language (text or code)
        comms = patient.get("communication", [])
        pid15 = ""
        if comms:
            lang = comms[0].get("language", {})
            codings = lang.get("coding", [])
            pid15 = codings[0].get("code", "") if codings else lang.get("text", "")

        # PID-16: marital status — emit only the code, not the full URI
        marital = patient.get("maritalStatus", {})
        pid16 = ""
        if marital:
            codings = marital.get("coding", [])
            if codings:
                pid16 = codings[0].get("code", "")
            if not pid16:
                pid16 = marital.get("text", "")

        fields = ["PID", "1", "", pid3, "", pid5, "", pid7, pid8, "", "", pid11, "", pid13, "", pid15, pid16]
        return "|".join(fields).rstrip("|")

    # ------------------------------------------------------------------
    def _build_pv1(
        self,
        event: str,
        encounter: Optional[Dict[str, Any]],
        practitioners: List[Dict[str, Any]],
    ) -> str:
        if not encounter:
            return "PV1|1|U"

        # PV1-2: patient class
        enc_class  = encounter.get("class", {})
        class_code = enc_class.get("code", "") if isinstance(enc_class, dict) else ""
        pv1_2 = ENCOUNTER_CLASS_MAP.get(class_code.upper(), ENCOUNTER_CLASS_MAP.get(class_code, "U"))

        # PV1-3: assigned location (from location[].location.display)
        locations = encounter.get("location", [])
        pv1_3 = ""
        if locations:
            loc_ref = locations[0].get("location", {})
            pv1_3 = loc_ref.get("display", "")

        # PV1-7/8: attending/referring from participants
        participants = encounter.get("participant", [])
        pv1_7 = ""
        pv1_8 = ""

        def _prac_by_ref(ref_str: str) -> str:
            prac_id = ref_str.replace("Practitioner/", "")
            for p in practitioners:
                if p.get("id") == prac_id:
                    return _encode_xcn(p)
            return ""

        for part in participants:
            types = part.get("type", [])
            type_code = ""
            for t in types:
                codings = t.get("coding", [])
                type_code = codings[0].get("code", "") if codings else ""
                break
            ref = (part.get("individual", {}) or part.get("actor", {})).get("reference", "")
            xcn = _prac_by_ref(ref)
            if not xcn:
                continue
            if type_code.lower() in ("atnd", "attending") and not pv1_7:
                pv1_7 = xcn
            elif type_code.lower() in ("ref", "referring") and not pv1_8:
                pv1_8 = xcn
            elif not pv1_7:
                pv1_7 = xcn

        # PV1-19: visit number
        enc_ids = encounter.get("identifier", [])
        pv1_19 = enc_ids[0].get("value", "") if enc_ids else ""

        # PV1-44/45: admission/discharge datetimes
        period = encounter.get("period", {})
        pv1_44 = fmt_datetime(period.get("start", ""))
        pv1_45 = fmt_datetime(period.get("end", ""))

        # Build to field 45; pad with empty fields in between
        f = ["PV1", "1", pv1_2, pv1_3, "", "", "", pv1_7, pv1_8,
             "", "", "", "", "", "", "", "", "", "", pv1_19]
        while len(f) < 44:
            f.append("")
        f.append(pv1_44)
        if pv1_45:
            f.append(pv1_45)

        return "|".join(f).rstrip("|")
