"""
Local EHR pipe-delimited → FHIR R4 converter.

Supports the format:
  PATIENT|MRN|First|Last|DOB|Gender|Language|Phone|Address|City|State|Zip
  ENCOUNTER|VisitID|VisitType|Location|ProviderID|ProviderName|Start|End
  ALLERGY|Seq|Substance|Reaction|OnsetDate
  DIAGNOSIS|Seq|ICDCode|Description
  LAB_ORDER|OrderID|PanelName|OrderedTime
  LAB_RESULT|Seq|LOINCCode|TestName|Value|Unit|RefRange|Flag
  VITAL|Type|Value|Unit
  IMMUNIZATION|VaccineName|Date|Dose|Unit|Route|Site
  INSURANCE|ProviderName|Plan|Group|MemberID
  NK1|Seq|Name|Relationship|Phone
  PROVIDER|ID|Name|Role
"""
import re
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── LOINC codes for common vitals ────────────────────────────────────────────
_VITAL_LOINC = {
    "BP":     ("55284-4", "Blood pressure panel"),
    "BPSYS":  ("8480-6",  "Systolic blood pressure"),
    "BPDIAS": ("8462-4",  "Diastolic blood pressure"),
    "HR":     ("8867-4",  "Heart rate"),
    "WEIGHT": ("29463-7", "Body weight"),
    "TEMP":   ("8310-5",  "Body temperature"),
    "SPO2":   ("59408-5", "Oxygen saturation"),
    "RR":     ("9279-1",  "Respiratory rate"),
    "HEIGHT": ("8302-2",  "Body height"),
    "BMI":    ("39156-5", "Body mass index"),
}

# ── Interpretation code map ───────────────────────────────────────────────────
_FLAG_MAP = {
    "normal": "N", "n": "N",
    "high": "H",   "h": "H",
    "low": "L",    "l": "L",
    "critical": "C", "c": "C",
    "abnormal": "A", "a": "A",
}

# ── Route CVX / route code maps ───────────────────────────────────────────────
_ROUTE_CODE = {
    "intramuscular": "IM", "im": "IM",
    "oral": "PO",          "po": "PO",
    "intravenous": "IV",   "iv": "IV",
    "subcutaneous": "SC",  "sc": "SC",
    "intranasal": "NS",    "ns": "NS",
}


def _uid() -> str:
    return str(uuid.uuid4())


def _fmt_date(raw: str) -> Optional[str]:
    """Normalise any date-like string to YYYY-MM-DD."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw if raw else None


def _fmt_datetime(raw: str) -> Optional[str]:
    """Normalise to YYYY-MM-DDTHH:MM:SS."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return _fmt_date(raw)  # fallback to date only


def _gender(raw: str) -> str:
    raw = raw.strip().lower()
    return {"male": "male", "m": "male", "female": "female", "f": "female"}.get(raw, "unknown")


def _cols(line: str) -> List[str]:
    """Split pipe-delimited line, strip whitespace per field."""
    return [c.strip() for c in line.split("|")]


