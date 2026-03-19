"""
Base utilities for FHIR → HL7 v2.x conversion.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


def make_msg_id() -> str:
    return str(uuid.uuid4()).replace("-", "")[:20].upper()


def fmt_datetime(iso: Optional[str]) -> str:
    """Convert ISO 8601 datetime → HL7 YYYYMMDDHHMMSS."""
    if not iso:
        return ""
    try:
        s = iso.strip().rstrip("Z")
        # Try each format against the full string (strptime ignores trailing chars if we truncate)
        for fmt, data_len in [
            ("%Y-%m-%dT%H:%M:%S.%f", None),  # None = full string
            ("%Y-%m-%dT%H:%M:%S", 19),
            ("%Y-%m-%dT%H:%M", 16),
            ("%Y-%m-%d", 10),
        ]:
            try:
                candidate = s if data_len is None else s[:data_len]
                dt = datetime.strptime(candidate, fmt)
                return dt.strftime("%Y%m%d%H%M%S") if "T" in s else dt.strftime("%Y%m%d")
            except ValueError:
                continue
    except Exception:
        pass
    return ""


def fmt_date(iso: Optional[str]) -> str:
    """Convert ISO 8601 date → HL7 YYYYMMDD."""
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%Y%m%d")
    except Exception:
        return ""


def encode_name(name_dict: Dict[str, Any]) -> str:
    """FHIR HumanName → HL7 XPN: family^given^middle^suffix^prefix."""
    family = name_dict.get("family", "")
    given_list = name_dict.get("given", [])
    given = given_list[0] if given_list else ""
    middle = given_list[1] if len(given_list) > 1 else ""
    suffix = name_dict.get("suffix", [""])[0] if name_dict.get("suffix") else ""
    prefix = name_dict.get("prefix", [""])[0] if name_dict.get("prefix") else ""
    result = f"{family}^{given}^{middle}^{suffix}^{prefix}"
    return result.rstrip("^")


def encode_address(addr: Dict[str, Any]) -> str:
    """FHIR Address → HL7 XAD: street^other^city^state^zip^country."""
    lines = addr.get("line", [])
    street = lines[0] if lines else ""
    other = lines[1] if len(lines) > 1 else ""
    city = addr.get("city", "")
    state = addr.get("state", "")
    postal = addr.get("postalCode", "")
    country = addr.get("country", "")
    result = f"{street}^{other}^{city}^{state}^{postal}^{country}"
    return result.rstrip("^")


def encode_telecom(telecoms: List[Dict[str, Any]], use: str = "home") -> str:
    """Pick the first matching phone from FHIR ContactPoint list → HL7 phone string."""
    for t in telecoms:
        if t.get("system") == "phone" and (not use or t.get("use", "") == use or True):
            return t.get("value", "")
    return ""


def encode_coding(codeable: Dict[str, Any]) -> str:
    """FHIR CodeableConcept → HL7 CE: code^display^system."""
    codings = codeable.get("coding", [])
    if not codings:
        return codeable.get("text", "")
    c = codings[0]
    code = c.get("code", "")
    display = c.get("display", "") or codeable.get("text", "")
    system = reverse_system_uri(c.get("system", ""))
    return f"{code}^{display}^{system}".rstrip("^")


def reverse_system_uri(uri: str) -> str:
    """Map FHIR system URI → HL7 coding system abbreviation."""
    mapping = {
        "http://loinc.org": "LN",
        "http://snomed.info/sct": "SCT",
        "http://hl7.org/fhir/sid/icd-10": "ICD10",
        "http://hl7.org/fhir/sid/icd-9-cm": "ICD9",
        "http://www.ama-assn.org/go/cpt": "CPT4",
        "http://www.nlm.nih.gov/research/umls/rxnorm": "RXNORM",
        "http://hl7.org/fhir/sid/ndc": "NDC",
        "http://hl7.org/fhir/sid/us-npi": "NPI",
        "http://hl7.org/fhir/sid/cvx": "CVX",
    }
    return mapping.get(uri, uri)


GENDER_TO_HL7 = {"male": "M", "female": "F", "other": "O", "unknown": "U"}


def make_msh(
    sending_app: str,
    sending_facility: str,
    message_type: str,
    message_event: str,
    msg_id: Optional[str] = None,
    version: str = "2.5",
) -> str:
    """Build an MSH segment string."""
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    mid = msg_id or make_msg_id()
    return f"MSH|^~\\&|{sending_app}|{sending_facility}|FHIR_CONVERTER||{now}||{message_type}^{message_event}|{mid}|P|{version}"


class BaseFHIRtoHL7Converter:
    """Base class for FHIR Bundle → HL7 v2.x converters."""

    def convert(self, bundle: Dict[str, Any]) -> str:
        """Return a complete HL7 message string (segments separated by \\r)."""
        raise NotImplementedError

    def _get_resources(self, bundle: Dict[str, Any], resource_type: str) -> List[Dict[str, Any]]:
        return [
            e["resource"]
            for e in bundle.get("entry", [])
            if e.get("resource", {}).get("resourceType") == resource_type
        ]

    def _first(self, bundle: Dict[str, Any], resource_type: str) -> Optional[Dict[str, Any]]:
        resources = self._get_resources(bundle, resource_type)
        return resources[0] if resources else None
