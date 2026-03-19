"""
LLM-powered HL7 <-> FHIR converter using Groq API (Llama 3.3 70B).

Sends the raw message to Groq with a structured prompt and parses
the response back into the same ConversionResult format used by the
manual converters — so all existing UI tabs (JSON, XML, Mappings,
PDF) work without any changes.
"""
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Groq client (lazy init so server starts even without the key) ──
_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError(
                "groq package not installed. Run: pip install groq"
            )
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set in environment / .env file.")
        _client = Groq(api_key=api_key)
    return _client


# ─────────────────────────────────────────────────────────────────────
# HL7 → FHIR prompts (split into 2 calls to handle large messages)
# ─────────────────────────────────────────────────────────────────────

# Step 1: Get FHIR Bundle only (compact, no field_mappings)
_HL7_DEMOGRAPHICS_SYSTEM = """You are an HL7 to FHIR R4 converter. Extract ONLY demographic resources.

Return a compact JSON array of FHIR resources (no markdown, no extra text):
[{"resourceType":"Patient","id":"..."},{"resourceType":"Encounter","id":"..."},{"resourceType":"Organization","id":"..."}]

Create these resources from the message:
- PID -> Patient (id, identifier, name, birthDate, gender, address, telecom, communication, maritalStatus)
- PV1 -> Encounter (id, status, class, period, location, participant)
- MSH-4 -> Organization (id, name)
- PV1-7/8/9 -> Practitioner resources (id, identifier with NPI, name)
- NK1 -> RelatedPerson (id, name, relationship, address, telecom)
- GT1 -> RelatedPerson (guarantor)
- SFT -> extension on Organization

Rules: CX identifiers: value^^^authority^typeCode. XPN names: family^given^middle^suffix^prefix.
Dates YYYYMMDD->YYYY-MM-DD. Gender M=male F=female. Compact JSON no indentation.
"""

_HL7_CLINICAL_SYSTEM = """You are an HL7 to FHIR R4 converter. Extract ONLY clinical resources.

Return a compact JSON array of FHIR resources (no markdown, no extra text):
[{"resourceType":"DiagnosticReport","id":"..."},{"resourceType":"Observation","id":"..."},...]

Create these resources:
- ORC -> ServiceRequest (id, identifier, status, code, authoredOn, requester)
- Each OBR group -> ONE DiagnosticReport (id, status, code, effectiveDateTime, identifier)
  + ONE Observation per OBX under that OBR (id, status, code, value[x], unit, referenceRange, interpretation)
  + NTE after OBR -> note on DiagnosticReport
- RXA+RXR -> Immunization (id, vaccineCode, occurrenceDateTime, doseQuantity, route, site, performer)

OBX value types: NM->valueQuantity, CWE/CE->valueCodeableConcept, ST/TX->valueString, ED->valueAttachment.
OBX-8 interpretation: H=high L=low N=normal A=abnormal.
Dates YYYYMMDD->YYYY-MM-DD, YYYYMMDDHHMMSS->YYYY-MM-DDTHH:MM:SS. Compact JSON no indentation.
"""

_HL7_ADMIN_SYSTEM = """You are an HL7 to FHIR R4 converter. Extract ONLY admin/coverage resources.

Return a compact JSON array of FHIR resources (no markdown, no extra text):
[{"resourceType":"AllergyIntolerance","id":"..."},{"resourceType":"Condition","id":"..."},...]

Create these resources:
- AL1 -> AllergyIntolerance (id, code from AL1-3, criticality from AL1-4, onsetDateTime from AL1-6)
- DG1 -> Condition (id, code with ICD system, verificationStatus from DG1-6)
- IN1 -> Coverage (id, identifier plan, payor name, subscriberId, period)
- Z-segments -> Parameters resource with one parameter per non-empty Z-segment field

Compact JSON no indentation. If none of these segments exist return empty array [].
"""

