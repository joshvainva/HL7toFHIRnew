"""
Rendering layer — converts FHIR bundle dicts to JSON, XML, and human-readable text.
"""
import json
from typing import Any, Dict, List
from xml.etree import ElementTree as ET
from xml.dom import minidom

from app.models.schemas import ResourceSummary


def to_fhir_json(bundle: Dict[str, Any]) -> str:
    """Serialize FHIR bundle to formatted JSON string."""
    return json.dumps(bundle, indent=2, default=str)


def _dict_to_xml_element(data: Any, parent: ET.Element, tag: str = "value") -> None:
    """Recursively convert a Python dict/list/scalar to XML elements."""
    if isinstance(data, dict):
        el = ET.SubElement(parent, tag)
        for key, val in data.items():
            # XML tags can't start with digit or contain special chars
            safe_key = key.lstrip("_").replace(" ", "_").replace("@", "attr_")
            if not safe_key or safe_key[0].isdigit():
                safe_key = f"field_{safe_key}"
            _dict_to_xml_element(val, el, safe_key)
    elif isinstance(data, list):
        el = ET.SubElement(parent, tag)
        for item in data:
            _dict_to_xml_element(item, el, "item")
    else:
        el = ET.SubElement(parent, tag)
        el.text = str(data) if data is not None else ""


def to_fhir_xml(bundle: Dict[str, Any]) -> str:
    """
    Serialize FHIR bundle to FHIR-style XML.

    Note: Full FHIR XML uses a specific element-per-field structure.
    This produces a clean, parseable XML representation of the bundle.
    """
    root = ET.Element("Bundle", xmlns="http://hl7.org/fhir")

    # Bundle-level fields
    def add_value(parent: ET.Element, tag: str, value: Any) -> None:
        if value is None:
            return
        _dict_to_xml_element(value, parent, tag)

    # id
    if bundle.get("id"):
        id_el = ET.SubElement(root, "id")
        id_el.set("value", str(bundle["id"]))

    # type
    if bundle.get("type"):
        type_el = ET.SubElement(root, "type")
        type_el.set("value", str(bundle["type"]))

    # timestamp
    if bundle.get("timestamp"):
        ts_el = ET.SubElement(root, "timestamp")
        ts_el.set("value", str(bundle["timestamp"]))

    # entries
    for entry in bundle.get("entry", []):
        entry_el = ET.SubElement(root, "entry")

        fullurl = entry.get("fullUrl", "")
        if fullurl:
            fu_el = ET.SubElement(entry_el, "fullUrl")
            fu_el.set("value", fullurl)

        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType", "Resource")
        res_el = ET.SubElement(entry_el, "resource")
        typed_el = ET.SubElement(res_el, resource_type)

        for key, val in resource.items():
            if key == "resourceType":
                continue
            if key.startswith("_"):
                continue
            _dict_to_xml_element(val, typed_el, key)

    # Pretty-print
    raw_xml = ET.tostring(root, encoding="unicode")
    try:
        dom = minidom.parseString(raw_xml)
        return dom.toprettyxml(indent="  ", encoding=None)
    except Exception:
        return raw_xml


