import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.models.db_models import FhirResource, FhirResourceVersion

# Conditional import for dateutil. Fallback to basic string parsing if not available.
try:
    from dateutil.parser import parse as parse_date
except ImportError:
    def parse_date(date_str):
        # Basic fallback for FHIR dates like 2023-01-01T10:00:00+00:00
        # If this fails, it returns None
        try:
            clean_str = date_str.replace("Z", "+00:00")
            if "." in clean_str:
                clean_str = clean_str[:clean_str.index(".")] + clean_str[clean_str.index("+"):]
            if len(clean_str) > 19 and "+" in clean_str:
                return datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S%z")
            if "T" in clean_str:
                return datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
            return datetime.strptime(clean_str, "%Y-%m-%d")
        except ValueError:
            return None

logger = logging.getLogger(__name__)

class SmartUpsertEngine:
    def __init__(self, db: Session):
        self.db = db

    def extract_mrn(self, resource: dict) -> str:
        res_type = resource.get("resourceType")
        if res_type == "Patient":
            for ident in resource.get("identifier", []):
                if ident.get("value"):
                    return ident.get("value")
            return resource.get("id", "UNKNOWN_MRN")
        
        ref_str = None
        if "subject" in resource and "reference" in resource["subject"]:
            ref_str = resource["subject"]["reference"]
        elif "patient" in resource and "reference" in resource["patient"]:
            ref_str = resource["patient"]["reference"]
            
        if ref_str and ref_str.startswith("Patient/"):
            return ref_str.split("Patient/")[1]
            
        return "UNKNOWN_MRN"

    def extract_logical_date(self, resource: dict) -> datetime:
        try:
            date_str = None
            if resource.get("resourceType") == "Encounter":
                date_str = resource.get("period", {}).get("start")
            elif resource.get("resourceType") == "Observation":
                date_str = resource.get("effectiveDateTime")
            elif resource.get("resourceType") == "AllergyIntolerance":
                date_str = resource.get("onsetDateTime")
            elif resource.get("resourceType") == "Condition":
                date_str = resource.get("onsetDateTime")

            if date_str:
                return parse_date(date_str)
        except Exception:
            pass
        return None

    def upsert_bundle(self, bundle: dict, message_type: str = None, conversion_source: str = None) -> dict:
        """
        Process a FHIR Bundle and upsert all resources into PostgreSQL.
        Returns a summary of operations.
        """
        if bundle.get("resourceType") != "Bundle":
            return {"error": "Not a FHIR Bundle"}

        summary = {"inserted": 0, "updated": 0, "errors": 0}
        
        entries = bundle.get("entry", [])
        for entry in entries:
            resource = entry.get("resource", {})
            if not resource:
                continue
                
            res_type = resource.get("resourceType")
            if not res_type:
                continue
                
            mrn = self.extract_mrn(resource)
            logical_date = self.extract_logical_date(resource)
            
            existing = self.db.query(FhirResource).filter(
                FhirResource.patient_mrn == mrn,
                FhirResource.resource_type == res_type
            )
            
            if logical_date:
                existing = existing.filter(FhirResource.logical_date == logical_date)
                
            existing_record = existing.first()
            
            try:
                if existing_record:
                    # Create audit trail of the old version
                    old_version = FhirResourceVersion(
                        id=str(uuid.uuid4()),
                        resource_id=existing_record.id,
                        version=existing_record.version,
                        data=existing_record.data,
                        action="UPDATE"
                    )
                    self.db.add(old_version)
                    
                    # Update
                    existing_record.version += 1
                    existing_record.data = resource
                    if message_type:
                        existing_record.message_type = message_type
                    if conversion_source:
                        existing_record.conversion_source = conversion_source
                    summary["updated"] += 1
                else:
                    # Insert
                    new_id = str(uuid.uuid4())
                    new_record = FhirResource(
                        id=new_id,
                        resource_type=res_type,
                        patient_mrn=mrn,
                        logical_date=logical_date,
                        data=resource,
                        version=1,
                        message_type=message_type,
                        conversion_source=conversion_source
                    )
                    self.db.add(new_record)
                    
                    # Create initial version
                    initial_version = FhirResourceVersion(
                        id=str(uuid.uuid4()),
                        resource_id=new_id,
                        version=1,
                        data=resource,
                        action="CREATE"
                    )
                    self.db.add(initial_version)
                    summary["inserted"] += 1
                    
            except Exception as e:
                logger.error(f"Error upserting resource {res_type}: {e}")
                summary["errors"] += 1
        
        try:
            self.db.commit()
        except SQLAlchemyError as err:
            self.db.rollback()
            logger.error(f"Database commit failed: {err}")
            summary["errors"] += len(entries)
            
        return summary