# ─────────────────────────────────────────────────────────────────────────────
# Per-record parsers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_patient(cols: List[str], ctx: dict) -> dict:
    """PATIENT|MRN|First|Last|DOB|Gender|Language|Phone|Address|City|State|Zip"""
    mrn     = cols[1] if len(cols) > 1 else _uid()
    first   = cols[2] if len(cols) > 2 else ""
    last    = cols[3] if len(cols) > 3 else ""
    dob     = _fmt_date(cols[4]) if len(cols) > 4 else None
    gender  = _gender(cols[5]) if len(cols) > 5 else "unknown"
    lang    = cols[6] if len(cols) > 6 else ""
    phone   = cols[7] if len(cols) > 7 else ""
    addr    = cols[8] if len(cols) > 8 else ""
    city    = cols[9] if len(cols) > 9 else ""
    state   = cols[10] if len(cols) > 10 else ""
    zipcode = cols[11] if len(cols) > 11 else ""

    ctx["patient_id"] = mrn

    res: dict = {
        "resourceType": "Patient",
        "id": mrn,
        "identifier": [{"system": "urn:oid:local:mrn", "value": mrn, "type": {
            "coding": [{"code": "MR"}]
        }}],
        "name": [{"use": "official", "family": last, "given": [first] if first else []}],
        "gender": gender,
    }
    if dob:
        res["birthDate"] = dob
    if phone:
        res["telecom"] = [{"system": "phone", "value": phone, "use": "home"}]
    if addr or city:
        res["address"] = [{"use": "home", "line": [addr], "city": city, "state": state, "postalCode": zipcode, "country": "US"}]
    if lang:
        res["communication"] = [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": lang.lower()[:2]}]}, "preferred": True}]
    return res


def _parse_encounter(cols: List[str], ctx: dict) -> List[dict]:
    """ENCOUNTER|VisitID|VisitType|Location|ProviderID|ProviderName|Start|End"""
    visit_id     = cols[1] if len(cols) > 1 else _uid()
    visit_type   = cols[2] if len(cols) > 2 else "outpatient"
    location     = cols[3] if len(cols) > 3 else ""
    provider_id  = cols[4] if len(cols) > 4 else _uid()
    provider_name= cols[5] if len(cols) > 5 else ""
    start        = _fmt_datetime(cols[6]) if len(cols) > 6 else None
    end          = _fmt_datetime(cols[7]) if len(cols) > 7 else None

    ctx["encounter_id"]  = visit_id
    ctx["provider_id"]   = provider_id
    ctx["provider_name"] = provider_name

    # Encounter class code
    vt_lower = visit_type.lower()
    if "inpatient" in vt_lower or "inp" in vt_lower:
        cls_code, cls_display = "IMP", "inpatient encounter"
    elif "emergency" in vt_lower or "er" in vt_lower:
        cls_code, cls_display = "EMER", "emergency"
    elif "tele" in vt_lower or "virtual" in vt_lower or "remote" in vt_lower:
        cls_code, cls_display = "VR", "virtual"
    else:
        cls_code, cls_display = "AMB", "ambulatory"

    encounter: dict = {
        "resourceType": "Encounter",
        "id": visit_id,
        "status": "finished",
        "class": {"code": cls_code, "display": cls_display},
        "type": [{"text": visit_type}],
        "subject": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
        "participant": [{"individual": {"reference": f"Practitioner/{provider_id}"}}],
    }
    if start or end:
        encounter["period"] = {}
        if start:
            encounter["period"]["start"] = start
        if end:
            encounter["period"]["end"] = end
    if location:
        encounter["location"] = [{"location": {"display": location}}]

    # Parse provider name (supports "Dr. First Last" or "First Last")
    name_parts = re.sub(r"^Dr\.?\s*", "", provider_name).strip().split()
    pract_family = name_parts[-1] if name_parts else provider_name
    pract_given  = name_parts[:-1] if len(name_parts) > 1 else []

    practitioner: dict = {
        "resourceType": "Practitioner",
        "id": provider_id,
        "identifier": [{"system": "urn:oid:local:provider", "value": provider_id}],
        "name": [{"use": "official", "family": pract_family, "given": pract_given,
                  "prefix": ["Dr."] if "Dr" in provider_name else []}],
    }
    return [encounter, practitioner]


def _parse_allergy(cols: List[str], ctx: dict) -> dict:
    """ALLERGY|Seq|Substance|Reaction|OnsetDate"""
    seq       = cols[1] if len(cols) > 1 else "1"
    substance = cols[2] if len(cols) > 2 else "Unknown"
    reaction  = cols[3] if len(cols) > 3 else ""
    onset     = _fmt_date(cols[4]) if len(cols) > 4 else None

    res: dict = {
        "resourceType": "AllergyIntolerance",
        "id": f"allergy-{seq}",
        "clinicalStatus": {"coding": [{"code": "active"}]},
        "verificationStatus": {"coding": [{"code": "confirmed"}]},
        "type": "allergy",
        "patient": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
        "code": {"text": substance, "coding": [{"display": substance}]},
    }
    if reaction:
        res["reaction"] = [{"manifestation": [{"text": reaction}]}]
    if onset:
        res["onsetDateTime"] = onset
    return res


def _parse_diagnosis(cols: List[str], ctx: dict) -> dict:
    """DIAGNOSIS|Seq|ICDCode|Description"""
    seq   = cols[1] if len(cols) > 1 else "1"
    code  = cols[2] if len(cols) > 2 else ""
    desc  = cols[3] if len(cols) > 3 else ""

    system = "http://hl7.org/fhir/sid/icd-10-cm" if re.match(r"[A-Z]\d", code) else "http://hl7.org/fhir/sid/icd-9-cm"

    return {
        "resourceType": "Condition",
        "id": f"condition-{seq}",
        "clinicalStatus": {"coding": [{"code": "active"}]},
        "verificationStatus": {"coding": [{"code": "confirmed"}]},
        "subject": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
        "encounter": {"reference": f"Encounter/{ctx.get('encounter_id', 'unknown')}"},
        "code": {"coding": [{"system": system, "code": code, "display": desc}], "text": desc},
    }


def _parse_lab_order(cols: List[str], ctx: dict) -> dict:
    """LAB_ORDER|OrderID|PanelName|OrderedTime"""
    order_id   = cols[1] if len(cols) > 1 else _uid()
    panel_name = cols[2] if len(cols) > 2 else "Lab Panel"
    ordered    = _fmt_datetime(cols[3]) if len(cols) > 3 else None

    ctx["order_id"] = order_id

    res: dict = {
        "resourceType": "ServiceRequest",
        "id": order_id,
        "status": "completed",
        "intent": "order",
        "subject": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
        "encounter": {"reference": f"Encounter/{ctx.get('encounter_id', 'unknown')}"},
        "requester": {"reference": f"Practitioner/{ctx.get('provider_id', 'unknown')}"},
        "identifier": [{"value": order_id}],
        "code": {"text": panel_name},
    }
    if ordered:
        res["authoredOn"] = ordered
    return res


def _parse_lab_result(cols: List[str], ctx: dict) -> Tuple[Optional[dict], Optional[dict]]:
    """LAB_RESULT|Seq|LOINCCode|TestName|Value|Unit|RefRange|Flag
    Returns (Observation, adds ref to DiagnosticReport)
    """
    seq      = cols[1] if len(cols) > 1 else "1"
    loinc    = cols[2] if len(cols) > 2 else ""
    test     = cols[3] if len(cols) > 3 else "Unknown"
    value    = cols[4] if len(cols) > 4 else ""
    unit     = cols[5] if len(cols) > 5 else ""
    ref_rng  = cols[6] if len(cols) > 6 else ""
    flag_raw = cols[7].strip().lower() if len(cols) > 7 else "normal"
    flag     = _FLAG_MAP.get(flag_raw, "N")

    obs_id = f"obs-{seq}"
    ctx.setdefault("obs_ids", []).append(obs_id)

    obs: dict = {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "subject": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
        "encounter": {"reference": f"Encounter/{ctx.get('encounter_id', 'unknown')}"},
        "code": {
            "coding": [{"system": "http://loinc.org", "code": loinc, "display": test}],
            "text": test,
        },
        "interpretation": [{"coding": [{"code": flag}]}],
    }

    # Try numeric value first, fallback to string
    try:
        obs["valueQuantity"] = {"value": float(value), "unit": unit, "system": "http://unitsofmeasure.org", "code": unit}
    except (ValueError, TypeError):
        obs["valueString"] = value

    if ref_rng:
        low_high = ref_rng.split("-")
        rr: dict = {"text": ref_rng}
        if len(low_high) == 2:
            try:
                rr["low"]  = {"value": float(low_high[0]), "unit": unit}
                rr["high"] = {"value": float(low_high[1]), "unit": unit}
            except ValueError:
                pass
        obs["referenceRange"] = [rr]

    return obs


def _parse_vital(cols: List[str], ctx: dict) -> List[dict]:
    """VITAL|Type|Value|Unit — returns one or two Observations (BP splits into systolic/diastolic)"""
    vtype = cols[1].strip().upper() if len(cols) > 1 else "UNKNOWN"
    value = cols[2].strip() if len(cols) > 2 else ""
    unit  = cols[3].strip() if len(cols) > 3 else ""

    ctx.setdefault("vital_seq", 0)
    ctx["vital_seq"] += 1
    seq = ctx["vital_seq"]

    observations = []

    if vtype == "BP" and "/" in value:
        # Split into systolic + diastolic
        parts = value.split("/")
        for i, (sub_type, val_str) in enumerate(zip(["BPSYS", "BPDIAS"], parts)):
            loinc, display = _VITAL_LOINC.get(sub_type, ("", sub_type))
            obs: dict = {
                "resourceType": "Observation",
                "id": f"vital-{seq}-{i+1}",
                "status": "final",
                "category": [{"coding": [{"code": "vital-signs"}]}],
                "subject": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
                "encounter": {"reference": f"Encounter/{ctx.get('encounter_id', 'unknown')}"},
                "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": display}], "text": display},
            }
            try:
                obs["valueQuantity"] = {"value": float(val_str.strip()), "unit": "mm[Hg]", "system": "http://unitsofmeasure.org"}
            except ValueError:
                obs["valueString"] = val_str.strip()
            observations.append(obs)
    else:
        loinc, display = _VITAL_LOINC.get(vtype, ("", vtype))
        obs = {
            "resourceType": "Observation",
            "id": f"vital-{seq}",
            "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
            "subject": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
            "encounter": {"reference": f"Encounter/{ctx.get('encounter_id', 'unknown')}"},
            "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": display or vtype}], "text": display or vtype},
        }
        try:
            obs["valueQuantity"] = {"value": float(value), "unit": unit, "system": "http://unitsofmeasure.org"}
        except ValueError:
            obs["valueString"] = value
        observations.append(obs)

    return observations


