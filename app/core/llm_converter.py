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

# ── Groq client (lazy init) ──
_client = None

# ── Anthropic/Claude client (lazy init) ──
_claude_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError("groq package not installed. Run: pip install groq")
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set in environment / .env file.")
        _client = Groq(api_key=api_key)
    return _client


def _get_claude_client():
    global _claude_client
    if _claude_client is None:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in environment / .env file.")
        _claude_client = anthropic.Anthropic(api_key=api_key)
    return _claude_client


def _claude_call(system: str, user: str, max_tokens: int = 8192) -> str:
    """Single Claude API call, returns raw text."""
    client = _get_claude_client()
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text
    except Exception as exc:
        msg_str = str(exc)
        if "rate_limit" in msg_str.lower() or "429" in msg_str:
            raise RuntimeError(f"Claude rate limit hit. Please wait and try again.") from exc
        if "credit" in msg_str.lower() or "quota" in msg_str.lower():
            raise RuntimeError("Claude API quota exceeded. Check your Anthropic billing.") from exc
        raise


# ─────────────────────────────────────────────────────────────────────
# HL7 → FHIR prompts (split into 2 calls to handle large messages)
# ─────────────────────────────────────────────────────────────────────

# Step 1: Get FHIR Bundle only (compact, no field_mappings)
_HL7_DEMOGRAPHICS_SYSTEM = """You are an HL7 to FHIR R4 converter. Extract ONLY demographic resources.

Return a compact JSON array of FHIR resources (no markdown, no extra text):
[{"resourceType":"Patient","id":"..."},{"resourceType":"Encounter","id":"..."},{"resourceType":"Organization","id":"..."}]

Create these resources from the message:
- PID -> Patient (id, identifier, name, birthDate, gender, address, telecom, communication, maritalStatus)
- PV1 -> Encounter REQUIRED: id, status (default in-progress), class from PV1-2 (I=inpatient O=outpatient E=emergency), location from PV1-3 (point-of-care^room^bed), participant (attending from PV1-7 NPI^family^given), period.start from PV1-44, period.end from PV1-45
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
[{"resourceType":"ServiceRequest","id":"..."},{"resourceType":"DiagnosticReport","id":"..."},...]

CRITICAL — map ALL of these when present:
- ORC -> ServiceRequest REQUIRED fields:
    id (unique), status (from ORC-1: NW=active, CA/DC=revoked, HD=on-hold),
    intent (from ORC-1: NW=order),
    identifier: [{type:{coding:[{code:"PLAC"}]},value:ORC-2}, {type:{coding:[{code:"FILL"}]},value:ORC-3}, {type:{coding:[{code:"PGN"}]},value:ORC-4}],
    authoredOn (ORC-9 datetime), requester (ORC-12 NPI as Practitioner ref)
- OBR (with ORC) -> add to the same ServiceRequest: code from OBR-4 (LOINC), priority from OBR-5
- OBR (ORU message) -> ONE DiagnosticReport per OBR group + ONE Observation per OBX
- NTE after OBR -> note on DiagnosticReport
- RXA+RXR -> Immunization (vaccineCode, occurrenceDateTime, doseQuantity, route, site, performer)

IMPORTANT: For ORM messages (order messages with ORC+OBR but NO OBX), produce a ServiceRequest only — do NOT produce DiagnosticReport.
For ORU messages (result messages with OBX), produce DiagnosticReport + Observation resources.

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
# Raw EHR → FHIR prompts (2-step: resources then mappings)
# ─────────────────────────────────────────────────────────────────────
_EHR_TO_FHIR_SYSTEM = """You are an expert EHR data to FHIR R4 converter.
The user will provide raw EHR data in any format: pipe-delimited records, key-value pairs, structured text, CSV, or clinical notes.