def _resource_description(resource: Dict[str, Any]) -> str:
    """Generate a short human-readable description for a FHIR resource."""
    rt = resource.get("resourceType", "Resource")

    if rt == "Patient":
        names = resource.get("name", [])
        if names:
            n = names[0]
            family = n.get("family", "")
            given = " ".join(n.get("given", []))
            full = f"{given} {family}".strip()
        else:
            full = "Unknown"
        dob = resource.get("birthDate", "")
        gender = resource.get("gender", "")
        return f"Patient: {full} | DOB: {dob} | Gender: {gender}"

    if rt == "Encounter":
        status = resource.get("status", "")
        enc_class = resource.get("class", {})
        class_display = enc_class.get("display", enc_class.get("code", ""))
        period = resource.get("period", {})
        start = period.get("start", "")
        return f"Encounter: {class_display} | Status: {status} | Start: {start}"

    if rt == "Practitioner":
        names = resource.get("name", [])
        if names:
            n = names[0]
            family = n.get("family", "")
            given = " ".join(n.get("given", []))
            full = f"{given} {family}".strip()
        else:
            full = "Unknown"
        return f"Practitioner: {full}"

    if rt == "Organization":
        name = resource.get("name", "Unknown")
        return f"Organization: {name}"

    if rt == "Observation":
        code = resource.get("code", {})
        code_text = code.get("text", "")
        if not code_text:
            codings = code.get("coding", [])
            code_text = codings[0].get("display", codings[0].get("code", "")) if codings else ""
        status = resource.get("status", "")
        value_qty = resource.get("valueQuantity", {})
        value_str = resource.get("valueString", "")
        if value_qty:
            val_display = f"{value_qty.get('value', '')} {value_qty.get('unit', '')}".strip()
        else:
            val_display = value_str
        return f"Observation: {code_text} = {val_display} | Status: {status}"

    if rt == "DiagnosticReport":
        code = resource.get("code", {})
        code_text = code.get("text", "")
        if not code_text:
            codings = code.get("coding", [])
            code_text = codings[0].get("display", codings[0].get("code", "")) if codings else ""
        status = resource.get("status", "")
        return f"DiagnosticReport: {code_text} | Status: {status}"

    if rt == "ServiceRequest":
        code = resource.get("code", {})
        code_text = code.get("text", "")
        if not code_text:
            codings = code.get("coding", [])
            code_text = codings[0].get("display", codings[0].get("code", "")) if codings else ""
        status = resource.get("status", "")
        intent = resource.get("intent", "")
        return f"ServiceRequest: {code_text} | Status: {status} | Intent: {intent}"

    return f"{rt}: {resource.get('id', 'no-id')}"


def to_human_readable(
    bundle: Dict[str, Any],
    hl7_version: str,
    message_type: str,
    message_event: str,
    warnings: List[str],
) -> str:
    """Generate a plain-text human-readable conversion report."""
    lines = [
        "=" * 70,
        "  HL7 → FHIR CONVERSION REPORT",
        "=" * 70,
        "",
        f"  HL7 Version   : {hl7_version}",
        f"  Message Type  : {message_type} (event: {message_event})",
        f"  Bundle ID     : {bundle.get('id', 'N/A')}",
        f"  Timestamp     : {bundle.get('timestamp', 'N/A')}",
        "",
    ]

    entries = bundle.get("entry", [])
    if not entries:
        lines.append("  No FHIR resources were generated.")
    else:
        lines.append(f"  Resources Generated ({len(entries)} total):")
        lines.append("  " + "-" * 66)

        # Group by resource type
        by_type: Dict[str, List] = {}
        for entry in entries:
            resource = entry.get("resource", {})
            rt = resource.get("resourceType", "Unknown")
            by_type.setdefault(rt, []).append(resource)

        for rt, resources in by_type.items():
            lines.append(f"\n  [{rt}]  ({len(resources)} resource{'s' if len(resources) > 1 else ''})")
            for r in resources:
                lines.append(f"    • {_resource_description(r)}")
                lines.append(f"      ID: {r.get('id', 'N/A')}")

    if warnings:
        lines.append("")
        lines.append("  Warnings:")
        lines.append("  " + "-" * 66)
        for w in warnings:
            lines.append(f"  ⚠  {w}")

    lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)


def build_resource_summary(bundle: Dict[str, Any]) -> List[ResourceSummary]:
    """Build a summary list of all FHIR resources in the bundle."""
    summaries = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rt = resource.get("resourceType", "Unknown")
        rid = resource.get("id", "N/A")
        desc = _resource_description(resource)
        summaries.append(ResourceSummary(resource_type=rt, resource_id=rid, description=desc))
    return summaries