def _parse_immunization(cols: List[str], ctx: dict) -> dict:
    """IMMUNIZATION|VaccineName|Date|Dose|Unit|Route|Site"""
    ctx.setdefault("imm_seq", 0)
    ctx["imm_seq"] += 1
    seq     = ctx["imm_seq"]
    vaccine = cols[1] if len(cols) > 1 else "Unknown"
    date    = _fmt_date(cols[2]) if len(cols) > 2 else None
    dose    = cols[3] if len(cols) > 3 else ""
    unit    = cols[4] if len(cols) > 4 else ""
    route   = cols[5].strip() if len(cols) > 5 else ""
    site    = cols[6].strip() if len(cols) > 6 else ""

    route_code = _ROUTE_CODE.get(route.lower(), route)

    res: dict = {
        "resourceType": "Immunization",
        "id": f"imm-{seq}",
        "status": "completed",
        "patient": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
        "encounter": {"reference": f"Encounter/{ctx.get('encounter_id', 'unknown')}"},
        "vaccineCode": {"text": vaccine, "coding": [{"display": vaccine}]},
        "performer": [{"actor": {"reference": f"Practitioner/{ctx.get('provider_id', 'unknown')}"}}],
    }
    if date:
        res["occurrenceDateTime"] = date
    if dose and unit:
        try:
            res["doseQuantity"] = {"value": float(dose), "unit": unit, "system": "http://unitsofmeasure.org"}
        except ValueError:
            pass
    if route:
        res["route"] = {"coding": [{"code": route_code, "display": route}], "text": route}
    if site:
        res["site"] = {"text": site}
    return res


