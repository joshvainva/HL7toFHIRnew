"""
Base FHIR converter — common utilities shared by all message-type converters.
"""
import re
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

import hl7


def make_id() -> str:
    """Generate a short deterministic-style UUID string."""
    return str(uuid.uuid4()).replace("-", "")[:16]


def safe_str(val: Any) -> str:
    """Convert any hl7 field value to a clean Python string."""
    if val is None:
        return ""
    return str(val).strip()


def parse_hl7_datetime(raw: str) -> Optional[str]:
    """
    Parse HL7 datetime formats (YYYYMMDDHHMMSS, YYYYMMDD, etc.)
    and return ISO 8601 string.
    """
    raw = raw.strip()
    if not raw:
        return None
    formats = [
        ("%Y%m%d%H%M%S%f", 14),
        ("%Y%m%d%H%M%S", 14),
        ("%Y%m%d%H%M", 12),
        ("%Y%m%d", 8),
    ]
    # Remove timezone offset if present (e.g., -0500)
    raw_clean = re.sub(r"[+-]\d{4}$", "", raw)
    for fmt, length in formats:
        try:
            dt = datetime.strptime(raw_clean[:length], fmt)
            if length == 8:
                return dt.date().isoformat()
            return dt.isoformat()
        except ValueError:
            continue
    return raw  # Return as-is if we can't parse it


def parse_hl7_date(raw: str) -> Optional[str]:
    """Parse HL7 date (YYYYMMDD) into ISO 8601 date string."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:8], "%Y%m%d").date().isoformat()
    except ValueError:
        return raw


def extract_name(name_field: Any) -> Dict[str, Any]:
    """
    Parse HL7 XPN name field (family^given^middle^suffix^prefix).
    Returns a FHIR HumanName dict.
    """
    parts = str(name_field).split("^")

    def get(idx): return parts[idx].strip() if len(parts) > idx else ""

    name: Dict[str, Any] = {"use": "official"}
    family = get(0)
    given = get(1)
    middle = get(2)
    suffix = get(3)
    prefix = get(4)

    if family:
        name["family"] = family
    given_list = [g for g in [given, middle] if g]
    if given_list:
        name["given"] = given_list
    if prefix:
        name["prefix"] = [prefix]
    if suffix:
        name["suffix"] = [suffix]
    return name


def extract_address(addr_field: Any) -> Dict[str, Any]:
    """
    Parse HL7 XAD address field.
    street^other^city^state^zip^country^type
    """
    parts = str(addr_field).split("^")

    def get(idx): return parts[idx].strip() if len(parts) > idx else ""

    addr: Dict[str, Any] = {}
    street = get(0)
    city = get(2)
    state = get(3)
    postal = get(4)
    country = get(5)

    lines = [l for l in [street, get(1)] if l]
    if lines:
        addr["line"] = lines
    if city:
        addr["city"] = city
    if state:
        addr["state"] = state
    if postal:
        addr["postalCode"] = postal
    if country:
        addr["country"] = country
    return addr


def extract_telecom(phone_field: Any, email_field: Any = None) -> List[Dict[str, Any]]:
    """Build FHIR ContactPoint list from HL7 phone/email fields."""
    result = []
    phone = safe_str(phone_field)
    if phone:
        # HL7 phone: (555)555-5555^NET^Internet or just number
        parts = phone.split("^")
        number = parts[0].strip()
        if number:
            result.append({"system": "phone", "value": number, "use": "home"})
    if email_field:
        email = safe_str(email_field)
        if email:
            result.append({"system": "email", "value": email})
    return result


def extract_identifier(id_field: Any, system_prefix: str = "urn:hl7:id") -> Dict[str, Any]:
    """Build a FHIR Identifier from an HL7 CX field (id^check^authority)."""
    parts = str(id_field).split("^")
    value = parts[0].strip() if parts else ""
    authority = parts[2].strip() if len(parts) > 2 else ""
    ident: Dict[str, Any] = {"value": value}
    if authority:
        ident["system"] = f"{system_prefix}:{authority}"
    else:
        ident["system"] = system_prefix
    return ident


def extract_coding(coded_field: Any, default_system: str = "") -> Dict[str, Any]:
    """
    Parse HL7 CE/CWE coded field: code^display^system^altCode^altDisplay^altSystem
    Returns FHIR CodeableConcept dict.
    """
    parts = str(coded_field).split("^")

    def get(idx): return parts[idx].strip() if len(parts) > idx else ""

    code = get(0)
    display = get(1)
    system = get(2) or default_system

    coding = {}
    if code:
        coding["code"] = code
    if display:
        coding["display"] = display
    if system:
        # Map common HL7 coding systems to FHIR URIs
        coding["system"] = map_coding_system(system)

    concept: Dict[str, Any] = {}
    if coding:
        concept["coding"] = [coding]
    if display:
        concept["text"] = display
    return concept


def map_coding_system(system: str) -> str:
    """Map HL7 coding system identifiers to FHIR system URIs."""
    mapping = {
        "LN": "http://loinc.org",
        "LOINC": "http://loinc.org",
        "SCT": "http://snomed.info/sct",
        "SNOMED": "http://snomed.info/sct",
        "ICD10": "http://hl7.org/fhir/sid/icd-10",
        "I10": "http://hl7.org/fhir/sid/icd-10",
        "ICD9": "http://hl7.org/fhir/sid/icd-9-cm",
        "I9": "http://hl7.org/fhir/sid/icd-9-cm",
        "CPT4": "http://www.ama-assn.org/go/cpt",
        "C4": "http://www.ama-assn.org/go/cpt",
        "RXNORM": "http://www.nlm.nih.gov/research/umls/rxnorm",
        "NDC": "http://hl7.org/fhir/sid/ndc",
        "NPI": "http://hl7.org/fhir/sid/us-npi",
        "HL70001": "http://terminology.hl7.org/CodeSystem/v2-0001",
        "HL70002": "http://terminology.hl7.org/CodeSystem/v2-0002",
        "HL70003": "http://terminology.hl7.org/CodeSystem/v2-0003",
        "HL70004": "http://terminology.hl7.org/CodeSystem/v2-0004",
        "HL70076": "http://terminology.hl7.org/CodeSystem/v2-0076",
    }
    return mapping.get(system.upper(), f"urn:oid:{system}" if system else "")


def build_bundle(resources: List[Dict[str, Any]], bundle_type: str = "collection") -> Dict[str, Any]:
    """Wrap FHIR resources into a FHIR Bundle."""
    entries = []
    for resource in resources:
        resource_type = resource.get("resourceType", "Resource")
        resource_id = resource.get("id", make_id())
        entries.append({
            "fullUrl": f"urn:uuid:{resource_id}",
            "resource": resource,
        })

    return {
        "resourceType": "Bundle",
        "id": make_id(),
        "type": bundle_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entry": entries,
    }


class BaseConverter:
    """Base class for all HL7 → FHIR converters."""

    def convert(self, parsed_msg) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Convert a ParsedHL7Message into a list of FHIR resource dicts.

        Returns:
            (resources, warnings)
        """
        raise NotImplementedError
