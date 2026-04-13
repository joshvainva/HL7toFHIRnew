from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base

class FhirResource(Base):
    __tablename__ = "fhir_resource"

    id = Column(String(36), primary_key=True, index=True)
    resource_type = Column(String(50), index=True, nullable=False)
    patient_mrn = Column(String(100), index=True, nullable=False)
    logical_date = Column(DateTime, index=True, nullable=True)
    data = Column(JSONB, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    message_type = Column(String(100), nullable=True, index=True)   # e.g. "ADT^A01", "ORU^R01", "EHR_PIPE"
    conversion_source = Column(String(50), nullable=True)            # e.g. "HL7→FHIR", "EHR→FHIR", "FHIR→HL7"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    versions = relationship("FhirResourceVersion", back_populates="resource", cascade="all, delete-orphan")

class FhirResourceVersion(Base):
    __tablename__ = "fhir_resource_version"

    id = Column(String(36), primary_key=True, index=True)
    resource_id = Column(String(36), ForeignKey("fhir_resource.id"), index=True, nullable=False)
    version = Column(Integer, nullable=False)
    data = Column(JSONB, nullable=False)
    action = Column(String(20), nullable=False) # 'CREATE', 'UPDATE'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    resource = relationship("FhirResource", back_populates="versions")

class DataQualityIssue(Base):
    __tablename__ = "data_quality_issue"

    id = Column(String(36), primary_key=True, index=True)
    record_locator = Column(String(100), index=True)
    issue_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False) # 'WARNING', 'ERROR'
    raw_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ConversionLog(Base):
    """Immutable audit record — one row per individual conversion event."""
    __tablename__ = "conversion_log"

    id = Column(String(36), primary_key=True, index=True)
    patient_mrn = Column(String(100), index=True, nullable=True)   # extracted from bundle
    patient_name = Column(String(200), nullable=True)               # human-readable label
    message_type = Column(String(100), nullable=True)               # e.g. "ADT^A01"
    conversion_source = Column(String(50), nullable=False)          # "HL7→FHIR", "EHR→FHIR", "FHIR→HL7"
    fhir_bundle = Column(JSONB, nullable=True)                      # original clean FHIR output
    field_mappings = Column(JSONB, nullable=True)                   # source-to-target mapping details
    raw_input = Column(Text,  nullable=True)                        # original HL7/EHR text
    warnings = Column(JSONB,  nullable=True)                        # list of warning strings
    dq_issues = Column(JSONB, nullable=True)                        # data-quality flags
    success = Column(String(10), default="success", nullable=False) # "success" | "error"
    converted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
