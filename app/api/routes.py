"""
API routes for the HL7 → FHIR converter.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import cast, String

# Load .env so GROQ_API_KEY is available without python-dotenv dependency
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app.core.parser import HL7Parser, HL7ParseError
from app.core.validator import HL7Validator
from app.core.mapper import FHIRMapper
from app.core.fhir_mapper import FHIRtoHL7Mapper
from app.core.renderer import (
    to_fhir_json,
    to_fhir_xml,
    to_human_readable,
    build_resource_summary,
)
from app.core.history import history, HistoryItem
from app.file_handlers.registry import get_handler
from app.models.schemas import ConversionResult, ErrorResponse, FHIRConversionRequest, ResourceSummary
from app.db.session import SessionLocal
from app.models.db_models import FhirResource, ConversionLog
from app.core.dq_engine import DQEngine
from app.core.upsert_engine import SmartUpsertEngine

logger = logging.getLogger(__name__)

router = APIRouter()

def _post_process_bundle(
    bundle: dict,
    raw_content: str = "",
    message_type: str = None,
    conversion_source: str = None,
    warnings: list = None,
    field_mappings: list = None
) -> tuple:
    if not bundle:
        return [], None
    db = SessionLocal()
    try:
        # --- DQ validation ---
        dq = DQEngine(db)
        issues = dq.validate_bundle(bundle)
        dq.record_issues(issues, raw_content)

        # --- Smart upsert (cumulative FHIR resource store) ---
        upsert = SmartUpsertEngine(db)
        summary = upsert.upsert_bundle(bundle, message_type=message_type, conversion_source=conversion_source)

        # --- ConversionLog: intelligent splitting ---
        # We split the bundle so each audit entry only contains resources related to that specific patient.
        logs_to_create = []
        patient_resources = {} # mrn -> list of resource-entries
        
        # 1. Identify all patients first
        all_patients = []
        for entry in bundle.get("entry", []):
            res = entry.get("resource", {})
            if res.get("resourceType") == "Patient":
                mrn = None
                for ident in res.get("identifier", []):
                    if ident.get("value"): mrn = ident["value"]; break
                if not mrn: mrn = res.get("id")
                
                name = None
                names = res.get("name", [])
                if names:
                    n = names[0]
                    gn = " ".join(n.get("given", []))
                    fn = n.get("family", "")
                    name = f"{gn} {fn}".strip()
                
                patient_info = {"mrn": mrn or "UNKNOWN", "name": name, "res_id": res.get("id")}
                all_patients.append(patient_info)
                patient_resources[patient_info["mrn"]] = [entry]

        if not all_patients:
            # Fallback for non-patient bundles (unlikely in EHR/HL7 context)
            logs_to_create.append({"mrn": "UNKNOWN", "name": None, "bundle": bundle})
        else:
            # 2. Assign other resources to their respective patients based on references
            # Build maps for intelligent partitioning
            enc_to_pat = {}
            prac_to_pats = {} # PractitionerID -> set of PatientMRNs
            
            # First pass: Build Encounter and Practitioner relationship maps
            for entry in bundle.get("entry", []):
                res = entry.get("resource", {})
                rt = res.get("resourceType")
                if rt == "Encounter":
                    pat_mrn = None
                    ref = res.get("subject", {}).get("reference", "")
                    if ref.startswith("Patient/"):
                        p_id = ref.split("/")[-1]
                        # Find the MRN for this patient ID
                        for p in all_patients:
                            if p["res_id"] == p_id or p["mrn"] == p_id:
                                pat_mrn = p["mrn"]
                                break
                    
                    if pat_mrn:
                        enc_to_pat[res.get("id")] = pat_mrn
                        # Map practitioners from this encounter to this patient
                        for part in res.get("participant", []):
                            indiv_ref = part.get("individual", {}).get("reference", "")
                            if indiv_ref.startswith("Practitioner/"):
                                prac_id = indiv_ref.split("/")[-1]
                                if prac_id not in prac_to_pats:
                                    prac_to_pats[prac_id] = set()
                                prac_to_pats[prac_id].add(pat_mrn)

            # Second pass: Partition all resources into patient buckets
            for entry in bundle.get("entry", []):
                res = entry.get("resource", {})
                rt = res.get("resourceType")
                if rt == "Patient": continue # already handled
                
                # Identify which patients this resource belongs to
                target_mrns = []
                
                # Check direct subject/patient reference
                ref = (res.get("subject") or res.get("patient") or {}).get("reference", "")
                if ref.startswith("Patient/"):
                    p_id = ref.split("/")[-1]
                    # Find MRN
                    for p in all_patients:
                        if p["res_id"] == p_id or p["mrn"] == p_id:
                            target_mrns.append(p["mrn"])
                            break
                elif ref.startswith("Encounter/"):
                    enc_id = ref.split("/")[-1]
                    if enc_id in enc_to_pat:
                        target_mrns.append(enc_to_pat[enc_id])
                elif rt == "Practitioner":
                    # Use practitioner map
                    prac_id = res.get("id")
                    if prac_id in prac_to_pats:
                        target_mrns.extend(list(prac_to_pats[prac_id]))
                elif rt == "Organization":
                    # Organizations (like sending facility) are often shared across the whole batch
                    for p in all_patients:
                        target_mrns.append(p["mrn"])

                # Add to buckets
                if target_mrns:
                    for mrn in target_mrns:
                        if mrn in patient_resources:
                            patient_resources[mrn].append(entry)
                else:
                    # If orphan and no direct link, attach to the first patient found as fallback
                    # This handles edge cases where resources are not correctly linked in the source
                    if all_patients:
                        patient_resources[all_patients[0]["mrn"]].append(entry)

            for p in all_patients:
                logs_to_create.append({
                    "mrn": p["mrn"],
                    "name": p["name"],
                    "bundle": {
                        "resourceType": "Bundle",
                        "type": "collection",
                        "entry": patient_resources.get(p["mrn"], [])
                    }
                })

        # 3. Save logs
        # Ensure all nested objects are plain dicts for JSONB serialization
        serializable_mappings = []
        if field_mappings:
            for m in field_mappings:
                if hasattr(m, "dict"):
                    serializable_mappings.append(m.dict())
                else:
                    serializable_mappings.append(m)

        serializable_dq = []
        if issues:
            for i in issues:
                if isinstance(i, dict):
                    # Strip SQLAlchemy state if present
                    if "_sa_instance_state" in i:
                        i = {k: v for k, v in i.items() if k != "_sa_instance_state"}
                    serializable_dq.append(i)
                elif hasattr(i, "__dict__"):
                    d = {k: v for k, v in vars(i).items() if k != "_sa_instance_state"}
                    serializable_dq.append(d)
                else:
                    serializable_dq.append(str(i))

        for log_data in logs_to_create:
            log_entry = ConversionLog(
                id=str(uuid.uuid4()),
                patient_mrn=log_data["mrn"],
                patient_name=log_data["name"],
                message_type=message_type,
                conversion_source=conversion_source or "Unknown",
                fhir_bundle=log_data["bundle"],
                field_mappings=serializable_mappings,
                raw_input=raw_content[:16000] if raw_content else None,
                warnings=warnings or [],
                dq_issues=serializable_dq,
                success="success",
            )
            db.add(log_entry)
        
        db.commit()
        return issues, summary
    except Exception as e:
        logger.error(f"Post-process error: {e}")
        return [], None
    finally:
        db.close()

# Shared service instances (stateless — safe to reuse)
_parser = HL7Parser()
_validator = HL7Validator()
_mapper = FHIRMapper()
_fhir_mapper = FHIRtoHL7Mapper()


def _process_hl7_text(raw_message: str, input_type: str = "text", input_name: Optional[str] = None) -> ConversionResult:
    """Core conversion pipeline: parse → validate → map → render."""
    # 1. Parse
    try:
        parsed = _parser.parse(raw_message)
    except HL7ParseError as exc:
        # Save failed parse to history
        result = ConversionResult(
            success=False,
            hl7_version=None,
            message_type=None,
            message_event=None,
            errors=[str(exc)],
            warnings=[],
        )
        history_item = HistoryItem(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            hl7_version=None,
            message_type=None,
            message_event=None,
            input_type=input_type,
            input_name=input_name,
            success=False,
            hl7_content=raw_message,
            errors=[str(exc)],
            warnings=[],
        )
        history.add_conversion(history_item)
        return result

    # 2. Validate
    validation = _validator.validate(parsed)
    if not validation.valid:
        result = ConversionResult(
            success=False,
            hl7_version=parsed.version,
            message_type=parsed.message_type,
            message_event=parsed.message_event,
            errors=validation.errors,
            warnings=validation.warnings,
        )
        # Save failed conversion to history
        history_item = HistoryItem(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            hl7_version=parsed.version,
            message_type=parsed.message_type,
            message_event=parsed.message_event,
            input_type=input_type,
            input_name=input_name,
            success=False,
            hl7_content=raw_message,
            errors=validation.errors,
            warnings=validation.warnings,
        )
        history.add_conversion(history_item)
        return result

    # 3. Map to FHIR
    bundle, mapping_warnings, field_mappings = _mapper.map(parsed)

    # 4. Render outputs
    fhir_json_str = to_fhir_json(bundle)
    fhir_xml_str = to_fhir_xml(bundle)
    human_str = to_human_readable(
        bundle,
        parsed.version,
        parsed.message_type,
        parsed.message_event,
        validation.warnings + mapping_warnings,
    )

    # 5. Build summary
    summaries = build_resource_summary(bundle)

    dq_issues, upsert_summary = _post_process_bundle(
        bundle,
        raw_message,
        message_type=f"{parsed.message_type}{'~'+parsed.message_event if parsed.message_event else ''}",
        conversion_source="HL7→FHIR",
        warnings=validation.warnings + mapping_warnings,
        field_mappings=field_mappings
    )

    result = ConversionResult(
        success=True,
        hl7_version=parsed.version,
        message_type=parsed.message_type,
        message_event=parsed.message_event,
        fhir_json=bundle,
        fhir_xml=fhir_xml_str,
        human_readable=human_str,
        resource_summary=summaries,
        field_mappings=field_mappings,
        warnings=validation.warnings + mapping_warnings,
        dq_issues=dq_issues,
        upsert_summary=upsert_summary,
    )

    # Save successful conversion to history
    history_item = HistoryItem(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        hl7_version=parsed.version,
        message_type=parsed.message_type,
        message_event=parsed.message_event,
        input_type=input_type,
        input_name=input_name,
        success=True,
        hl7_content=raw_message,
        fhir_json=bundle,
        fhir_xml=fhir_xml_str,
        human_readable=human_str,
        field_mappings=field_mappings,
        warnings=validation.warnings + mapping_warnings,
    )
    history.add_conversion(history_item)

    return result


@router.post(
    "/convert/text",
    response_model=ConversionResult,
    summary="Convert HL7 text to FHIR",
    description="Accept a raw HL7 message string and return FHIR JSON, XML, and human-readable output.",
)
async def convert_text(payload: dict) -> ConversionResult:
    raw = payload.get("hl7_message", "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'hl7_message' is required and must not be empty.",
        )
    try:
        return _process_hl7_text(raw, input_type="text")
    except HL7ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Unexpected error during text conversion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal conversion error: {exc}",
        )


@router.post(
    "/convert/file",
    summary="Convert HL7 from uploaded file",
    description="Upload .hl7, .txt, .csv, .xlsx, .xls, or .docx file and convert to FHIR.",
)
async def convert_file(file: UploadFile = File(...)):
    # File size limit: 10 MB
    MAX_SIZE = 10 * 1024 * 1024
    data = await file.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds maximum allowed size of 10 MB.",
        )

    filename = file.filename or "upload"
    content_type = file.content_type or ""

    handler = get_handler(filename, content_type)
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{filename}'. "
                "Supported: .hl7, .txt, .csv, .xlsx, .xls, .docx"
            ),
        )

    try:
        messages = handler.extract_messages(data, filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # For batch files: return array of results
    results = []
    for msg_text in messages:
        try:
            result = _process_hl7_text(msg_text, input_type="file", input_name=filename)
        except HL7ParseError as exc:
            result = ConversionResult(
                success=False,
                errors=[str(exc)],
            )
        except Exception as exc:
            result = ConversionResult(
                success=False,
                errors=[f"Conversion failed: {exc}"],
            )
        results.append(result)

    if len(results) == 1:
        return results[0]

    return {"batch": True, "count": len(results), "results": results}


def _process_fhir_bundle(bundle: dict, input_type: str = "text", input_name: Optional[str] = None) -> ConversionResult:
    """Core FHIR→HL7 pipeline: detect type → convert → store history."""
    try:
        hl7_message, msg_type, error = _fhir_mapper.map(bundle)
    except Exception as exc:
        return ConversionResult(
            success=False,
            direction="fhir_to_hl7",
            errors=[str(exc)],
        )

    if error or not hl7_message:
        return ConversionResult(
            success=False,
            direction="fhir_to_hl7",
            message_type=msg_type,
            errors=[error or "Conversion produced no output"],
        )

    result = ConversionResult(
        success=True,
        direction="fhir_to_hl7",
        message_type=msg_type,
        hl7_output=hl7_message,
    )

    history_item = HistoryItem(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        hl7_version="2.5",
        message_type=msg_type,
        message_event=None,
        input_type=input_type,
        input_name=input_name,
        success=True,
        hl7_content="",
        direction="fhir_to_hl7",
        fhir_json=bundle,
        hl7_output=hl7_message,
    )
    history.add_conversion(history_item)

    return result


@router.post(
    "/convert/fhir-to-hl7",
    response_model=ConversionResult,
    summary="Convert FHIR Bundle to HL7",
    description="Accept a FHIR R4 Bundle and return an HL7 v2.x message string.",
)
async def convert_fhir_to_hl7(payload: dict) -> ConversionResult:
    bundle = payload.get("fhir_bundle")
    if not bundle:
        # Allow sending the bundle directly at top level if it has resourceType
        if payload.get("resourceType") == "Bundle":
            bundle = payload
    if not bundle:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'fhir_bundle' is required and must be a FHIR Bundle object.",
        )
    try:
        return _process_fhir_bundle(bundle, input_type="text")
    except Exception as exc:
        logger.exception("Unexpected error during FHIR→HL7 conversion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal conversion error: {exc}",
        )


@router.post(
    "/convert/ai/hl7-to-fhir",
    summary="AI-powered HL7 → FHIR conversion via Gemini",
)
async def ai_convert_hl7_to_fhir(payload: dict):
    from app.core.llm_converter import convert_hl7_to_fhir_via_llm
    raw = payload.get("hl7_message", "").strip()
    provider = payload.get("provider", "groq").lower()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'hl7_message' is required.",
        )
    try:
        result = convert_hl7_to_fhir_via_llm(raw, provider=provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        logger.exception("AI HL7→FHIR error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # Save to history
    if result.get("success"):
        dq_issues, upsert_summary = _post_process_bundle(
            result.get("fhir_json"), raw,
            message_type=result.get("message_type"),
            conversion_source="HL7→FHIR (AI)",
            field_mappings=result.get("field_mappings")
        )
        result["dq_issues"] = dq_issues
        result["upsert_summary"] = upsert_summary

        history_item = HistoryItem(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            hl7_version=result.get("hl7_version", "2.5"),
            message_type=result.get("message_type"),
            message_event=result.get("message_event"),
            input_type="ai",
            input_name="AI conversion",
            success=True,
            hl7_content=raw,
            fhir_json=result.get("fhir_json"),
            fhir_xml=result.get("fhir_xml", ""),
            warnings=result.get("warnings", []),
        )
        history.add_conversion(history_item)

    return result


@router.post(
    "/convert/ai/fhir-to-hl7",
    summary="AI-powered FHIR → HL7 conversion via Gemini",
)
async def ai_convert_fhir_to_hl7(payload: dict):
    from app.core.llm_converter import convert_fhir_to_hl7_via_llm
    bundle = payload.get("fhir_bundle")
    provider = payload.get("provider", "groq").lower()
    if not bundle:
        if payload.get("resourceType") == "Bundle":
            bundle = payload
    if not bundle:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'fhir_bundle' is required.",
        )
    try:
        result = convert_fhir_to_hl7_via_llm(bundle, provider=provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        logger.exception("AI FHIR→HL7 error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # Save to history
    if result.get("success"):
        history_item = HistoryItem(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            hl7_version="2.5",
            message_type=result.get("message_type"),
            message_event=None,
            input_type="ai",
            input_name="AI conversion",
            success=True,
            hl7_content="",
            direction="fhir_to_hl7",
            fhir_json=bundle,
            hl7_output=result.get("hl7_output", ""),
            warnings=result.get("warnings", []),
        )
        history.add_conversion(history_item)

    return result


@router.post(
    "/convert/ehr-to-fhir",
    summary="Local EHR pipe-delimited → FHIR (no AI)",
    description="Convert pipe-delimited EHR data to FHIR R4 Bundle using local code — no external API needed.",
)
async def convert_ehr_to_fhir(payload: dict):
    from app.core.ehr_converter import convert_ehr_pipe_to_fhir
    from app.core.renderer import to_fhir_xml
    raw = payload.get("ehr_data", "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'ehr_data' is required.",
        )
    try:
        result = convert_ehr_pipe_to_fhir(raw)
    except Exception as exc:
        logger.exception("EHR→FHIR local conversion error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if result.get("success"):
        dq_issues, upsert_summary = _post_process_bundle(
            result.get("fhir_json"), raw,
            message_type=result.get("message_type", "EHR"),
            conversion_source="EHR→FHIR",
            field_mappings=result.get("field_mappings")
        )
        result["dq_issues"] = dq_issues
        result["upsert_summary"] = upsert_summary
        
        # Build XML via existing renderer
        try:
            result["fhir_xml"] = to_fhir_xml(result["fhir_json"])
        except Exception:
            result["fhir_xml"] = ""
        history_item = HistoryItem(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            hl7_version="N/A",
            message_type=result.get("message_type", "EHR"),
            message_event="EHR_PIPE",
            input_type="ehr_raw",
            input_name="Raw EHR Data",
            success=True,
            hl7_content=raw,
            fhir_json=result.get("fhir_json"),
            fhir_xml=result.get("fhir_xml", ""),
            warnings=result.get("warnings", []),
        )
        history.add_conversion(history_item)
    return result


@router.post(
    "/convert/ai/ehr-to-fhir",
    summary="AI-powered Raw EHR → FHIR conversion",
    description="Accept raw EHR data in any format (key-value, CSV, clinical notes) and convert to FHIR R4 Bundle.",
)
async def ai_convert_ehr_to_fhir(payload: dict):
    from app.core.llm_converter import convert_ehr_to_fhir_via_llm
    raw = payload.get("ehr_data", "").strip()
    provider = payload.get("provider", "groq").lower()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'ehr_data' is required.",
        )
    try:
        result = convert_ehr_to_fhir_via_llm(raw, provider=provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        logger.exception("AI EHR→FHIR error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if result.get("success"):
        dq_issues, upsert_summary = _post_process_bundle(
            result.get("fhir_json"), raw,
            message_type=result.get("message_type", "EHR"),
            conversion_source="EHR→FHIR (AI)",
            field_mappings=result.get("field_mappings")
        )
        result["dq_issues"] = dq_issues
        result["upsert_summary"] = upsert_summary
        
        history_item = HistoryItem(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            hl7_version="N/A",
            message_type=result.get("message_type", "EHR"),
            message_event=None,
            input_type="ehr_raw",
            input_name="Raw EHR Data",
            success=True,
            hl7_content=raw,
            fhir_json=result.get("fhir_json"),
            fhir_xml=result.get("fhir_xml", ""),
            warnings=result.get("warnings", []),
        )
        history.add_conversion(history_item)

    return result


@router.get(
    "/ai/status",
    summary="Check if AI (Groq) is configured",
)
async def ai_status():
    key = os.environ.get("GROQ_API_KEY", "")
    return {"configured": bool(key), "model": "llama-3.3-70b-versatile", "provider": "Groq"}


@router.get(
    "/health",
    summary="Health check",
)
async def health():
    return {"status": "ok", "service": "HL7-FHIR-Converter"}


@router.get(
    "/history",
    summary="Get conversion history",
    description="Retrieve the last 10 conversion attempts with their results.",
)
async def get_history():
    """Get all conversion history items."""
    return {"history": history.get_all()}


@router.get(
    "/history/{item_id}",
    summary="Get specific history item",
    description="Retrieve a specific conversion from history by ID.",
)
async def get_history_item(item_id: str):
    """Get a specific history item by ID."""
    item = history.get_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History item not found",
        )
    return item.to_dict()


@router.delete(
    "/history",
    summary="Clear conversion history",
    description="Clear all conversion history.",
)
async def clear_history():
    """Clear all conversion history."""
    history.clear()
    return {"message": "History cleared"}


@router.get(
    "/history/db/search",
    summary="Search conversion history — one entry per conversion event, grouped by patient",
)
def search_history(
    time_filter: str = "1d",
    name: Optional[str] = None,
    dob: Optional[str] = None,
    address: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    db = SessionLocal()
    try:
        from sqlalchemy import text as sa_text, cast, String, or_, Text
        query = db.query(ConversionLog)

        # 1. Date Range & Time Filter
        now = datetime.utcnow()
        if time_filter == "custom" and (start_date or end_date):
            if start_date:
                try:
                    s_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(ConversionLog.converted_at >= s_dt)
                except: pass
            if end_date:
                try:
                    e_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    if e_dt.hour == 0 and e_dt.minute == 0:
                        e_dt = e_dt + timedelta(days=1)
                    query = query.filter(ConversionLog.converted_at <= e_dt)
                except: pass
        elif time_filter != "all":
            # Traditional quick filters
            days_map = {"1d": 1, "1w": 7, "1m": 30, "1y": 365, "5y": 1825}
            if time_filter in days_map:
                query = query.filter(ConversionLog.converted_at >= now - timedelta(days=days_map[time_filter]))

        # Diagnostic Log
        print(f"Audit Search: time={time_filter}, name={name}, dob={dob}, address={address}, range={start_date} to {end_date}")

        # 2. ISOLATED Field Filters (avoid cross-matching)
        if name:
            # ONLY search the patient_name column. This prevents "New York" from matching James Rivera.
            query = query.filter(ConversionLog.patient_name.ilike(f"%{name}%"))
        
        if dob:
            # Use SQLAlchemy's native cast+ilike — generates proper parameterized SQL.
            # Searches the 'birthDate' key specifically inside the JSONB text so
            # encounter/observation dates do NOT accidentally match.
            dob_pattern = f'%"birthDate": "{dob}%'
            query = query.filter(cast(ConversionLog.fhir_bundle, Text).ilike(dob_pattern))

        if address:
            # Use SQLAlchemy's native cast+ilike — generates proper parameterized SQL.
            # Searches the entire FHIR bundle JSON for the city/address string.
            query = query.filter(cast(ConversionLog.fhir_bundle, Text).ilike(f"%{address}%"))

        logs = query.order_by(ConversionLog.converted_at.desc()).limit(200).all()

        # Group by patient — use MRN+name composite key so different patients
        # never collapse together even when MRN is missing or identical across samples.
        from collections import OrderedDict

        def _group_key(log):
            mrn = (log.patient_mrn or "").strip()
            name = (log.patient_name or "").strip().upper()
            # If we have a real MRN (not UNKNOWN / empty), use it alone
            if mrn and mrn != "UNKNOWN":
                return mrn
            # Fallback: use name so two different unknowns stay separate
            if name:
                return f"__NAME__{name}"
            # Last resort: keep the log isolated by its own id
            return f"__ID__{log.id}"

        patients: dict = OrderedDict()
        for log in logs:
            key = _group_key(log)
            if key not in patients:
                # Pull patient demographics matching THIS log entry's MRN
                patient_fhir = {}
                target_mrn = log.patient_mrn
                for entry in (log.fhir_bundle or {}).get("entry", []):
                    res = entry.get("resource", {})
                    if res.get("resourceType") == "Patient":
                        # Extract this resource's MRN for matching
                        curr_mrn = None
                        for ident in res.get("identifier", []):
                            if ident.get("value"):
                                curr_mrn = ident["value"]
                                break
                        if not curr_mrn: curr_mrn = res.get("id")
                        
                        if curr_mrn == target_mrn:
                            patient_fhir = res
                            break
                
                # If MRN match failed (e.g. name-based group), fallback to name match
                if not patient_fhir and log.patient_name:
                    search_name = log.patient_name.upper()
                    for entry in (log.fhir_bundle or {}).get("entry", []):
                        res = entry.get("resource", {})
                        if res.get("resourceType") == "Patient":
                            n = res.get("name", [{}])[0]
                            gn = " ".join(n.get("given", []))
                            fn = n.get("family", "")
                            res_name = f"{gn} {fn}".strip().upper()
                            if res_name == search_name:
                                patient_fhir = res
                                break

                # Determine best display MRN and name
                display_mrn = (log.patient_mrn or "").strip()
                if not display_mrn or display_mrn == "UNKNOWN":
                    display_mrn = "—"

                display_name = (log.patient_name or "").strip()
                if not display_name and patient_fhir.get("name"):
                    n = patient_fhir["name"][0]
                    given = " ".join(n.get("given", []))
                    family = n.get("family", "")
                    display_name = f"{given} {family}".strip()

                patients[key] = {
                    "patient_mrn": display_mrn,
                    "patient_name": display_name or "Unknown Patient",
                    "patient_data": patient_fhir,
                    "conversions": []
                }
            patients[key]["conversions"].append({
                "log_id": log.id,
                "message_type": log.message_type or "—",
                "conversion_source": log.conversion_source,
                "converted_at": log.converted_at.isoformat(),
                "warnings": log.warnings or [],
                "dq_issues": log.dq_issues or [],
                "success": log.success,
            })

        return {"results": list(patients.values())}
    except Exception as e:
        logger.error(f"Search history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get(
    "/history/log/{log_id}",
    summary="Retrieve the original clean FHIR bundle from a specific conversion log entry",
)
def get_conversion_log_bundle(log_id: str):
    """Returns the exact original FHIR bundle stored at conversion time — zero modification."""
    db = SessionLocal()
    try:
        log = db.query(ConversionLog).filter(ConversionLog.id == log_id).first()
        if not log:
            raise HTTPException(status_code=404, detail="Conversion log entry not found")
        return {
            "bundle": log.fhir_bundle,       # original, unmodified FHIR bundle
            "message_type": log.message_type,
            "conversion_source": log.conversion_source,
            "converted_at": log.converted_at.isoformat(),
            "patient_mrn": log.patient_mrn,
            "patient_name": log.patient_name,
            "warnings": log.warnings or [],
            "dq_issues": log.dq_issues or [],
            "field_mappings": log.field_mappings or [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get conversion log error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get(
    "/history/patient/{mrn}",
    summary="Get cumulative FHIR resource store for a patient MRN (filtered by resource_type if given)",
)
def get_patient_bundle(mrn: str, resource_type: Optional[str] = None):
    """Returns the cumulative FHIR resource store — best used for 'current state' view."""
    db = SessionLocal()
    try:
        query = db.query(FhirResource).filter(FhirResource.patient_mrn == mrn)
        if resource_type:
            query = query.filter(FhirResource.resource_type == resource_type)
        resources = query.all()
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [{"resource": r.data} for r in resources],
        }
        return {"bundle": bundle, "patient_mrn": mrn}
    except Exception as e:
        logger.error(f"Get patient bundle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