# Step 2: Get field mappings only (given the HL7 message and resource IDs)
_HL7_TO_FHIR_MAPPINGS_SYSTEM = """You are an HL7 to FHIR field mapping expert.
Given an HL7 message and the FHIR resource IDs produced from it, return ONLY the field mappings.

Return ONLY a compact JSON array — no markdown, no extra text:
[{"resource_type":"Patient","resource_id":"id123","field_mappings":[{"fhir_field":"identifier","hl7_segment":"PID","hl7_field":"3","hl7_value":"12345^^^HOSP^MR","description":"Patient MRN"}]}]

Rules:
- One entry per resource.
- field_mappings: list each HL7 field -> FHIR field mapping for that resource.
- Include segment name, field number, raw HL7 value, and plain English description.
- Cover all segments: PID, PV1, OBR, OBX, ORC, RXA, AL1, DG1, IN1, NK1, GT1, SFT, MSH, NTE.
- Output COMPACT JSON (no indentation, no trailing commas).
"""

# ─────────────────────────────────────────────────────────────────────
# FHIR → HL7 prompt
# ─────────────────────────────────────────────────────────────────────
_FHIR_TO_HL7_SYSTEM = """You are an expert FHIR R4 to HL7 v2.5 converter.
Convert the given FHIR R4 Bundle into a valid HL7 v2.5 message and produce field mappings.

Return ONLY a single valid JSON object — no markdown fences, no extra text — with this exact structure:

{
  "success": true,
  "direction": "fhir_to_hl7",
  "message_type": "ADT",
  "hl7_output": "MSH|^~\\&|FHIR_CONVERTER|FACILITY|DEST||20240315143022||ADT^A01|MSG001|P|2.5\\rEVN|A01|20240315143022\\rPID|1||12345^^^HOSP^MR||SMITH^JOHN^A||19800515|M\\rPV1|1|I",
  "field_mappings": [
    {
      "resource_type": "Patient",
      "resource_id": "id-from-bundle",
      "field_mappings": [
        {
          "fhir_field": "name[0].family",
          "hl7_segment": "PID",
          "hl7_field": "5",
          "hl7_value": "SMITH^JOHN",
          "description": "Patient family name"
        }
      ]
    }
  ],
  "warnings": [],
  "errors": []
}

Rules for HL7 output:
- Segments separated by \\r (carriage return), NOT newlines.
- MSH: MSH|^~\\&|FHIR_CONVERTER|{facility}|DEST||{datetime}||{type}^{event}|{msgid}|P|2.5
- Detect message type from bundle resources:
    Patient+Encounter -> ADT^A01 (A03 if encounter.status=finished)
    Patient+DiagnosticReport+Observation -> ORU^R01
    Patient+ServiceRequest -> ORM^O01
    Patient+Immunization -> VXU^V04
- Build correct segments for each type.
- PID-3: format identifiers as value^^^authority^typeCode, repeat with ~.
- PID-5: family^given^middle^suffix^prefix.
- Dates: YYYY-MM-DD -> YYYYMMDD, YYYY-MM-DDTHH:MM:SS -> YYYYMMDDHHMMSS.
- Gender: male=M, female=F, other=O, unknown=U.
- field_mappings: document every FHIR field you mapped to an HL7 segment.
- message_type: the HL7 message type string (ADT, ORU, ORM etc).
"""


