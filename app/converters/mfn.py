"""
MFN (Master File Notification) message converter.

Produces: Organization, Practitioner, Location, ObservationDefinition resources.
"""
from typing import Any, Dict, List, Tuple

from app.converters.base import (
    BaseConverter,
    make_id,
    parse_hl7_datetime,
    extract_name,
    extract_address,
    extract_telecom,
    extract_identifier,
    extract_coding,
)
from app.core.parser import ParsedHL7Message
from app.models.schemas import FieldMapping, ResourceMapping


MFE_STATUS_MAP = {
    "MAD": "active",
    "MDL": "inactive",
    "MUP": "active",
    "MAC": "active",
    "MDC": "inactive",
}


def _seg(parsed_msg, name):
    return parsed_msg.get_segment(name)


def _field(seg, idx: int, component: int = 1) -> str:
    if seg is None:
        return ""
    try:
        val = str(seg[idx]).strip()
        if component > 1:
            parts = val.split("^")
            return parts[component - 1].strip() if len(parts) >= component else ""
        return val
    except Exception:
        return ""


class MFNConverter(BaseConverter):
    """Converts HL7 MFN messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[ResourceMapping]]:
        resources = []
        warnings = []
        field_mappings = []

        mfi = _seg(parsed_msg, "MFI")
        if mfi is None:
            warnings.append("MFN message missing MFI segment")
            return resources, warnings, field_mappings

        master_file_type = _field(mfi, 1)
        if not master_file_type:
            warnings.append("MFI-1 (master file identifier) is empty")

        # MFI-level mappings (no standalone resource, attach to first resource or skip)
        # We'll capture MFI info but only emit ResourceMapping when resources exist.
        mfi_mappings: List[FieldMapping] = []
        if master_file_type:
            mfi_mappings.append(FieldMapping(
                fhir_field="meta.tag",
                hl7_segment="MFI",
                hl7_field="1",
                hl7_value=master_file_type,
                description="Master file identifier / type"
            ))
        mfi_response_dt_raw = _field(mfi, 5)
        if mfi_response_dt_raw:
            mfi_mappings.append(FieldMapping(
                fhir_field="meta.lastUpdated",
                hl7_segment="MFI",
                hl7_field="5",
                hl7_value=mfi_response_dt_raw,
                description="Effective date/time of change"
            ))

        # Process each MFE segment
        for mfe in parsed_msg.get_all_segments("MFE"):
            resource, res_mappings = self._build_master_file_resource(
                master_file_type, mfe, parsed_msg
            )
            if resource:
                resources.append(resource)
                all_mappings = mfi_mappings + res_mappings
                mfi_mappings = []  # only attach MFI info to first resource
                if all_mappings:
                    field_mappings.append(ResourceMapping(
                        resource_type=resource["resourceType"],
                        resource_id=resource["id"],
                        field_mappings=all_mappings
                    ))

        return resources, warnings, field_mappings

    # ------------------------------------------------------------------
    def _build_master_file_resource(
        self,
        master_file_type: str,
        mfe: Any,
        parsed_msg: ParsedHL7Message,
    ) -> Tuple[Dict | None, List[FieldMapping]]:
        record_event = _field(mfe, 1)
        status = MFE_STATUS_MAP.get(record_event, "active")

        if master_file_type in ("PRA", "STF"):
            return self._build_practitioner(mfe, parsed_msg, status, record_event)
        elif master_file_type == "LOC":
            return self._build_location(mfe, parsed_msg, status, record_event)
        elif master_file_type == "OMD":
            return self._build_observation_definition(mfe, status, record_event)
        else:
            return self._build_organization(mfe, status, record_event)

    # ------------------------------------------------------------------
    def _build_practitioner(
        self, mfe: Any, parsed_msg: ParsedHL7Message, status: str, record_event: str
    ) -> Tuple[Dict, List[FieldMapping]]:
        prac_id = make_id()
        mappings: List[FieldMapping] = []

        mappings.append(FieldMapping(
            fhir_field="active",
            hl7_segment="MFE",
            hl7_field="1",
            hl7_value=record_event,
            description=f"Record-level event ({record_event} → active={status == 'active'})"
        ))

        # MFE-4: primary key value (ID/NPI)
        key_raw = _field(mfe, 4)
        # MFE-5: primary key value (name)
        name_raw = _field(mfe, 5)

        prac: Dict[str, Any] = {
            "resourceType": "Practitioner",
            "id": prac_id,
            "active": status == "active",
        }

        if key_raw:
            prac["identifier"] = [extract_identifier(key_raw, "http://hl7.org/fhir/sid/us-npi")]
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="MFE",
                hl7_field="4",
                hl7_value=key_raw,
                description="Practitioner primary key / NPI"
            ))

        if name_raw:
            prac["name"] = [extract_name(name_raw)]
            mappings.append(FieldMapping(
                fhir_field="name",
                hl7_segment="MFE",
                hl7_field="5",
                hl7_value=name_raw,
                description="Practitioner name"
            ))

        # Try STF segment for richer practitioner data
        stf = _seg(parsed_msg, "STF")
        if stf is not None:
            stf_phone = str(stf[10]).strip() if len(stf) > 10 else ""
            if stf_phone:
                telecoms = extract_telecom(stf_phone, "")
                if telecoms:
                    prac["telecom"] = telecoms
                    mappings.append(FieldMapping(
                        fhir_field="telecom",
                        hl7_segment="STF",
                        hl7_field="10",
                        hl7_value=stf_phone,
                        description="Staff phone number"
                    ))
            stf_addr = str(stf[11]).strip() if len(stf) > 11 else ""
            if stf_addr:
                addr = extract_address(stf_addr)
                if addr:
                    prac["address"] = [addr]
                    mappings.append(FieldMapping(
                        fhir_field="address",
                        hl7_segment="STF",
                        hl7_field="11",
                        hl7_value=stf_addr,
                        description="Staff address"
                    ))

        # Try PRA segment for specialty
        pra = _seg(parsed_msg, "PRA")
        if pra is not None:
            specialty_raw = str(pra[3]).strip() if len(pra) > 3 else ""
            if specialty_raw:
                prac["qualification"] = [{
                    "code": {"coding": [extract_coding(specialty_raw, "http://snomed.info/sct")]}
                }]
                mappings.append(FieldMapping(
                    fhir_field="qualification.code",
                    hl7_segment="PRA",
                    hl7_field="3",
                    hl7_value=specialty_raw,
                    description="Practitioner specialty"
                ))

        return prac, mappings

    # ------------------------------------------------------------------
    def _build_location(
        self, mfe: Any, parsed_msg: ParsedHL7Message, status: str, record_event: str
    ) -> Tuple[Dict, List[FieldMapping]]:
        loc_id = make_id()
        mappings: List[FieldMapping] = []

        mappings.append(FieldMapping(
            fhir_field="status",
            hl7_segment="MFE",
            hl7_field="1",
            hl7_value=record_event,
            description=f"Record-level event ({record_event} → {status})"
        ))

        key_raw = _field(mfe, 4)
        name_raw = _field(mfe, 5)

        location: Dict[str, Any] = {
            "resourceType": "Location",
            "id": loc_id,
            "status": status,
        }

        if key_raw:
            location["identifier"] = [extract_identifier(key_raw, "http://hospital.example.org/location")]
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="MFE",
                hl7_field="4",
                hl7_value=key_raw,
                description="Location primary key"
            ))

        if name_raw:
            location["name"] = name_raw
            mappings.append(FieldMapping(
                fhir_field="name",
                hl7_segment="MFE",
                hl7_field="5",
                hl7_value=name_raw,
                description="Location name"
            ))

        # LOC segment for address, type
        loc_seg = _seg(parsed_msg, "LOC")
        if loc_seg is not None:
            loc_type = str(loc_seg[3]).strip() if len(loc_seg) > 3 else ""
            if loc_type:
                location["type"] = [{"coding": [extract_coding(loc_type, "http://terminology.hl7.org/CodeSystem/v3-RoleCode")]}]
                mappings.append(FieldMapping(
                    fhir_field="type",
                    hl7_segment="LOC",
                    hl7_field="3",
                    hl7_value=loc_type,
                    description="Location type code"
                ))
            loc_addr = str(loc_seg[4]).strip() if len(loc_seg) > 4 else ""
            if loc_addr:
                addr = extract_address(loc_addr)
                if addr:
                    location["address"] = addr
                    mappings.append(FieldMapping(
                        fhir_field="address",
                        hl7_segment="LOC",
                        hl7_field="4",
                        hl7_value=loc_addr,
                        description="Location address"
                    ))

        return location, mappings

    # ------------------------------------------------------------------
    def _build_organization(
        self, mfe: Any, status: str, record_event: str
    ) -> Tuple[Dict, List[FieldMapping]]:
        org_id = make_id()
        mappings: List[FieldMapping] = []

        mappings.append(FieldMapping(
            fhir_field="active",
            hl7_segment="MFE",
            hl7_field="1",
            hl7_value=record_event,
            description=f"Record-level event ({record_event} → active={status == 'active'})"
        ))

        key_raw = _field(mfe, 4)
        name_raw = _field(mfe, 5)

        org: Dict[str, Any] = {
            "resourceType": "Organization",
            "id": org_id,
            "active": status == "active",
        }

        if key_raw:
            org["identifier"] = [extract_identifier(key_raw, "http://hospital.example.org/org")]
            mappings.append(FieldMapping(
                fhir_field="identifier",
                hl7_segment="MFE",
                hl7_field="4",
                hl7_value=key_raw,
                description="Organization primary key"
            ))

        if name_raw:
            org["name"] = name_raw
            mappings.append(FieldMapping(
                fhir_field="name",
                hl7_segment="MFE",
                hl7_field="5",
                hl7_value=name_raw,
                description="Organization name"
            ))

        return org, mappings

    # ------------------------------------------------------------------
    def _build_observation_definition(
        self, mfe: Any, status: str, record_event: str
    ) -> Tuple[Dict, List[FieldMapping]]:
        obs_id = make_id()
        mappings: List[FieldMapping] = []

        mappings.append(FieldMapping(
            fhir_field="status",
            hl7_segment="MFE",
            hl7_field="1",
            hl7_value=record_event,
            description=f"Record-level event ({record_event} → {status})"
        ))

        key_raw = _field(mfe, 4)
        name_raw = _field(mfe, 5)

        obs_def: Dict[str, Any] = {
            "resourceType": "ObservationDefinition",
            "id": obs_id,
        }

        if key_raw:
            obs_def["code"] = {"coding": [extract_coding(key_raw, "http://loinc.org")]}
            mappings.append(FieldMapping(
                fhir_field="code",
                hl7_segment="MFE",
                hl7_field="4",
                hl7_value=key_raw,
                description="Observation code (LOINC)"
            ))

        if name_raw:
            obs_def["name"] = name_raw
            mappings.append(FieldMapping(
                fhir_field="name",
                hl7_segment="MFE",
                hl7_field="5",
                hl7_value=name_raw,
                description="Observation definition name"
            ))

        return obs_def, mappings
