"""
FHIR Bundle → HL7 ORU^R01 converter.

Reads: Patient, Encounter, Practitioner, Organization, RelatedPerson,
       AllergyIntolerance, Condition, Coverage, Immunization,
       DiagnosticReport, Observation resources.
Produces: MSH, PID, PV1, NK1, AL1, DG1, OBR, OBX, IN1, RXA, RXR segments.
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

ENCOUNTER_CLASS_MAP = {
    "IMP": "I", "inpatient": "I",
    "AMB": "O", "ambulatory": "O", "outpatient": "O",
    "EMER": "E", "emergency": "E",
    "PRENC": "P", "pre-admission": "P",
}

ALLERGY_TYPE_MAP = {
    "allergy": "DA",
    "intolerance": "FA",
    "environment": "EA",
    "food": "FA",
}

CRITICALITY_MAP = {
    "high": "SV",
    "low": "MO",
    "unable-to-assess": "U",
}


def _encode_xcn(practitioner: Dict[str, Any]) -> str:
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
    suffix = (n.get("suffix") or [""])[0]
    prefix = (n.get("prefix") or [""])[0]
    return f"{npi}^{family}^{given}^{middle}^{suffix}^{prefix}".rstrip("^")


class ORUtoHL7Converter(BaseFHIRtoHL7Converter):

    def convert(self, bundle: Dict[str, Any]) -> str:
        patient       = self._first(bundle, "Patient")
        encounter     = self._first(bundle, "Encounter")
        practitioners = self._get_resources(bundle, "Practitioner")
        org           = self._first(bundle, "Organization")
        related       = self._get_resources(bundle, "RelatedPerson")
        allergies     = self._get_resources(bundle, "AllergyIntolerance")
        conditions    = self._get_resources(bundle, "Condition")
        coverages     = self._get_resources(bundle, "Coverage")
        immunizations = self._get_resources(bundle, "Immunization")
        reports       = self._get_resources(bundle, "DiagnosticReport")
        all_obs       = self._get_resources(bundle, "Observation")

        facility = org.get("name", "FACILITY") if org else "FACILITY"

        segments = [make_msh("FHIR_CONVERTER", facility, "ORU", "R01")]
        segments.append(self._build_pid(patient))

        # PV1
        if encounter:
            segments.append(self._build_pv1(encounter, practitioners))

        # NK1 — next of kin from RelatedPerson
        for idx, rp in enumerate(related, 1):
            seg = self._build_nk1(rp, idx)
            if seg:
                segments.append(seg)

        # AL1 — allergies
        for idx, allergy in enumerate(allergies, 1):
            seg = self._build_al1(allergy, idx)
            if seg:
                segments.append(seg)

        # DG1 — diagnoses
        for idx, cond in enumerate(conditions, 1):
            seg = self._build_dg1(cond, idx)
            if seg:
                segments.append(seg)

        # OBR / OBX
        if not reports:
            segments.append(self._build_obr(None, patient, practitioners, 1))
            for i, obs in enumerate(all_obs, 1):
                segments.append(self._build_obx(obs, i))
        else:
            for obr_idx, report in enumerate(reports, 1):
                segments.append(self._build_obr(report, patient, practitioners, obr_idx))
                obs_refs = {
                    r.get("reference", "").replace("Observation/", "")
                    for r in report.get("result", [])
                }
                report_obs = [o for o in all_obs if o.get("id", "") in obs_refs] or all_obs
                for obx_idx, obs in enumerate(report_obs, 1):
                    segments.append(self._build_obx(obs, obx_idx))

        # IN1 — insurance / coverage
        for idx, cov in enumerate(coverages, 1):
            seg = self._build_in1(cov, idx)
            if seg:
                segments.append(seg)

        # RXA / RXR — immunizations
        for idx, imm in enumerate(immunizations, 1):
            rxa = self._build_rxa(imm, idx)
            if rxa:
                segments.append(rxa)
                rxr = self._build_rxr(imm)
                if rxr:
                    segments.append(rxr)

        return "\r".join(s for s in segments if s)

    # ------------------------------------------------------------------
    def _build_pid(self, patient: Optional[Dict[str, Any]]) -> str:
        if not patient:
            return "PID|1"
        identifiers = patient.get("identifier", [])
        mrn = ""
        for ident in identifiers:
            type_code = (ident.get("type", {}).get("coding") or [{}])[0].get("code", "")
            if type_code in ("MR", "MRN") or not mrn:
                mrn = ident.get("value", "")
                if type_code in ("MR", "MRN"):
                    break
        pid3 = f"{mrn}^^^HOSP^MR" if mrn else ""
        names = patient.get("name", [])
        pid5 = encode_name(names[0]) if names else ""
        pid7 = fmt_date(patient.get("birthDate", ""))
        pid8 = GENDER_TO_HL7.get(patient.get("gender", "unknown"), "U")
        addresses = patient.get("address", [])
        from app.converters.fhir_to_hl7.base import encode_address
        pid11 = encode_address(addresses[0]) if addresses else ""
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
        marital = patient.get("maritalStatus", {})
        pid16 = ""
        if marital:
            codings = marital.get("coding", [])
            pid16 = codings[0].get("code", "") if codings else marital.get("text", "")
        fields = ["PID", "1", "", pid3, "", pid5, "", pid7, pid8, "", "", pid11, "", pid13, "", "", pid16]
        return "|".join(fields).rstrip("|")

    # ------------------------------------------------------------------
    def _build_pv1(
        self,
        encounter: Dict[str, Any],
        practitioners: List[Dict[str, Any]],
    ) -> str:
        enc_class = encounter.get("class", {})
        class_code = enc_class.get("code", "") if isinstance(enc_class, dict) else ""
        pv1_2 = ENCOUNTER_CLASS_MAP.get(class_code.upper(), ENCOUNTER_CLASS_MAP.get(class_code, "U"))

        locations = encounter.get("location", [])
        pv1_3 = locations[0].get("location", {}).get("display", "") if locations else ""

        def _xcn_by_ref(ref_str: str) -> str:
            prac_id = ref_str.replace("Practitioner/", "")
            for p in practitioners:
                if p.get("id") == prac_id:
                    return _encode_xcn(p)
            return ""

        pv1_7 = pv1_8 = ""
        for part in encounter.get("participant", []):
            types = part.get("type", [])
            type_code = (types[0].get("coding") or [{}])[0].get("code", "") if types else ""
            ref = (part.get("individual", {}) or part.get("actor", {})).get("reference", "")
            xcn = _xcn_by_ref(ref)
            if not xcn:
                continue
            if type_code.lower() in ("atnd", "attending") and not pv1_7:
                pv1_7 = xcn
            elif type_code.lower() in ("ref", "referring") and not pv1_8:
                pv1_8 = xcn
            elif not pv1_7:
                pv1_7 = xcn

        enc_ids = encounter.get("identifier", [])
        pv1_19 = enc_ids[0].get("value", "") if enc_ids else ""

        period = encounter.get("period", {})
        pv1_44 = fmt_datetime(period.get("start", ""))
        pv1_45 = fmt_datetime(period.get("end", ""))

        # PV1: 1=set_id 2=class 3=location 7=attending 8=referring 19=visit_no
        # Dates (44/45) omitted to avoid 24 empty pipe fields
        f = ["PV1", "1", pv1_2, pv1_3, "", "", "", pv1_7, pv1_8,
             "", "", "", "", "", "", "", "", "", "", pv1_19]
        return "|".join(f).rstrip("|")

    # ------------------------------------------------------------------
    def _build_nk1(self, rp: Dict[str, Any], index: int) -> str:
        names = rp.get("name", [])
        if not names:
            return ""
        name_str = encode_name(names[0])
        relationship = rp.get("relationship", [{}])
        rel_codings = (relationship[0].get("coding") or [{}]) if relationship else [{}]
        rel_code = rel_codings[0].get("code", "") if rel_codings else ""
        rel_display = rel_codings[0].get("display", "") if rel_codings else ""
        rel_str = f"{rel_code}^{rel_display}^HL70063".rstrip("^")
        telecoms = rp.get("telecom", [])
        phone = ""
        for t in telecoms:
            if t.get("system") == "phone":
                phone = t.get("value", "")
                break
        return f"NK1|{index}|{name_str}|{rel_str}|{phone}"

    # ------------------------------------------------------------------
    def _build_al1(self, allergy: Dict[str, Any], index: int) -> str:
        # AL1-2: allergy type
        category_list = allergy.get("category", [])
        raw_type = category_list[0] if category_list else "allergy"
        al1_2 = ALLERGY_TYPE_MAP.get(raw_type.lower(), "DA")

        # AL1-3: allergen code/description
        substance = allergy.get("code", {}) or allergy.get("substance", {})
        al1_3 = encode_coding(substance) if substance else "UNKNOWN"

        # AL1-4: severity
        severity = allergy.get("criticality", "")
        al1_4 = CRITICALITY_MAP.get(severity.lower(), "")

        # AL1-5: reaction (first reaction manifestation)
        reactions = allergy.get("reaction", [])
        al1_5 = ""
        if reactions:
            manifestations = reactions[0].get("manifestation", [])
            if manifestations:
                al1_5 = encode_coding(manifestations[0])

        return f"AL1|{index}|{al1_2}|{al1_3}|{al1_4}|{al1_5}".rstrip("|")

    # ------------------------------------------------------------------
    def _build_dg1(self, condition: Dict[str, Any], index: int) -> str:
        code = condition.get("code", {})
        dg1_3 = encode_coding(code) if code else ""

        # DG1-4: description (text)
        dg1_4 = code.get("text", "") if code else ""
        if not dg1_4 and code:
            codings = code.get("coding", [])
            dg1_4 = codings[0].get("display", "") if codings else ""

        # DG1-5: date/time
        onset = condition.get("onsetDateTime", "") or condition.get("recordedDate", "")
        dg1_5 = fmt_datetime(onset)

        # DG1-6: diagnosis type
        dg1_6 = "W"  # working

        # Clinical status
        clin_status = condition.get("clinicalStatus", {})
        clin_codings = clin_status.get("coding", []) if clin_status else []
        status_code = clin_codings[0].get("code", "").lower() if clin_codings else ""
        if status_code in ("resolved", "inactive"):
            dg1_6 = "F"  # final
        elif status_code == "active":
            dg1_6 = "A"  # admitting

        return f"DG1|{index}||{dg1_3}|{dg1_4}|{dg1_5}|{dg1_6}".rstrip("|")

    # ------------------------------------------------------------------
    def _build_in1(self, coverage: Dict[str, Any], index: int) -> str:
        payors = coverage.get("payor", [])
        payor_name = payors[0].get("display", "") if payors else ""

        plan_val = ""
        group_val = ""
        for cls in coverage.get("class", []):
            cls_type = (cls.get("type", {}).get("coding") or [{}])[0].get("code", "")
            if cls_type == "plan":
                plan_val = cls.get("value", "")
            elif cls_type == "group":
                group_val = cls.get("value", "")

        member_id = coverage.get("subscriberId", "")

        # Compact layout:
        # IN1-2: Plan ID  IN1-3: Member ID  IN1-4: Payor Name  IN1-8: Group Number
        fields = ["IN1", str(index), plan_val, member_id, payor_name, "", "", "", group_val]
        return "|".join(fields).rstrip("|")

    # ------------------------------------------------------------------
    def _build_rxa(self, immunization: Dict[str, Any], index: int) -> str:
        # RXA-3: date/time of substance administration
        occurrence = immunization.get("occurrenceDateTime", "")
        rxa_3 = fmt_datetime(occurrence)

        # RXA-5: administered code (vaccine code)
        vaccine_code = immunization.get("vaccineCode", {})
        rxa_5 = encode_coding(vaccine_code) if vaccine_code else ""

        # RXA-6: administered amount
        dose_qty = immunization.get("doseQuantity", {})
        rxa_6 = str(dose_qty.get("value", "")) if dose_qty else ""
        rxa_7 = dose_qty.get("unit", "") if dose_qty else ""

        # RXA-9: administration notes / status
        status = immunization.get("status", "completed")
        rxa_9 = "CP" if status == "completed" else "RE"  # CP=completed, RE=refused

        # RXA-15: substance lot number
        lot_number = immunization.get("lotNumber", "")

        # RXA-16: substance expiration date
        expiration = immunization.get("expirationDate", "")
        rxa_16 = fmt_date(expiration)

        # RXA-17: substance manufacturer
        manufacturers = immunization.get("manufacturer", {})
        rxa_17 = manufacturers.get("display", "") if manufacturers else ""

        fields = [
            "RXA", "0", str(index), rxa_3, rxa_3, rxa_5,
            rxa_6, rxa_7, "", rxa_9, "", "", "", "", "", lot_number,
            rxa_16, rxa_17,
        ]
        return "|".join(fields).rstrip("|")

    # ------------------------------------------------------------------
    def _build_rxr(self, immunization: Dict[str, Any]) -> str:
        routes = immunization.get("route", {})
        if not routes:
            return ""
        route_str = encode_coding(routes)
        site = immunization.get("site", {})
        site_str = encode_coding(site) if site else ""
        return f"RXR|{route_str}|{site_str}".rstrip("|")

    # ------------------------------------------------------------------
    def _build_obr(
        self,
        report: Optional[Dict[str, Any]],
        patient: Optional[Dict[str, Any]],
        practitioners: List[Dict[str, Any]],
        index: int,
    ) -> str:
        placer = filler = code_str = obs_dt = issued = provider_xcn = ""
        status = "F"

        if report:
            ids = report.get("identifier", [])
            for ident in ids:
                itype = (ident.get("type", {}).get("coding") or [{}])[0].get("code", "")
                val = ident.get("value", "")
                if itype == "PLAC":
                    placer = val
                elif itype == "FILL":
                    filler = val
            code_str = encode_coding(report.get("code", {}))
            obs_dt = fmt_datetime(report.get("effectiveDateTime", ""))
            status = REPORT_STATUS_MAP.get(report.get("status", "final"), "F")
            issued = fmt_datetime(report.get("issued", ""))

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
            "", "", obs_dt,
            "", "", "", "", "", "", "",
            "", provider_xcn,
            "", "", "", "", "", "",
            "", "", status,
        ]
        return "|".join(fields).rstrip("|")

    # ------------------------------------------------------------------
    def _build_obx(self, obs: Dict[str, Any], index: int) -> str:
        code_str = encode_coding(obs.get("code", {}))
        status = OBX_STATUS_MAP.get(obs.get("status", "final"), "F")

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

        ref_ranges = obs.get("referenceRange", [])
        ref_str = ref_ranges[0].get("text", "") if ref_ranges else ""

        interp = obs.get("interpretation", [])
        interp_str = ""
        if interp:
            codings = interp[0].get("coding", [])
            raw_code = codings[0].get("code", "") if codings else interp[0].get("text", "")
            interp_str = INTERP_MAP.get(raw_code.upper(), raw_code)

        eff_dt = fmt_datetime(obs.get("effectiveDateTime", ""))

        fields = [
            "OBX", str(index), value_type, code_str,
            "", value_str, units_str, ref_str, interp_str,
            "", "", status, "", "", eff_dt,
        ]
        return "|".join(fields).rstrip("|")