def _extract_json(text: str) -> dict:
    """Strip markdown fences, repair truncated JSON, and parse."""
    # Remove markdown fences
    text = re.sub(r"^```[a-z]*\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text.strip(), flags=re.MULTILINE)
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to repair truncated JSON by closing open brackets/braces
    repaired = _repair_truncated_json(text)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Last resort: extract first complete {...} block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            repaired2 = _repair_truncated_json(match.group())
            return json.loads(repaired2)
    raise ValueError("No valid JSON found in LLM response")


def _repair_truncated_json(text: str) -> str:
    """
    Attempt to repair JSON truncated mid-stream by closing open
    brackets and braces in reverse order.
    """
    # Track open brackets/braces
    stack = []
    in_string = False
    escape_next = False

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if not in_string:
            if ch in ('{', '['):
                stack.append('}' if ch == '{' else ']')
            elif ch in ('}', ']'):
                if stack and stack[-1] == ch:
                    stack.pop()

    # If we're mid-string, close it
    if in_string:
        text += '"'

    # Remove trailing comma before closing
    text = re.sub(r',\s*$', '', text.rstrip())

    # Close all open brackets in reverse
    text += ''.join(reversed(stack))
    return text


def _normalize_resource_summary(data: dict) -> None:
    """
    Always rebuild resource_summary from actual fhir_json entries.
    This is the most reliable approach — the LLM always puts correct
    data in fhir_json even when resource_summary fields are empty/wrong.

    UI expects:  [{ "resource_type": "Patient", "resource_id": "abc", "description": "Patient resource" }]
    """
    bundle = data.get("fhir_json", {})
    entries = bundle.get("entry", [])

    normalized = []
    for entry in entries:
        res = entry.get("resource", {})
        rt = res.get("resourceType", "Unknown")
        rid = res.get("id", "")

        # Build a meaningful description from key fields
        description = _describe_resource(res, rt)

        if not rid:
            rid = str(uuid.uuid4())

        normalized.append({
            "resource_type": rt,
            "resource_id": rid,
            "description": description,
        })

    # Fallback to raw summary if no fhir_json entries
    if not normalized:
        for item in data.get("resource_summary", []):
            rt = item.get("resource_type", "Unknown")
            rid = item.get("resource_id") or item.get("ids", [None])[0] or f"{rt.lower()}-ai"
            normalized.append({
                "resource_type": rt,
                "resource_id": str(rid),
                "description": item.get("description") or f"{rt} resource",
            })

    data["resource_summary"] = normalized


def _describe_resource(res: dict, rt: str) -> str:
    """Build a short human-readable description from a FHIR resource."""
    if rt == "Patient":
        names = res.get("name", [])
        if names:
            n = names[0]
            family = n.get("family", "")
            given = " ".join(n.get("given", []))
            return f"{given} {family}".strip() or "Patient"
        return "Patient"
    if rt == "Practitioner":
        names = res.get("name", [])
        if names:
            n = names[0]
            family = n.get("family", "")
            given = " ".join(n.get("given", []))
            return f"Dr. {given} {family}".strip() or "Practitioner"
        return "Practitioner"
    if rt == "Encounter":
        status = res.get("status", "")
        cls = res.get("class", {})
        code = cls.get("code", cls.get("display", "")) if isinstance(cls, dict) else ""
        return f"Encounter ({code or status})" if (code or status) else "Encounter"
    if rt == "Organization":
        return res.get("name", "Organization")
    if rt == "DiagnosticReport":
        code = res.get("code", {})
        codings = code.get("coding", [])
        display = codings[0].get("display", "") if codings else ""
        return display or "DiagnosticReport"
    if rt == "Observation":
        code = res.get("code", {})
        codings = code.get("coding", [])
        display = codings[0].get("display", "") if codings else ""
        return display or "Observation"
    if rt == "ServiceRequest":
        code = res.get("code", {})
        codings = code.get("coding", [])
        display = codings[0].get("display", "") if codings else ""
        return display or "ServiceRequest"
    if rt == "Immunization":
        vc = res.get("vaccineCode", {})
        codings = vc.get("coding", [])
        display = codings[0].get("display", "") if codings else ""
        return display or "Immunization"
    return f"{rt} resource"


def _build_xml_from_bundle(bundle: dict) -> str:
    """Produce a minimal FHIR XML representation of the bundle."""
    try:
        import dicttoxml  # type: ignore
        xml_bytes = dicttoxml.dicttoxml(bundle, custom_root="Bundle", attr_type=False)
        return xml_bytes.decode("utf-8")
    except Exception:
        return "<Bundle><note>XML rendering unavailable</note></Bundle>"


def _groq_call(client, system: str, user: str, max_tokens: int = 8192) -> str:
    """Single Groq API call, returns raw text."""
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content
    except Exception as exc:
        msg = str(exc)
        # Surface a clean rate-limit message
        if "rate_limit_exceeded" in msg or "429" in msg:
            if "tokens per day" in msg.lower() or "TPD" in msg:
                raise RuntimeError(
                    "Groq daily token limit reached (100,000 tokens/day on free tier). "
                    "Please try again after midnight UTC when the limit resets, "
                    "or upgrade at https://console.groq.com/settings/billing"
                ) from exc
            if "tokens per minute" in msg.lower() or "TPM" in msg:
                import re
                wait = re.search(r"try again in ([\d.]+[ms]+)", msg)
                wait_str = wait.group(1) if wait else "a minute"
                raise RuntimeError(
                    f"Groq rate limit hit. Please wait {wait_str} and try again."
                ) from exc
        raise


def _parse_resource_array(raw: str) -> list:
    """Parse a JSON array of FHIR resources from LLM response."""
    raw = re.sub(r"^```[a-z]*\s*", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw.strip(), flags=re.MULTILINE)
    raw = raw.strip()
    # Try direct parse
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        pass
    # Try repaired
    try:
        result = json.loads(_repair_truncated_json(raw))
        return result if isinstance(result, list) else []
    except Exception:
        pass
    # Try to find [...] block
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if match:
        try:
            result = json.loads(_repair_truncated_json(match.group()))
            return result if isinstance(result, list) else []
        except Exception:
            pass
    return []


def _extract_msh_info(hl7_message: str) -> dict:
    """Extract version, message_type, message_event directly from MSH segment."""
    for line in hl7_message.replace('\r', '\n').split('\n'):
        if line.startswith('MSH'):
            fields = line.split('|')
            version = fields[11].strip() if len(fields) > 11 else "2.5"
            msg_type_field = fields[8].strip() if len(fields) > 8 else ""
            parts = msg_type_field.split('^')
            msg_type = parts[0].strip() if parts else ""
            msg_event = parts[1].strip() if len(parts) > 1 else ""
            return {"hl7_version": version, "message_type": msg_type, "message_event": msg_event}
    return {"hl7_version": "2.5", "message_type": "", "message_event": ""}


def convert_hl7_to_fhir_via_llm(hl7_message: str) -> dict:
    """
    Four-step conversion to handle large complex messages:
    Step 1 — Demographics (Patient, Encounter, Organization, Practitioner, RelatedPerson)
    Step 2 — Clinical (DiagnosticReport, Observation, ServiceRequest, Immunization)
    Step 3 — Admin (AllergyIntolerance, Condition, Coverage, Z-segments)
    Step 4 — Field Mappings
    All resource arrays are merged into one Bundle.
    """
    client = _get_client()
    all_entries: list = []
    warnings: list = []

    # Extract MSH info directly (no LLM needed)
    msh_info = _extract_msh_info(hl7_message)

    # ── Step 1: Demographics ─────────────────────────────────────────
    try:
        raw1 = _groq_call(client, _HL7_DEMOGRAPHICS_SYSTEM,
                          "Extract demographic FHIR resources from:\n\n" + hl7_message,
                          max_tokens=4096)
        resources1 = _parse_resource_array(raw1)
        all_entries.extend({"resource": r} for r in resources1 if isinstance(r, dict))
    except Exception as exc:
        logger.warning("Step-1 demographics failed: %s", exc)
        warnings.append(f"Demographics extraction partial: {exc}")

    # ── Step 2: Clinical ─────────────────────────────────────────────
    try:
        raw2 = _groq_call(client, _HL7_CLINICAL_SYSTEM,
                          "Extract clinical FHIR resources from:\n\n" + hl7_message,
                          max_tokens=6000)
        resources2 = _parse_resource_array(raw2)
        all_entries.extend({"resource": r} for r in resources2 if isinstance(r, dict))
    except Exception as exc:
        logger.warning("Step-2 clinical failed: %s", exc)
        warnings.append(f"Clinical extraction partial: {exc}")

    # ── Step 3: Admin / Coverage ─────────────────────────────────────
    try:
        raw3 = _groq_call(client, _HL7_ADMIN_SYSTEM,
                          "Extract admin FHIR resources from:\n\n" + hl7_message,
                          max_tokens=3000)
        resources3 = _parse_resource_array(raw3)
        all_entries.extend({"resource": r} for r in resources3 if isinstance(r, dict))
    except Exception as exc:
        logger.warning("Step-3 admin failed (non-fatal): %s", exc)

    if not all_entries:
        return {"success": False, "errors": ["All conversion steps failed"], "warnings": warnings}

    # ── Build final Bundle ────────────────────────────────────────────
    bundle = {"resourceType": "Bundle", "type": "collection", "entry": all_entries}
    data: dict = {
        "success": True,
        "fhir_json": bundle,
        "field_mappings": [],
        **msh_info,
    }

    # ── Step 4: Field Mappings ────────────────────────────────────────
    id_summary = ", ".join(
        f"{e['resource'].get('resourceType')}:{e['resource'].get('id','?')}"
        for e in all_entries if "resource" in e
    )[:800]  # cap length
    try:
        raw4 = _groq_call(client, _HL7_TO_FHIR_MAPPINGS_SYSTEM,
                          f"HL7:\n{hl7_message[:3000]}\n\nResources: {id_summary}\n\nReturn field mappings array.",
                          max_tokens=4096)
        fm = _extract_json(raw4)
        if isinstance(fm, list):
            data["field_mappings"] = fm
        elif isinstance(fm, dict):
            data["field_mappings"] = fm.get("field_mappings", [])
    except Exception as exc:
        logger.warning("Step-4 mappings failed (non-fatal): %s", exc)

    # Normalise flat field_mappings
    fm = data.get("field_mappings", [])
    if fm and isinstance(fm[0], dict) and "fhir_field" in fm[0]:
        data["field_mappings"] = [{"resource_type": "All", "resource_id": "ai",
                                   "field_mappings": fm}]

    # ── Build XML & summary ───────────────────────────────────────────
    data["fhir_xml"] = _build_xml_from_bundle(bundle)
    _normalize_resource_summary(data)

    data["ai_powered"] = True
    data["warnings"] = warnings
    data.setdefault("errors", [])
    return data


def convert_fhir_to_hl7_via_llm(fhir_bundle: dict) -> dict:
    """Send a FHIR bundle to Groq and return a dict matching ConversionResult schema."""
    client = _get_client()

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _FHIR_TO_HL7_SYSTEM},
                {"role": "user", "content": "Convert this FHIR Bundle:\n\n" + json.dumps(fhir_bundle, indent=2)},
            ],
            temperature=0.1,
            max_tokens=8192,
        )
        raw = completion.choices[0].message.content
    except Exception as exc:
        logger.exception("Groq API call failed")
        return {
            "success": False,
            "direction": "fhir_to_hl7",
            "errors": [f"Groq API error: {exc}"],
            "warnings": [],
        }

    try:
        data = _extract_json(raw)
    except Exception as exc:
        logger.error("Failed to parse Groq response as JSON: %s", raw[:500])
        return {
            "success": False,
            "direction": "fhir_to_hl7",
            "errors": [f"LLM returned invalid JSON: {exc}", "Raw (first 500): " + raw[:500]],
            "warnings": [],
        }

    data["ai_powered"] = True
    data.setdefault("direction", "fhir_to_hl7")
    data.setdefault("warnings", [])
    data.setdefault("errors", [])
    return data