def _parse_insurance(cols: List[str], ctx: dict) -> dict:
    """INSURANCE|ProviderName|Plan|Group|MemberID"""
    provider  = cols[1] if len(cols) > 1 else "Unknown"
    plan      = cols[2] if len(cols) > 2 else ""
    group     = cols[3] if len(cols) > 3 else ""
    member_id = cols[4] if len(cols) > 4 else ""

    ctx.setdefault("ins_seq", 0)
    ctx["ins_seq"] += 1
    seq = ctx["ins_seq"]

    return {
        "resourceType": "Coverage",
        "id": f"coverage-{seq}",
        "status": "active",
        "beneficiary": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
        "payor": [{"display": provider}],
        "subscriberId": member_id,
        "class": [
            {"type": {"coding": [{"code": "plan"}]}, "value": plan, "name": plan},
            {"type": {"coding": [{"code": "group"}]}, "value": group},
        ],
    }


def _parse_nk1(cols: List[str], ctx: dict) -> dict:
    """NK1|Seq|Name|Relationship|Phone"""
    seq      = cols[1] if len(cols) > 1 else "1"
    name     = cols[2] if len(cols) > 2 else ""
    rel      = cols[3] if len(cols) > 3 else ""
    phone    = cols[4] if len(cols) > 4 else ""

    name_parts = name.strip().split()
    family = name_parts[-1] if name_parts else name
    given  = name_parts[:-1]

    res: dict = {
        "resourceType": "RelatedPerson",
        "id": f"related-{seq}",
        "patient": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
        "name": [{"family": family, "given": given}],
        "relationship": [{"text": rel}],
    }
    if phone:
        res["telecom"] = [{"system": "phone", "value": phone}]
    return res


