"""
Pydantic schemas for request/response models.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConversionRequest(BaseModel):
    hl7_message: str = Field(..., description="Raw HL7 message text")


class ResourceSummary(BaseModel):
    resource_type: str
    resource_id: str
    description: str


class FieldMapping(BaseModel):
    fhir_field: str
    hl7_segment: str
    hl7_field: str
    hl7_value: Optional[str] = None
    description: str


class ResourceMapping(BaseModel):
    resource_type: str
    resource_id: str
    field_mappings: List[FieldMapping] = []


class ConversionResult(BaseModel):
    success: bool
    direction: str = "hl7_to_fhir"
    hl7_version: Optional[str] = None
    message_type: Optional[str] = None
    message_event: Optional[str] = None
    fhir_json: Optional[Dict[str, Any]] = None
    fhir_xml: Optional[str] = None
    human_readable: Optional[str] = None
    resource_summary: List[ResourceSummary] = []
    field_mappings: List[ResourceMapping] = []
    hl7_output: Optional[str] = None
    errors: List[str] = []
    warnings: List[str] = []


class FHIRConversionRequest(BaseModel):
    fhir_bundle: Dict[str, Any] = Field(..., description="FHIR Bundle JSON object")


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[str] = None