For pipe-delimited format, the column order per record type is:
PATIENT    | MRN | FirstName | LastName | DOB | Gender | Language | Phone | Address | City | State | Zip
ENCOUNTER  | VisitID | VisitType | Location | ProviderID | ProviderName | StartTime | EndTime
ALLERGY    | SeqNum | Substance | Reaction | OnsetDate
DIAGNOSIS  | SeqNum | ICD Code | Description
LAB_ORDER  | OrderID | PanelName | OrderedTime
LAB_RESULT | SeqNum | LOINCCode | TestName | Value | Unit | ReferenceRange | Flag
VITAL      | Type(BP/HR/WEIGHT/TEMP/SPO2) | Value | Unit
IMMUNIZATION | VaccineName | Date | Dose | Unit | Route | Site
INSURANCE  | ProviderName | Plan | Group | MemberID

Your job is to parse ALL clinical information and return a FHIR R4 Bundle.

Return a compact JSON array of FHIR R4 resources (no markdown, no extra text):
[{"resourceType":"Patient","id":"..."},{"resourceType":"Encounter","id":"..."},...]

Create resources from EVERY piece of data found:
- Patient demographics (name, DOB, gender, MRN, address, phone, language, race/ethnicity)
- Encounter (visit type, location, provider, start/end times, visit ID)
- Practitioner (provider name, ID, NPI)
- Organization (facility/clinic name)
- AllergyIntolerance (substance, reaction, severity, onset date)
- Condition (ICD codes, descriptions, clinical status)
- Observation (lab results, vitals — each as separate Observation with LOINC code, value, unit, reference range, interpretation)
- DiagnosticReport (if lab panel ordered — reference all related Observations)
- ServiceRequest (lab orders with order ID, panel name, ordered time)
- Immunization (vaccine name, CVX code, date, dose, route, site)
- Coverage (insurance provider, plan, group, member ID, period)
- RelatedPerson (next of kin, emergency contacts)

Rules:
- Use LOINC codes for lab tests and vitals where possible
- Dates: YYYY-MM-DD format, DateTimes: YYYY-MM-DDTHH:MM:SS
- Gender: male/female/other/unknown
- Interpretation: N=normal, H=high, L=low, A=abnormal
- Assign meaningful IDs derived from MRN/visit IDs in the data
- Compact JSON, no indentation
"""

_EHR_TO_FHIR_MAPPINGS_SYSTEM = """You are an EHR to FHIR field mapping expert.
Given raw EHR data and the FHIR resource IDs produced, return field mappings showing how each EHR field maps to FHIR.

Return ONLY a compact JSON array — no markdown, no extra text:
[{"resource_type":"Patient","resource_id":"id123","field_mappings":[{"fhir_field":"name[0].family","hl7_segment":"EHR","hl7_field":"Last Name","hl7_value":"Rivera","description":"Patient family name"}]}]

- One entry per resource.
- Cover every EHR field mapped to a FHIR path.
- hl7_segment should be the EHR section name (PATIENT, ENCOUNTER, LAB RESULTS, etc.)
- hl7_field is the field label from the raw data.
- Compact JSON, no indentation.
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
    if rt == "Coverage":
        payors = res.get("payor", [{}])
        payor_name = payors[0].get("display", "") if payors else ""
        plan_val  = next((c.get("value","") for c in res.get("class",[]) if c.get("type",{}).get("coding",[{}])[0].get("code") == "plan"), "")
        group_val = next((c.get("value","") for c in res.get("class",[]) if c.get("type",{}).get("coding",[{}])[0].get("code") == "group"), "")
        member_id = res.get("subscriberId", "")
        parts = [payor_name]
        if plan_val:  parts.append(f"Plan: {plan_val}")
        if group_val: parts.append(f"Group: {group_val}")
        if member_id: parts.append(f"MBR: {member_id}")
        return " | ".join(p for p in parts if p) or "Coverage"
    return f"{rt} resource"


def _build_xml_from_bundle(bundle: dict) -> str:
    """Produce a minimal FHIR XML representation of the bundle."""
    try:
        import dicttoxml  # type: ignore
        xml_bytes = dicttoxml.dicttoxml(bundle, custom_root="Bundle", attr_type=False)
        return xml_bytes.decode("utf-8")
    except Exception:
        return "<Bundle><note>XML rendering unavailable</note></Bundle>"


