"""
FHIR Bundle → HL7 ORU^R01 converter.

Reads: Patient, DiagnosticReport, Observation, Practitioner resources.
Produces: MSH, PID, OBR, OBX segments.
"""
from typing import Any, Dict, List, Optional

from app.converters.fhir_to_hl7.base import (
    BaseFHIRtoHL7Converter,
    encode_name,
    encode_coding,
    fmt_datetime,
    fmt_date,
    make_msh,
    reverse_system_uri,
    GENDER_TO_HL7,
)


REPORT_STATUS_MAP = {
    "final": "F",
    "preliminary": "P",
    "corrected": "C",
    "cancelled": "X",
    "entered-in-error": "X",
    "partial": "P",
    "registered": "R",
    "unknown": "U",
}

OBX_STATUS_MAP = {
    "final": "F",
    "preliminary": "P",
    "corrected": "C",
    "cancelled": "X",
    "entered-in-error": "X",
    "registered": "R",
    "amended": "A",
}

INTERP_MAP = {
    "H": "H", "HH": "HH", "L": "L", "LL": "LL",
    "N": "N", "A": "A", "AA": "AA",
}


class ORUtoHL7Converter(BaseFHIRtoHL7Converter):

    def convert(self, bundle: Dict[str, Any]) -> str:
        patient = self._first(bundle, "Patient")
        practitioners = self._get_resources(bundle, "Practitioner")
        reports = self._get_resources(bundle, "DiagnosticReport")
        all_observations = self._get_resources(bundle, "Observation")

        org = self._first(bundle, "Organization")
        facility = org.get("name", "FACILITY") if org else "FACILITY"
        segments = [make_msh("FHIR_CONVERTER", facility, "ORU", "R01")]
        segments.append(self._build_pid(patient))

        if not reports:
            # No DiagnosticReport — emit all observations under a single OBR
            segments.append(self._build_obr(None, patient, practitioners, 1))
            for i, obs in enumerate(all_observations, 1):
                segments.append(self._build_obx(obs, i))
        else:
            for obr_idx, report in enumerate(reports, 1):
                segments.append(self._build_obr(report, patient, practitioners, obr_idx))
                # Link observations by reference
                report_id = report.get("id", "")
                obs_refs = {r.get("reference", "").replace("Observation/", "") for r in report.get("result", [])}
                report_obs = [o for o in all_observations if o.get("id", "") in obs_refs] or all_observations
                for obx_idx, obs in enumerate(report_obs, 1):
                    segments.append(self._build_obx(obs, obx_idx))

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

    def _build_obr(
        self,
        report: Optional[Dict[str, Any]],
        patient: Optional[Dict[str, Any]],
        practitioners: List[Dict[str, Any]],
        index: int,
    ) -> str:
        placer = ""
        filler = ""
        code_str = ""
        obs_dt = ""
        status = "F"
        issued = ""
        provider_xcn = ""

        if report:
            ids = report.get("identifier", [])
            for ident in ids:
                itype = ident.get("type", {}).get("coding", [{}])[0].get("code", "")
                val = ident.get("value", "")
                if itype == "PLAC":
                    placer = val
                elif itype == "FILL":
                    filler = val
            code_str = encode_coding(report.get("code", {}))
            obs_dt = fmt_datetime(report.get("effectiveDateTime", ""))
            status = REPORT_STATUS_MAP.get(report.get("status", "final"), "F")
            issued = fmt_datetime(report.get("issued", ""))

            # Performer → OBR-16
            performers = report.get("performer", [])
            if performers and practitioners:
                ref = performers[0].get("reference", "").replace("Practitioner/", "")
                for p in practitioners:
                    if p.get("id") == ref:
                        npi = (p.get("identifier") or [{}])[0].get("value", "")
                        names = p.get("name", [])
                        name_hl7 = encode_name(names[0]) if names else ""
                        provider_xcn = f"{npi}^{name_hl7}".strip("^")
                        break

        fields = [
            "OBR", str(index), placer, filler, code_str,
            "", "", obs_dt,  # 5=priority(empty), 6=requested-dt(empty), 7=obs-dt
            "", "", "", "", "", "", "",  # 8-14
            "", provider_xcn,  # 15-16
            "", "", "", "", "", "",  # 17-22
            "", "", status,  # 23-25
        ]
        return "|".join(fields).rstrip("|")

    def _build_obx(self, obs: Dict[str, Any], index: int) -> str:
        code_str = encode_coding(obs.get("code", {}))
        status = OBX_STATUS_MAP.get(obs.get("status", "final"), "F")

        # Value
        value_type = "ST"
        value_str = ""
        units_str = ""

        if "valueQuantity" in obs:
            vq = obs["valueQuantity"]
            value_type = "NM"
            value_str = str(vq.get("value", ""))
            unit = vq.get("unit", "") or vq.get("code", "")
            system = reverse_system_uri(vq.get("system", ""))
            units_str = f"{unit}^^{system}".strip("^") if system else unit
        elif "valueCodeableConcept" in obs:
            value_type = "CWE"
            value_str = encode_coding(obs["valueCodeableConcept"])
        elif "valueString" in obs:
            value_type = "ST"
            value_str = obs["valueString"]
        elif "valueBoolean" in obs:
            value_type = "ST"
            value_str = "true" if obs["valueBoolean"] else "false"
        elif "valueAttachment" in obs:
            value_type = "ED"
            va = obs["valueAttachment"]
            ct = va.get("contentType", "")
            data = va.get("data", "")
            value_str = f"^BASE64^{ct}^{data}" if data else ""

        # Reference range
        ref_ranges = obs.get("referenceRange", [])
        ref_str = ref_ranges[0].get("text", "") if ref_ranges else ""

        # Interpretation — use code only (HL7 OBX-8 is just a code like N, H, L)
        interp = obs.get("interpretation", [])
        interp_str = ""
        if interp:
            codings = interp[0].get("coding", [])
            raw_code = codings[0].get("code", "") if codings else ""
            # Also try text if no coding
            if not raw_code:
                raw_code = interp[0].get("text", "")
            interp_str = INTERP_MAP.get(raw_code.upper(), raw_code)

        # Effective datetime
        eff_dt = fmt_datetime(obs.get("effectiveDateTime", ""))

        fields = [
            "OBX", str(index), value_type, code_str,
            "", value_str, units_str, ref_str, interp_str,
            "", "", "F", "", "", eff_dt,
        ]
        # Override status at position 11 (0-indexed field 10)
        fields[11] = status
        return "|".join(fields).rstrip("|")
