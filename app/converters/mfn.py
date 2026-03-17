"""
MFN (Master File Notification) message converter.

Produces: Organization, Practitioner, Location, other master file resources.
"""
from typing import Any, Dict, List, Tuple

from app.converters.base import (
    BaseConverter,
    make_id,
    safe_str,
    parse_hl7_datetime,
    extract_name,
    extract_address,
    extract_telecom,
    extract_identifier,
    extract_coding,
)
from app.core.parser import ParsedHL7Message


class MFNConverter(BaseConverter):
    """Converts HL7 MFN messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str]]:
        resources = []
        warnings = []

        # MFN messages can contain different master file types
        mfi = parsed_msg.get_segment("MFI")
        if not mfi:
            warnings.append("MFN message missing MFI segment")
            return resources, warnings

        master_file_type = safe_str(mfi[1])  # Master file identifier

        # Process MFE segments (Master File Entry)
        for mfe in parsed_msg.get_all_segments("MFE"):
            resource = self._build_master_file_resource(master_file_type, mfe, parsed_msg, warnings)
            if resource:
                resources.append(resource)

        return resources, warnings

    def _build_master_file_resource(self, master_file_type: str, mfe: Any, parsed_msg: ParsedHL7Message, warnings: List[str]) -> Dict[str, Any]:
        """Build appropriate FHIR resource based on master file type."""
        record_level_event = safe_str(mfe[1])  # MFE-1: Record-level event code

        # Map MFN event to resource status
        status_map = {
            "MAD": "active",      # Add record to master file
            "MDL": "inactive",    # Delete record from master file
            "MUP": "active",      # Update record in master file
        }
        status = status_map.get(record_level_event, "active")

        if master_file_type == "PRA":  # Practitioner master file
            return self._build_practitioner(mfe, parsed_msg, status, warnings)
        elif master_file_type == "LOC":  # Location master file
            return self._build_location(mfe, parsed_msg, status, warnings)
        elif master_file_type == "STF":  # Staff master file
            return self._build_practitioner(mfe, parsed_msg, status, warnings)
        elif master_file_type == "OMD":  # Observation master file
            return self._build_observation_definition(mfe, parsed_msg, status, warnings)
        else:
            # Default to Organization for unknown types
            return self._build_organization(mfe, parsed_msg, status, warnings)

    def _build_practitioner(self, mfe: Any, parsed_msg: ParsedHL7Message, status: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR Practitioner resource."""
        practitioner_id = make_id()

        practitioner = {
            "resourceType": "Practitioner",
            "id": practitioner_id,
            "active": status == "active",
            "identifier": [extract_identifier(mfe[4])],  # MFE-4: Primary key value
            "name": [extract_name(mfe[5])],  # MFE-5: Primary key value (name)
        }

        # Add telecom from associated segments if available
        # This would typically come from PRA segments in real MFN messages
        return practitioner

    def _build_location(self, mfe: Any, parsed_msg: ParsedHL7Message, status: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR Location resource."""
        location_id = make_id()

        location = {
            "resourceType": "Location",
            "id": location_id,
            "status": status,
            "name": safe_str(mfe[5]),  # MFE-5: Primary key value
            "identifier": [extract_identifier(mfe[4])],  # MFE-4: Primary key value
        }

        # Add address from associated segments if available
        return location

    def _build_organization(self, mfe: Any, parsed_msg: ParsedHL7Message, status: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR Organization resource."""
        organization_id = make_id()

        organization = {
            "resourceType": "Organization",
            "id": organization_id,
            "active": status == "active",
            "name": safe_str(mfe[5]),  # MFE-5: Primary key value
            "identifier": [extract_identifier(mfe[4])],  # MFE-4: Primary key value
        }

        return organization

    def _build_observation_definition(self, mfe: Any, parsed_msg: ParsedHL7Message, status: str, warnings: List[str]) -> Dict[str, Any]:
        """Build FHIR ObservationDefinition resource (for lab tests, etc.)."""
        observation_id = make_id()

        observation = {
            "resourceType": "ObservationDefinition",
            "id": observation_id,
            "status": status,
            "code": {"coding": [extract_coding(mfe[4])]},  # MFE-4: Primary key value
            "name": safe_str(mfe[5]),  # MFE-5: Primary key value
        }

        return observation