# ─────────────────────────────────────────────────────────────────────────────
# Field mappings builder
# ─────────────────────────────────────────────────────────────────────────────

_FIELD_DEFS = {
    "PATIENT":     ["MRN", "First Name", "Last Name", "DOB", "Gender", "Language", "Phone", "Address", "City", "State", "Zip"],
    "ENCOUNTER":   ["Visit ID", "Visit Type", "Location", "Provider ID", "Provider Name", "Start Time", "End Time"],
    "ALLERGY":     ["Seq", "Substance", "Reaction", "Onset Date"],
    "DIAGNOSIS":   ["Seq", "ICD Code", "Description"],
    "LAB_ORDER":   ["Order ID", "Panel Name", "Ordered Time"],
    "LAB_RESULT":  ["Seq", "LOINC Code", "Test Name", "Value", "Unit", "Ref Range", "Flag"],
    "VITAL":       ["Type", "Value", "Unit"],
    "IMMUNIZATION":["Vaccine Name", "Date", "Dose", "Unit", "Route", "Site"],
    "INSURANCE":   ["Provider Name", "Plan", "Group", "Member ID"],
    "NK1":         ["Seq", "Name", "Relationship", "Phone"],
}

_FHIR_MAP = {
    "PATIENT":     ["identifier[0].value", "name[0].given[0]", "name[0].family", "birthDate", "gender", "communication[0].language", "telecom[0].value", "address[0].line[0]", "address[0].city", "address[0].state", "address[0].postalCode"],
    "ENCOUNTER":   ["id", "type[0].text", "location[0].location.display", "participant[0].individual.reference", "participant[0].individual.display", "period.start", "period.end"],
    "ALLERGY":     ["id (seq)", "code.text", "reaction[0].manifestation[0].text", "onsetDateTime"],
    "DIAGNOSIS":   ["id (seq)", "code.coding[0].code", "code.coding[0].display"],
    "LAB_ORDER":   ["identifier[0].value", "code.text", "authoredOn"],
    "LAB_RESULT":  ["id (seq)", "code.coding[0].code", "code.text", "valueQuantity.value", "valueQuantity.unit", "referenceRange[0].text", "interpretation[0].coding[0].code"],
    "VITAL":       ["code.coding[0].display", "valueQuantity.value", "valueQuantity.unit"],
    "IMMUNIZATION":["vaccineCode.text", "occurrenceDateTime", "doseQuantity.value", "doseQuantity.unit", "route.text", "site.text"],
    "INSURANCE":   ["payor[0].display", "class[plan].value", "class[group].value", "subscriberId"],
    "NK1":         ["id (seq)", "name[0].text", "relationship[0].text", "telecom[0].value"],
}


