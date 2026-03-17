"""
ORU (Observation Result Unsolicited) message converter.

Produces: Patient, DiagnosticReport, Observation resources.
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


# Maps HL7 result status to FHIR observation status
OBX_STATUS_MAP = {
    "F": "final",
    "P": "preliminary",
    "C": "corrected",
    "X": "cancelled",
    "I": "registered",
    "R": "registered",
    "S": "registered",
    "U": "unknown",
    "W": "entered-in-error",
    "A": "amended",
    "D": "entered-in-error",
    "N": "registered",
}

# Maps HL7 observation value type to FHIR quantity/type hints
OBX_VALUE_TYPES = {
    "NM": "numeric",
    "ST": "string",
    "TX": "text",
    "CE": "coded",
    "CWE": "coded",
    "DT": "date",
    "TM": "time",
    "TS": "datetime",
    "SN": "structured_numeric",
    "CX": "identifier",
    "XON": "organization_name",
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


class ORUConverter(BaseConverter):
    """Converts HL7 ORU^R01 messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str]]:
        resources = []
        warnings = []

        patient_id = make_id()
        patient = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)

        # Each OBR creates one DiagnosticReport + its OBX children
        obr_segments = parsed_msg.get_all_segments("OBR")
        obx_segments = parsed_msg.get_all_segments("OBX")

        if not obr_segments:
            warnings.append("No OBR segments found — creating minimal DiagnosticReport.")
            dr_id = make_id()
            dr = self._build_diagnostic_report(None, dr_id, patient_id, [], warnings)
            resources.append(dr)
            for obx in obx_segments:
                obs = self._build_observation(obx, patient_id, dr_id, warnings)
                resources.append(obs)
        else:
            # Associate OBX segments with their parent OBR by order of appearance
            # OBX sets belong to the most recently seen OBR
            all_segs = parsed_msg.parsed  # full message
            current_obr = None
            current_obr_obx: List = []
            obr_batches: List[Tuple[Any, List]] = []

            for seg in all_segs:
                seg_name = str(seg[0]).strip()
                if seg_name == "OBR":
                    if current_obr is not None:
                        obr_batches.append((current_obr, current_obr_obx))
                    current_obr = seg
                    current_obr_obx = []
                elif seg_name == "OBX" and current_obr is not None:
                    current_obr_obx.append(seg)
            # last batch
            if current_obr is not None:
                obr_batches.append((current_obr, current_obr_obx))

            for obr, obx_list in obr_batches:
                dr_id = make_id()
                obs_ids = []
                observations = []
                for obx in obx_list:
                    obs = self._build_observation(obx, patient_id, dr_id, warnings)
                    observations.append(obs)
                    obs_ids.append(obs["id"])

                dr = self._build_diagnostic_report(obr, dr_id, patient_id, obs_ids, warnings)
                resources.append(dr)
                resources.extend(observations)

        return resources, warnings

    # ------------------------------------------------------------------
    def _build_patient(self, msg: ParsedHL7Message, patient_id: str, warnings: list) -> Dict:
        pid = msg.get_segment("PID")
        resource: Dict[str, Any] = {"resourceType": "Patient", "id": patient_id}
        if pid is None:
            warnings.append("PID segment missing — Patient resource will be minimal.")
            return resource

        # Identifiers
        identifiers = []
        pid3 = safe_str(pid[3])
        if pid3:
            identifiers.append(extract_identifier(pid3, "http://hospital.example.org/mrn"))
        if identifiers:
            resource["identifier"] = identifiers

        # Name
        pid5 = safe_str(pid[5])
        if pid5:
            resource["name"] = [extract_name(pid5)]

        # DOB
        from app.converters.base import parse_hl7_date
        dob = parse_hl7_date(_field(pid, 7))
        if dob:
            resource["birthDate"] = dob

        return resource

    # ------------------------------------------------------------------
    def _build_diagnostic_report(
        self,
        obr,
        dr_id: str,
        patient_id: str,
        observation_ids: List[str],
        warnings: list,
    ) -> Dict:
        resource: Dict[str, Any] = {
            "resourceType": "DiagnosticReport",
            "id": dr_id,
            "subject": {"reference": f"Patient/{patient_id}"},
            "result": [{"reference": f"Observation/{oid}"} for oid in observation_ids],
        }

        if obr is None:
            resource["status"] = "unknown"
            resource["code"] = {"text": "Unknown order"}
            return resource

        # Status from OBR-25
        status_raw = _field(obr, 25).upper()
        resource["status"] = OBX_STATUS_MAP.get(status_raw, "unknown")

        # Order/test code (OBR-4)
        code_raw = _field(obr, 4)
        if code_raw:
            resource["code"] = extract_coding(code_raw, "http://loinc.org")
        else:
            resource["code"] = {"text": "Laboratory Result"}

        # Order number / identifiers (OBR-3)
        filler_order = _field(obr, 3)
        placer_order = _field(obr, 2)
        idents = []
        if filler_order:
            idents.append({"type": {"text": "FILL"}, "value": filler_order})
        if placer_order:
            idents.append({"type": {"text": "PLAC"}, "value": placer_order})
        if idents:
            resource["identifier"] = idents

        # Effective time (OBR-7 observation date)
        obs_dt = parse_hl7_datetime(_field(obr, 7))
        if obs_dt:
            resource["effectiveDateTime"] = obs_dt

        # Issued time (OBR-22 status change time)
        issued_dt = parse_hl7_datetime(_field(obr, 22))
        if issued_dt:
            resource["issued"] = issued_dt if "T" in issued_dt else issued_dt + "T00:00:00Z"

        # Category
        resource["category"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                "code": "LAB",
                "display": "Laboratory",
            }]
        }]

        return resource

    # ------------------------------------------------------------------
    def _build_observation(self, obx, patient_id: str, dr_id: str, warnings: list) -> Dict:
        resource: Dict[str, Any] = {
            "resourceType": "Observation",
            "id": make_id(),
            "subject": {"reference": f"Patient/{patient_id}"},
            "derivedFrom": [{"reference": f"DiagnosticReport/{dr_id}"}],
        }

        # Status (OBX-11)
        status_raw = _field(obx, 11).upper()
        resource["status"] = OBX_STATUS_MAP.get(status_raw, "unknown")

        # Observation code (OBX-3)
        obs_code = _field(obx, 3)
        if obs_code:
            resource["code"] = extract_coding(obs_code, "http://loinc.org")
        else:
            resource["code"] = {"text": "Observation"}

        # Value (OBX-5, type from OBX-2)
        value_type = _field(obx, 2).upper()
        raw_value = _field(obx, 5)
        units_raw = _field(obx, 6)

        if raw_value:
            if value_type == "NM":
                try:
                    qty: Dict[str, Any] = {"value": float(raw_value)}
                    if units_raw:
                        parts = units_raw.split("^")
                        qty["unit"] = parts[0]
                        qty["system"] = "http://unitsofmeasure.org"
                        qty["code"] = parts[0]
                    resource["valueQuantity"] = qty
                except ValueError:
                    resource["valueString"] = raw_value
            elif value_type in ("CE", "CWE"):
                resource["valueCodeableConcept"] = extract_coding(raw_value)
            elif value_type == "SN":
                # Structured numeric: comparator^value1^separator^value2
                parts = raw_value.split("^")
                comparator = parts[0].strip() if parts else ""
                num_val = parts[1].strip() if len(parts) > 1 else ""
                try:
                    qty = {"value": float(num_val)}
                    if comparator and comparator in ("<", ">", "<=", ">="):
                        qty["comparator"] = comparator
                    if units_raw:
                        unit_parts = units_raw.split("^")
                        qty["unit"] = unit_parts[0]
                        qty["system"] = "http://unitsofmeasure.org"
                        qty["code"] = unit_parts[0]
                    resource["valueQuantity"] = qty
                except ValueError:
                    resource["valueString"] = raw_value
            else:
                resource["valueString"] = raw_value

        # Reference range (OBX-7)
        ref_range = _field(obx, 7)
        if ref_range:
            resource["referenceRange"] = [{"text": ref_range}]

        # Interpretation (OBX-8)
        interp = _field(obx, 8)
        if interp:
            resource["interpretation"] = [extract_coding(
                interp,
                "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"
            )]

        # Observation date/time (OBX-14)
        obs_dt_raw = _field(obx, 14)
        if obs_dt_raw:
            obs_dt = parse_hl7_datetime(obs_dt_raw)
            if obs_dt:
                resource["effectiveDateTime"] = obs_dt

        # Body site / method (OBX-15, OBX-17)
        method_raw = _field(obx, 17)
        if method_raw:
            resource["method"] = extract_coding(method_raw)

        return resource