def _llm_call(system: str, user: str, max_tokens: int = 8192, provider: str = "groq") -> str:
    """Unified LLM call — routes to Groq or Claude based on provider."""
    if provider == "claude":
        return _claude_call(system, user, max_tokens)
    client = _get_client()
    return _groq_call(client, system, user, max_tokens)


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


def _unwrap_to_list(obj) -> list:
    """If obj is a Bundle dict, unwrap entries; otherwise return as-is."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        # Bundle with entry array
        entries = obj.get("entry", [])
        if entries:
            return [e.get("resource", e) if isinstance(e, dict) else e for e in entries]
        # Single resource wrapped in dict
        if obj.get("resourceType"):
            return [obj]
    return []


def _parse_resource_array(raw: str) -> list:
    """Parse a JSON array of FHIR resources from LLM response."""
    try:
        from json_repair import repair_json
        _has_json_repair = True
    except ImportError:
        _has_json_repair = False

    # Strip markdown code fences
    raw = re.sub(r"^```[a-z]*\s*", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw.strip(), flags=re.MULTILINE)
    raw = raw.strip()

    # Try direct parse first (fastest path)
    try:
        result = json.loads(raw)
        unwrapped = _unwrap_to_list(result)
        if unwrapped:
            return unwrapped
    except json.JSONDecodeError:
        pass

    # Try json_repair (handles mid-array corruption from LLM output)
    if _has_json_repair:
        try:
            result = json.loads(repair_json(raw))
            unwrapped = _unwrap_to_list(result)
            if unwrapped:
                return unwrapped
        except Exception:
            pass

    # Fallback: custom truncation repair
    for candidate in (raw, re.search(r'\[.*\]', raw, re.DOTALL),
                      re.search(r'\{.*\}', raw, re.DOTALL)):
        text = candidate if isinstance(candidate, str) else (candidate.group() if candidate else None)
        if not text:
            continue
        try:
            result = json.loads(_repair_truncated_json(text))
            unwrapped = _unwrap_to_list(result)
            if unwrapped:
                return unwrapped
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


def convert_hl7_to_fhir_via_llm(hl7_message: str, provider: str = "groq") -> dict:
    """
    Four-step conversion to handle large complex messages.
    provider: "groq" (default) or "claude"
    """
    all_entries: list = []
    warnings: list = []

    # Extract MSH info directly (no LLM needed)
    msh_info = _extract_msh_info(hl7_message)

    # ── Step 1: Demographics ─────────────────────────────────────────
    try:
        raw1 = _llm_call(_HL7_DEMOGRAPHICS_SYSTEM,
                         "Extract demographic FHIR resources from:\n\n" + hl7_message,
                         max_tokens=4096, provider=provider)
        resources1 = _parse_resource_array(raw1)
        all_entries.extend({"resource": r} for r in resources1 if isinstance(r, dict))
    except Exception as exc:
        logger.warning("Step-1 demographics failed: %s", exc)
        warnings.append(f"Demographics extraction partial: {exc}")

    # ── Step 2: Clinical ─────────────────────────────────────────────
    try:
        raw2 = _llm_call(_HL7_CLINICAL_SYSTEM,
                         "Extract clinical FHIR resources from:\n\n" + hl7_message,
                         max_tokens=6000, provider=provider)
        resources2 = _parse_resource_array(raw2)
        all_entries.extend({"resource": r} for r in resources2 if isinstance(r, dict))
    except Exception as exc:
        logger.warning("Step-2 clinical failed: %s", exc)
        warnings.append(f"Clinical extraction partial: {exc}")

    # ── Step 3: Admin / Coverage ─────────────────────────────────────
    try:
        raw3 = _llm_call(_HL7_ADMIN_SYSTEM,
                         "Extract admin FHIR resources from:\n\n" + hl7_message,
                         max_tokens=3000, provider=provider)
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
    )[:800]
    try:
        raw4 = _llm_call(_HL7_TO_FHIR_MAPPINGS_SYSTEM,
                         f"HL7:\n{hl7_message[:3000]}\n\nResources: {id_summary}\n\nReturn field mappings array.",
                         max_tokens=4096, provider=provider)
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


def convert_fhir_to_hl7_via_llm(fhir_bundle: dict, provider: str = "groq") -> dict:
    """Convert FHIR bundle to HL7 via LLM. provider: 'groq' or 'claude'."""
    try:
        raw = _llm_call(
            _FHIR_TO_HL7_SYSTEM,
            "Convert this FHIR Bundle:\n\n" + json.dumps(fhir_bundle, indent=2),
            max_tokens=8192,
            provider=provider,
        )
    except Exception as exc:
        logger.exception("LLM API call failed")
        return {
            "success": False,
            "direction": "fhir_to_hl7",
            "errors": [f"LLM API error: {exc}"],
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


def convert_ehr_to_fhir_via_llm(ehr_data: str, provider: str = "groq") -> dict:
    """
    Convert raw EHR data to FHIR R4 Bundle.
    provider: "groq" (default) or "claude"
    """
    warnings: list = []

    # ── Step 1: All FHIR resources from EHR data ─────────────────────
    try:
        raw1 = _llm_call(
            _EHR_TO_FHIR_SYSTEM,
            "Convert this raw EHR data to FHIR R4 resources:\n\n" + ehr_data,
            max_tokens=6000,
            provider=provider,
        )
        resources = _parse_resource_array(raw1)
    except Exception as exc:
        logger.error("EHR→FHIR step-1 failed: %s", exc)
        return {"success": False, "errors": [str(exc)], "warnings": []}

    if not resources:
        return {"success": False, "errors": ["No FHIR resources could be extracted from the EHR data."], "warnings": warnings}

    all_entries = [{"resource": r} for r in resources if isinstance(r, dict)]

    # Detect message type from resource types present
    rt_set = {e["resource"].get("resourceType", "") for e in all_entries}
    if "DiagnosticReport" in rt_set or "Observation" in rt_set:
        msg_type = "ORU"
    elif "ServiceRequest" in rt_set:
        msg_type = "ORM"
    else:
        msg_type = "ADT"

    bundle = {"resourceType": "Bundle", "type": "collection", "entry": all_entries}
    data: dict = {
        "success": True,
        "hl7_version": "N/A",
        "message_type": msg_type,
        "message_event": "EHR_RAW",
        "fhir_json": bundle,
        "field_mappings": [],
        "direction": "ehr_to_fhir",
    }

    # ── Step 2: Field mappings ────────────────────────────────────────
    id_summary = ", ".join(
        f"{e['resource'].get('resourceType')}:{e['resource'].get('id','?')}"
        for e in all_entries if "resource" in e
    )[:600]
    try:
        raw2 = _llm_call(
            _EHR_TO_FHIR_MAPPINGS_SYSTEM,
            f"EHR Data:\n{ehr_data[:2500]}\n\nFHIR Resources: {id_summary}\n\nReturn field mappings.",
            max_tokens=4096,
            provider=provider,
        )
        fm = _extract_json(raw2)
        if isinstance(fm, list):
            data["field_mappings"] = fm
        elif isinstance(fm, dict):
            data["field_mappings"] = fm.get("field_mappings", [])
    except Exception as exc:
        logger.warning("EHR→FHIR step-2 mappings failed (non-fatal): %s", exc)
        warnings.append(f"Field mappings partial: {exc}")

    # Normalise flat field_mappings
    fm = data.get("field_mappings", [])
    if fm and isinstance(fm[0], dict) and "fhir_field" in fm[0]:
        data["field_mappings"] = [{"resource_type": "All", "resource_id": "ehr-ai", "field_mappings": fm}]

    data["fhir_xml"] = _build_xml_from_bundle(bundle)
    _normalize_resource_summary(data)
    data["ai_powered"] = True
    data["warnings"] = warnings
    data.setdefault("errors", [])
    return data