def _build_mappings(lines_by_type: Dict[str, List[List[str]]]) -> List[dict]:
    """Build field_mappings array from parsed line data."""
    mappings = []
    resource_type_map = {
        "PATIENT": "Patient", "ENCOUNTER": "Encounter",
        "ALLERGY": "AllergyIntolerance", "DIAGNOSIS": "Condition",
        "LAB_ORDER": "ServiceRequest", "LAB_RESULT": "Observation",
        "VITAL": "Observation", "IMMUNIZATION": "Immunization",
        "INSURANCE": "Coverage", "NK1": "RelatedPerson",
    }
    for record_type, lines in lines_by_type.items():
        field_names = _FIELD_DEFS.get(record_type, [])
        fhir_fields = _FHIR_MAP.get(record_type, [])
        rt = resource_type_map.get(record_type, record_type)
        for line_cols in lines:
            seq_id = line_cols[1] if len(line_cols) > 1 else "?"
            fm = []
            for i, (fname, fhir_path) in enumerate(zip(field_names, fhir_fields)):
                col_idx = i + 1
                val = line_cols[col_idx] if col_idx < len(line_cols) else ""
                if val:
                    fm.append({
                        "fhir_field": fhir_path,
                        "hl7_segment": record_type,
                        "hl7_field": str(col_idx),
                        "hl7_value": val,
                        "description": fname,
                    })
            mappings.append({
                "resource_type": rt,
                "resource_id": seq_id,
                "field_mappings": fm,
            })
    return mappings


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def convert_ehr_pipe_to_fhir(ehr_text: str) -> dict:
    """
    Parse pipe-delimited EHR text and return a dict matching the ConversionResult schema.
    No external API calls — pure local processing.
    """
    resources: List[dict] = []
    ctx: dict = {}
    warnings: List[str] = []
    lines_by_type: Dict[str, List[List[str]]] = {}

    # Determine message type after parsing
    has_obs = False
    has_svc = False

    for raw_line in ehr_text.replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        cols = _cols(line)
        record_type = cols[0].upper()
        lines_by_type.setdefault(record_type, []).append(cols)

        try:
            if record_type == "PATIENT":
                resources.append(_parse_patient(cols, ctx))
            elif record_type == "ENCOUNTER":
                resources.extend(_parse_encounter(cols, ctx))
            elif record_type == "ALLERGY":
                resources.append(_parse_allergy(cols, ctx))
            elif record_type == "DIAGNOSIS":
                resources.append(_parse_diagnosis(cols, ctx))
            elif record_type == "LAB_ORDER":
                resources.append(_parse_lab_order(cols, ctx))
                has_svc = True
            elif record_type == "LAB_RESULT":
                obs = _parse_lab_result(cols, ctx)
                resources.append(obs)
                has_obs = True
            elif record_type == "VITAL":
                resources.extend(_parse_vital(cols, ctx))
                has_obs = True
            elif record_type == "IMMUNIZATION":
                resources.append(_parse_immunization(cols, ctx))
            elif record_type == "INSURANCE":
                resources.append(_parse_insurance(cols, ctx))
            elif record_type == "NK1":
                resources.append(_parse_nk1(cols, ctx))
            else:
                warnings.append(f"Unrecognised record type '{record_type}' — skipped.")
        except Exception as exc:
            warnings.append(f"Error parsing {record_type} line: {exc}")
            logger.warning("EHR parser error on line '%s': %s", line, exc)

    if not resources:
        return {"success": False, "errors": ["No valid EHR records found. Check the format."], "warnings": warnings}

    # Add DiagnosticReport if lab results exist
    if has_obs and ctx.get("order_id"):
        obs_refs = [{"reference": f"Observation/{oid}"} for oid in ctx.get("obs_ids", [])]
        dr: dict = {
            "resourceType": "DiagnosticReport",
            "id": f"dr-{ctx.get('order_id', _uid())}",
            "status": "final",
            "subject": {"reference": f"Patient/{ctx.get('patient_id', 'unknown')}"},
            "encounter": {"reference": f"Encounter/{ctx.get('encounter_id', 'unknown')}"},
            "code": {"text": "Lab Results"},
            "result": obs_refs,
            "basedOn": [{"reference": f"ServiceRequest/{ctx.get('order_id')}"}],
        }
        resources.insert(-1, dr)

    # Determine message type
    if has_obs:
        msg_type = "ORU"
    elif has_svc:
        msg_type = "ORM"
    else:
        msg_type = "ADT"

    # Build FHIR Bundle
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources],
    }

    # Build resource summary
    resource_summary = []
    for r in resources:
        rt = r.get("resourceType", "Unknown")
        rid = r.get("id", _uid())
        # Description
        if rt == "Patient":
            names = r.get("name", [{}])
            family = names[0].get("family", "") if names else ""
            given  = " ".join(names[0].get("given", [])) if names else ""
            desc   = f"{given} {family}".strip() or "Patient"
        elif rt == "Practitioner":
            names = r.get("name", [{}])
            family = names[0].get("family", "") if names else ""
            given  = " ".join(names[0].get("given", [])) if names else ""
            desc   = f"Dr. {given} {family}".strip() or "Practitioner"
        elif rt == "Encounter":
            cls = r.get("class", {}).get("display", "")
            desc = f"Encounter ({cls})" if cls else "Encounter"
        elif rt == "Observation":
            desc = r.get("code", {}).get("text", "Observation")
        elif rt == "Condition":
            desc = r.get("code", {}).get("text", "Condition")
        elif rt == "AllergyIntolerance":
            desc = r.get("code", {}).get("text", "AllergyIntolerance")
        elif rt == "Immunization":
            desc = r.get("vaccineCode", {}).get("text", "Immunization")
        elif rt == "Coverage":
            payors = r.get("payor", [{}])
            payor_name = payors[0].get("display", "") if payors else ""
            plan_val  = next((c.get("value","") for c in r.get("class",[]) if c.get("type",{}).get("coding",[{}])[0].get("code") == "plan"), "")
            group_val = next((c.get("value","") for c in r.get("class",[]) if c.get("type",{}).get("coding",[{}])[0].get("code") == "group"), "")
            member_id = r.get("subscriberId", "")
            parts = [payor_name]
            if plan_val:  parts.append(f"Plan: {plan_val}")
            if group_val: parts.append(f"Group: {group_val}")
            if member_id: parts.append(f"MBR: {member_id}")
            desc = " | ".join(p for p in parts if p)
        elif rt == "ServiceRequest":
            desc = r.get("code", {}).get("text", "ServiceRequest")
        elif rt == "DiagnosticReport":
            desc = r.get("code", {}).get("text", "DiagnosticReport")
        else:
            desc = f"{rt} resource"
        resource_summary.append({"resource_type": rt, "resource_id": rid, "description": desc})

    # Build field mappings
    field_mappings = _build_mappings(lines_by_type)

    return {
        "success": True,
        "hl7_version": "N/A",
        "message_type": msg_type,
        "message_event": "EHR_PIPE",
        "direction": "ehr_to_fhir",
        "fhir_json": bundle,
        "fhir_xml": "",          # XML built by renderer in route
        "resource_summary": resource_summary,
        "field_mappings": field_mappings,
        "warnings": warnings,
        "errors": [],
        "ai_powered": False,
    }
