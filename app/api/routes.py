"""
API routes for the HL7 → FHIR converter.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional

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

logger = logging.getLogger(__name__)

router = APIRouter()

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
