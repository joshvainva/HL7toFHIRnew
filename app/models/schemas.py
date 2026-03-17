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


class ConversionResult(BaseModel):
    success: bool
    hl7_version: Optional[str] = None
    message_type: Optional[str] = None
    message_event: Optional[str] = None
    fhir_json: Optional[Dict[str, Any]] = None
    fhir_xml: Optional[str] = None
    human_readable: Optional[str] = None
    resource_summary: List[ResourceSummary] = []
    errors: List[str] = []
    warnings: List[str] = []


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[str] = None
