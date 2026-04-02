import uuid
from typing import List, Dict
from sqlalchemy.orm import Session
import logging

from app.models.db_models import DataQualityIssue

logger = logging.getLogger(__name__)

class DQEngine:
    def __init__(self, db: Session):
        self.db = db

    def validate_bundle(self, bundle: dict) -> List[Dict]:
        """
        Validates all resources in a FHIR Bundle against Data Quality Rules.
        Returns a list of flagged issues.
        """
        issues = []
        if bundle.get("resourceType") != "Bundle":
            return issues

        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if not resource:
                continue
                
            res_type = resource.get("resourceType")
            res_id = resource.get("id", "UNKNOWN")
            
            # Rule 1: Mandatory Patient Demographics
            if res_type == "Patient":
                if "birthDate" not in resource:
                    issues.append({
                        "locator": f"Patient/{res_id}",
                        "type": "MISSING_DOB",
                        "desc": "Patient record is missing birthDate.",
                        "severity": "WARNING"
                    })
                if "name" not in resource or not resource.get("name"):
                    issues.append({
                        "locator": f"Patient/{res_id}",
                        "type": "MISSING_NAME",
                        "desc": "Patient record is missing a standard name.",
                        "severity": "ERROR"
                    })
            
            # Rule 2: Valid Date Checks
            if res_type in ["AllergyIntolerance", "Condition"]:
                onset = resource.get("onsetDateTime")
                if onset and len(onset) < 4:
                    issues.append({
                        "locator": f"{res_type}/{res_id}",
                        "type": "BAD_DATE_FORMAT",
                        "desc": f"Suspicious or invalid date string format: {onset}",
                        "severity": "WARNING"
                    })

            # Rule 3: Isolation Checks (must have patient reference)
            clinical_types = ["Observation", "Condition", "AllergyIntolerance", "Encounter", "MedicationRequest", "MedicationStatement", "Procedure", "DiagnosticReport"]
            if res_type in clinical_types:
                subject = resource.get("subject", resource.get("patient"))
                if not subject or "reference" not in subject:
                    issues.append({
                        "locator": f"{res_type}/{res_id}",
                        "type": "ORPHANED_RECORD",
                        "desc": f"{res_type} lacks patient subject reference. This record may be orphaned.",
                        "severity": "ERROR"
                    })
        return issues

    def record_issues(self, issues: List[Dict], raw_content: str = ""):
        """
        Store flagged DQ issues in the PostgreSQL database.
        """
        if not issues:
            return

        for issue in issues:
            db_issue = DataQualityIssue(
                id=str(uuid.uuid4()),
                record_locator=issue["locator"],
                issue_type=issue["type"],
                description=issue["desc"],
                severity=issue["severity"],
                raw_data=raw_content[:2000] if raw_content else None # store excerpt
            )
            self.db.add(db_issue)
            
        try:
            self.db.commit()
            logger.info(f"Recorded {len(issues)} DQ issues to database.")
        except Exception as e:
            logger.error(f"Failed to record DQ issues: {e}")
            self.db.rollback()
