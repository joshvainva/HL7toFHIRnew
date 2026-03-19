"""
VXU (Vaccination Update) message converter.

Produces: Patient, Immunization, Practitioner, Organization resources.
"""
from typing import Any, Dict, List, Tuple

from app.converters.base import (
    BaseConverter,
    make_id,
    safe_str,
    parse_hl7_datetime,
    parse_hl7_date,
    extract_name,
    extract_address,
    extract_telecom,
    extract_identifier,
    extract_coding,
)
from app.core.parser import ParsedHL7Message
from app.models.schemas import FieldMapping, ResourceMapping


GENDER_MAP = {
    "M": "male",
    "F": "female",
    "O": "other",
    "U": "unknown",
    "A": "other",
    "N": "unknown",
}

VXU_IMMUNIZATION_STATUS = {
    "V04": "completed",
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


class VXUConverter(BaseConverter):
    """Converts HL7 VXU messages to FHIR resources."""

    def convert(self, parsed_msg: ParsedHL7Message) -> Tuple[List[Dict[str, Any]], List[str], List[ResourceMapping]]:
        resources = []
        warnings = []
        field_mappings = []

        patient_id = make_id()
        org_id = make_id()

        # Build Patient
        patient, patient_mappings = self._build_patient(parsed_msg, patient_id, warnings)
        resources.append(patient)
        if patient_mappings:
            field_mappings.append(ResourceMapping(
                resource_type="Patient",
                resource_id=patient_id,
                field_mappings=patient_mappings
            ))

        # Build Organization from MSH-4
        org, org_mappings = self._build_organization(parsed_msg, org_id)
        if org:
            resources.append(org)
            if org_mappings:
                field_mappings.append(ResourceMapping(
                    resource_type="Organization",
                    resource_id=org_id,
                    field_mappings=org_mappings
                ))

        # Build Immunization resources from RXA segments
        for rxa in parsed_msg.get_all_segments("RXA"):
            immunization_id = make_id()
            immunization, practitioners, imm_mappings, prac_mappings_list = self._build_immunization(
                parsed_msg, immunization_id, patient_id, org_id if org else None, rxa, warnings
            )
            resources.extend(practitioners)
            resources.append(immunization)

            for i, prac in enumerate(practitioners):
                if i < len(prac_mappings_list) and prac_mappings_list[i]:
                    field_mappings.append(ResourceMapping(
                        resource_type="Practitioner",
                        resource_id=prac["id"],
                        field_mappings=prac_mappings_list[i]
                    ))

            if imm_mappings:
                field_mappings.append(ResourceMapping(
                    resource_type="Immunization",
                    resource_id=immunization_id,
                    field_mappings=imm_mappings
                ))

        return resources, warnings, field_mappings

    # ------------------------------------------------------------------
    def _build_patient(self, msg: ParsedHL7Message, patient_id: str, warnings: list) -> Tuple[Dict, List[FieldMapping]]:
        pid = _seg(msg, "PID")
        resource: Dict[str, Any] = {"resourceType": "Patient", "id": patient_id}
        mappings: List[FieldMapping] = []

        if pid is None:
            warnings.append("PID segment missing — Patient resource will be incomplete.")
            return resource, mappings

        # Identifiers (PID-3)
        identifiers = []
        for pid3 in str(pid[3]).split("~"):
            if pid3.strip():
                identifiers.append(extract_identifier(pid3, "http://hospital.example.org/mrn"))
                mappings.append(FieldMapping(
                    fhir_field="identifier",
                    hl7_segment="PID",
                    hl7_field="3",
                    hl7_value=pid3.strip(),
                    description="Patient identifier/MRN"
                ))
        if identifiers:
            resource["identifier"] = identifiers

        # Name (PID-5)
        names = []
        for name_raw in str(pid[5]).split("~"):
            if name_raw.strip():
                names.append(extract_name(name_raw))
                mappings.append(FieldMapping(
                    fhir_field="name",
                    hl7_segment="PID",
                    hl7_field="5",
                    hl7_value=name_raw.strip(),
                    description="Patient name"
                ))
        if names:
            resource["name"] = names

        # DOB (PID-7)
        dob_raw = _field(pid, 7)
        dob = parse_hl7_date(dob_raw)
        if dob:
            resource["birthDate"] = dob
            mappings.append(FieldMapping(
                fhir_field="birthDate",
                hl7_segment="PID",
                hl7_field="7",
                hl7_value=dob_raw,
                description="Date of birth"
            ))

        # Gender (PID-8)
        sex_code = _field(pid, 8).upper()
        resource["gender"] = GENDER_MAP.get(sex_code, "unknown")
        if sex_code:
            mappings.append(FieldMapping(
                fhir_field="gender",
                hl7_segment="PID",
                hl7_field="8",
                hl7_value=sex_code,
                description="Administrative sex"
            ))

        # Address (PID-11)
        try:
            addr_raw = str(pid[11]).strip()
            if addr_raw:
                addr = extract_address(addr_raw)
                if addr:
                    resource["address"] = [addr]
                    mappings.append(FieldMapping(
                        fhir_field="address",
                        hl7_segment="PID",
                        hl7_field="11",
                        hl7_value=addr_raw,
                        description="Patient address"
                    ))
        except Exception:
            pass

        # Telecom
        try:
            telecoms = extract_telecom(
                pid[13] if len(pid) > 13 else "",
                pid[14] if len(pid) > 14 else ""
            )
            if telecoms:
                if len(telecoms) > 1:
                    telecoms[1]["use"] = "work"
                resource["telecom"] = telecoms
                if len(pid) > 13 and pid[13]:
                    mappings.append(FieldMapping(
                        fhir_field="telecom",
                        hl7_segment="PID",
                        hl7_field="13",
                        hl7_value=str(pid[13]),
                        description="Home phone number"
                    ))
        except Exception:
            pass

        return resource, mappings

    # ------------------------------------------------------------------
    def _build_organization(self, msg: ParsedHL7Message, org_id: str) -> Tuple[Dict | None, List[FieldMapping]]:
        msh = _seg(msg, "MSH")
        org_name = _field(msh, 4, 1) or msg.sending_facility
        if not org_name:
            return None, []
        mappings = [FieldMapping(
            fhir_field="name",
            hl7_segment="MSH",
            hl7_field="4",
            hl7_value=org_name,
            description="Sending facility/organization name"
        )]
        return {"resourceType": "Organization", "id": org_id, "name": org_name}, mappings

    # ------------------------------------------------------------------
    def _build_immunization(
        self,
        msg: ParsedHL7Message,
        immunization_id: str,
        patient_id: str,
        org_id: str | None,
        rxa: Any,
        warnings: list,
    ) -> Tuple[Dict, List[Dict], List[FieldMapping], List[List[FieldMapping]]]:
        mappings: List[FieldMapping] = []
        practitioners: List[Dict] = []
        prac_mappings_list: List[List[FieldMapping]] = []

        status = VXU_IMMUNIZATION_STATUS.get(msg.message_event, "completed")

        immunization: Dict[str, Any] = {
            "resourceType": "Immunization",
            "id": immunization_id,
            "status": status,
            "patient": {"reference": f"Patient/{patient_id}"},
            "vaccineCode": {"coding": [{"system": "http://hl7.org/fhir/sid/cvx", "code": "unknown"}]},
        }
        mappings.append(FieldMapping(
            fhir_field="status",
            hl7_segment="MSH",
            hl7_field="9",
            hl7_value=msg.message_event,
            description=f"Immunization status from event ({status})"
        ))

        if rxa is None:
            warnings.append("RXA segment missing — Immunization will be incomplete.")
            return immunization, practitioners, mappings, prac_mappings_list

        # Vaccine code (RXA-5)
        vaccine_raw = _field(rxa, 5)
        if vaccine_raw:
            immunization["vaccineCode"] = extract_coding(vaccine_raw, "http://hl7.org/fhir/sid/cvx")
            mappings.append(FieldMapping(
                fhir_field="vaccineCode",
                hl7_segment="RXA",
                hl7_field="5",
                hl7_value=vaccine_raw,
                description="Vaccine administered code (CVX)"
            ))

        # Occurrence date/time (RXA-3)
        occurrence_raw = _field(rxa, 3)
        if occurrence_raw:
            occurrence_dt = parse_hl7_datetime(occurrence_raw)
            if occurrence_dt:
                immunization["occurrenceDateTime"] = occurrence_dt
                mappings.append(FieldMapping(
                    fhir_field="occurrenceDateTime",
                    hl7_segment="RXA",
                    hl7_field="3",
                    hl7_value=occurrence_raw,
                    description="Date/time of administration"
                ))

        # Dose quantity (RXA-6) and units (RXA-7)
        dose_raw = _field(rxa, 6)
        dose_units = _field(rxa, 7)
        if dose_raw:
            try:
                dose_qty: Dict[str, Any] = {"value": float(dose_raw)}
                if dose_units:
                    dose_qty["unit"] = dose_units
                    dose_qty["system"] = "http://unitsofmeasure.org"
                immunization["doseQuantity"] = dose_qty
                mappings.append(FieldMapping(
                    fhir_field="doseQuantity",
                    hl7_segment="RXA",
                    hl7_field="6",
                    hl7_value=dose_raw,
                    description="Administered dose amount"
                ))
            except Exception:
                pass

        # Administration site (RXA-9)
        site_raw = _field(rxa, 9)
        if site_raw:
            immunization["site"] = extract_coding(site_raw, "http://terminology.hl7.org/CodeSystem/v3-ActSite")
            mappings.append(FieldMapping(
                fhir_field="site",
                hl7_segment="RXA",
                hl7_field="9",
                hl7_value=site_raw,
                description="Administration site"
            ))

        # Administration route (RXA-10)  — also used for performer below, so read it once
        route_raw = _field(rxa, 10)
        if route_raw:
            immunization["route"] = extract_coding(route_raw, "http://terminology.hl7.org/CodeSystem/v3-RouteOfAdministration")
            mappings.append(FieldMapping(
                fhir_field="route",
                hl7_segment="RXA",
                hl7_field="10",
                hl7_value=route_raw,
                description="Administration route"
            ))

        # Lot number (RXA-15)
        lot_raw = _field(rxa, 15)
        if lot_raw:
            immunization["lotNumber"] = lot_raw
            mappings.append(FieldMapping(
                fhir_field="lotNumber",
                hl7_segment="RXA",
                hl7_field="15",
                hl7_value=lot_raw,
                description="Vaccine lot number"
            ))

        # Expiration date (RXA-16)
        exp_raw = _field(rxa, 16)
        if exp_raw:
            exp_dt = parse_hl7_date(exp_raw)
            if exp_dt:
                immunization["expirationDate"] = exp_dt
                mappings.append(FieldMapping(
                    fhir_field="expirationDate",
                    hl7_segment="RXA",
                    hl7_field="16",
                    hl7_value=exp_raw,
                    description="Vaccine expiration date"
                ))

        # Manufacturer (RXA-17)
        mfr_raw = _field(rxa, 17)
        if mfr_raw and org_id:
            # Reuse existing org or build a manufacturer org
            mfr_id = make_id()
            mfr_org: Dict[str, Any] = {
                "resourceType": "Organization",
                "id": mfr_id,
                "name": mfr_raw,
                "identifier": [extract_identifier(mfr_raw, "http://hl7.org/fhir/sid/mvx")],
            }
            practitioners.append(mfr_org)  # type: ignore[arg-type]
            prac_mappings_list.append([FieldMapping(
                fhir_field="name",
                hl7_segment="RXA",
                hl7_field="17",
                hl7_value=mfr_raw,
                description="Vaccine manufacturer"
            )])
            immunization["manufacturer"] = {"reference": f"Organization/{mfr_id}"}
            mappings.append(FieldMapping(
                fhir_field="manufacturer",
                hl7_segment="RXA",
                hl7_field="17",
                hl7_value=mfr_raw,
                description="Vaccine manufacturer"
            ))

        # Administering provider (RXA-10 already used for route; RXA-10 in HL7 v2.5+ is route,
        # actual administering provider is RXA-10 in v2.3. Use RXA-10 component check or dedicated field.)
        # In HL7 2.5, administering provider = RXA-10 (route) vs prior versions. Use ORC-12 or PV1-7.
        pv1 = _seg(msg, "PV1")
        if pv1 is not None:
            provider_raw = str(pv1[7]).strip() if len(pv1) > 7 else ""
            if provider_raw:
                parts = provider_raw.split("^")
                npi = parts[0].strip()
                family = parts[1].strip() if len(parts) > 1 else ""
                given = parts[2].strip() if len(parts) > 2 else ""
                prac_id = make_id()
                prac: Dict[str, Any] = {"resourceType": "Practitioner", "id": prac_id}
                prac_maps: List[FieldMapping] = []
                if npi:
                    prac["identifier"] = [{"system": "http://hl7.org/fhir/sid/us-npi", "value": npi}]
                    prac_maps.append(FieldMapping(
                        fhir_field="identifier",
                        hl7_segment="PV1",
                        hl7_field="7",
                        hl7_value=npi,
                        description="Administering provider NPI"
                    ))
                name: Dict[str, Any] = {"use": "official"}
                if family:
                    name["family"] = family
                if given:
                    name["given"] = [given]
                prac["name"] = [name]
                if family or given:
                    prac_maps.append(FieldMapping(
                        fhir_field="name",
                        hl7_segment="PV1",
                        hl7_field="7",
                        hl7_value=provider_raw,
                        description="Administering provider name"
                    ))
                practitioners.append(prac)
                prac_mappings_list.append(prac_maps)
                immunization["performer"] = [{"actor": {"reference": f"Practitioner/{prac_id}"}}]
                mappings.append(FieldMapping(
                    fhir_field="performer",
                    hl7_segment="PV1",
                    hl7_field="7",
                    hl7_value=provider_raw,
                    description="Vaccine administering provider"
                ))

        # VIS document (RXA-26 in v2.5+): Vaccine Information Statement
        try:
            vis_raw = _field(rxa, 26)
            if vis_raw:
                immunization["education"] = [{
                    "documentType": vis_raw,
                    "publicationDate": None,
                }]
                mappings.append(FieldMapping(
                    fhir_field="education.documentType",
                    hl7_segment="RXA",
                    hl7_field="26",
                    hl7_value=vis_raw,
                    description="Vaccine Information Statement (VIS)"
                ))
        except Exception:
            pass

        immunization["primarySource"] = True

        return immunization, practitioners, mappings, prac_mappings_list

    def _map_gender(self, gender_field: Any) -> str:
        gender = safe_str(gender_field).upper()
        return GENDER_MAP.get(gender, "unknown")
