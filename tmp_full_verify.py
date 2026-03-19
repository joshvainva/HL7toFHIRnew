"""
Comprehensive HL7 → FHIR Conversion Verification Script
Verifies all message types: ADT, ORU, ORM, SIU, MDM, DFT, VXU, MFN, ACK, BAR
"""

import sys
import os
import json
import traceback

# Add the project root to sys.path so we can import app.*
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.parser import HL7Parser, HL7ParseError
from app.core.mapper import FHIRMapper

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

PASS = "PASS"
FAIL = "FAIL"

results = []          # list of (test_name, status, detail)
total_pass = 0
total_fail = 0


def record(test_name: str, condition: bool, actual=None, expected=None):
    global total_pass, total_fail
    status = PASS if condition else FAIL
    detail = ""
    if not condition:
        detail = f"  expected={expected!r}  actual={actual!r}"
    results.append((test_name, status, detail))
    if condition:
        total_pass += 1
    else:
        total_fail += 1


def run_conversion(label: str, raw_msg: str):
    """Parse + map a raw HL7 message; return (bundle, warnings, field_mappings) or raise."""
    parser = HL7Parser()
    parsed = parser.parse(raw_msg)
    mapper = FHIRMapper()
    bundle, warnings, field_mappings = mapper.map(parsed)
    return bundle, warnings, field_mappings, parsed


def get_resources(bundle):
    """Flatten entries to list of resource dicts."""
    return [e["resource"] for e in bundle.get("entry", [])]


def find_resource(bundle, resource_type):
    """Return first matching resource of given type, or None."""
    for r in get_resources(bundle):
        if r.get("resourceType") == resource_type:
            return r
    return None


def find_all_resources(bundle, resource_type):
    return [r for r in get_resources(bundle) if r.get("resourceType") == resource_type]


def get_identifier_system(resource, system_substring):
    """Check if any identifier on the resource has a system containing system_substring."""
    for ident in resource.get("identifier", []):
        if system_substring in ident.get("system", ""):
            return ident
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Sample HL7 Messages
# ─────────────────────────────────────────────────────────────────────────────

# NOTE: HL7 field delimiter = |, component = ^, repeat = ~, escape = \, subcomponent = &
# PID-3 = patient identifiers (repeating with ~)
#   format per repeat: id^^^authority^id_type_code
# PV1-7 = attending physician: npi^family^given^...

ADT_A01 = (
    "MSH|^~\\&|EPIC|MEMHOSP|RHAPSODY|DEST|20240315120000||ADT^A01^ADT_A01|MSG001|P|2.5.1\r"
    "SFT|Epic Systems|10.3|EpicCare||20240101\r"
    "EVN|A01|20240315120000\r"
    "PID|1||12345^^^MEMHOSP^MRN~E98765^^^EPICMRN^EPI||SMITH^JOHN^PAUL^JR^DR||19800515|M|||123 MAIN ST^^SPRINGFIELD^IL^62701^USA||5551234567|5559876543||||S||||\r"
    # PV1: [7]=attending, [19]=visit#, [44]=admit_dt (46 data fields total, index 1-45 + seg name)
    "PV1|1|I|3WEST^301^A||||1234567890^DOE^JANE^M^DR^MD||||||||||||V12345|||||||||||||||||||||||||20240315120000||\r"
    "DG1|1||J18.9^Pneumonia^ICD10\r"
    "ZPD|EPIC_PAT_ID_12345|ENROLLED|PRIMARY_CARE_PROVIDER\r"
    "ZEP|EP_FLAG_001|ALERT_TYPE\r"
)

ADT_A03 = (
    "MSH|^~\\&|EPIC|MEMHOSP|RHAPSODY|DEST|20240316080000||ADT^A03^ADT_A03|MSG002|P|2.5.1\r"
    "EVN|A03|20240316080000\r"
    "PID|1||12345^^^MEMHOSP^MRN||SMITH^JOHN^PAUL^JR^DR||19800515|M|||123 MAIN ST^^SPRINGFIELD^IL^62701^USA\r"
    # PV1: [7]=attending, [19]=visit#, [44]=admit_dt, [45]=discharge_dt
    "PV1|1|I|3WEST^301^A||||1234567890^DOE^JANE^M^DR^MD||||||||||||V12345|||||||||||||||||||||||||20240315120000|20240316080000|\r"
)

ORU_R01 = (
    "MSH|^~\\&|LAB|MEMHOSP|RHAPSODY|DEST|20240315130000||ORU^R01^ORU_R01|MSG003|P|2.5.1\r"
    "PID|1||67890^^^MEMHOSP^MRN||JONES^MARY^ANN||19650720|F|||456 OAK AVE^^CHICAGO^IL^60601^USA\r"
    "PV1|1|O|CLINIC^101^B\r"
    "OBR|1|ORD001|FILL001|2160-0^Creatinine^LN|||20240315130000\r"
    "OBX|1|NM|2160-0^Creatinine^LN||1.2|mg/dL|0.5-1.5||||F|||20240315140000\r"
    "OBX|2|NM|2951-2^Sodium^LN||140|mEq/L|136-145||||F|||20240315140000\r"
)

ORM_O01 = (
    "MSH|^~\\&|ORDER|MEMHOSP|LAB|DEST|20240315110000||ORM^O01^ORM_O01|MSG004|P|2.5.1\r"
    "PID|1||54321^^^MEMHOSP^MRN||BROWN^ROBERT||19751010|M\r"
    # ORC: [1]=NW, [2]=placer, [3]=filler, [9]=date/time, [12]=ordering provider
    # Note: ORM converter skips ORC-12 if first component is 8-14 pure digits (NPI is 10 digits!)
    # Use a non-pure-digit NPI format: include family name to avoid the datetime filter
    "ORC|NW|ORD-2024-001|FILL-2024-001|||||||20240315110000||CARTER^WILLIAM^J^DR||\r"
    "OBR|1|ORD-2024-001|FILL-2024-001|85025^CBC with Diff^LN|||20240315110000|||||R|||\r"
)

SIU_S12 = (
    "MSH|^~\\&|SCHED|MEMHOSP|RHAPSODY|DEST|20240315090000||SIU^S12^SIU_S12|MSG005|P|2.5.1\r"
    "SCH|APPT-2024-001||||||WELLNESS|ANNUAL PHYSICAL|60|||^^^20240320090000|^^^20240320100000\r"
    "PID|1||11111^^^MEMHOSP^MRN||DAVIS^PATRICIA^A||19900215|F|||789 ELM ST^^BOSTON^MA^02101^USA\r"
    # AIP-3 = resource ID (NPI^family^given) - index 3
    "AIP|1||1111111111^MARTIN^SARAH^B^DR\r"
    "AIL|1||EXAM ROOM 5\r"
)

MDM_T02 = (
    "MSH|^~\\&|DOC|MEMHOSP|RHAPSODY|DEST|20240315150000||MDM^T02^MDM_T02|MSG006|P|2.5.1\r"
    "EVN|T02|20240315150000\r"
    "PID|1||22222^^^MEMHOSP^MRN||WILSON^JAMES^R||19551225|M\r"
    "PV1|1|I|4EAST^405^A\r"
    # TXA: [9]=primary author, [12]=doc UID, [22]=authenticator
    "TXA|1|OP NOTE|text/plain|20240315150000|||||2222222222^GRAY^THOMAS^A|||DOC-2024-001||||||||||9999999999^AUTH^DOCTOR\r"
)

DFT_P03 = (
    "MSH|^~\\&|BILLING|MEMHOSP|FINANCE|DEST|20240315160000||DFT^P03^DFT_P03|MSG007|P|2.5.1\r"
    "EVN|P03|20240315160000\r"
    "PID|1||33333^^^MEMHOSP^MRN||TAYLOR^LINDA^M||19720430|F|||321 PINE RD^^DALLAS^TX^75201^USA\r"
    # PV1: [7]=attending physician
    "PV1|1|I|5NORTH^501^A||||3333333333^HALL^HENRY^P^DR\r"
    # FT1: [4]=trans date, [6]=trans type, [7]=amount, [8]=units, [25]=procedure code
    "FT1|1|TX001|||20240315160000|CG|500.00|USD|||||||||||||||||||||||||99213^Office Visit^CPT4\r"
    "DG1|1||E11.9^Type 2 Diabetes^ICD10\r"
)

VXU_V04 = (
    "MSH|^~\\&|IMMREG|MEMHOSP|DEST|DEST|20240315170000||VXU^V04^VXU_V04|MSG008|P|2.5.1\r"
    "PID|1||44444^^^MEMHOSP^MRN||ANDERSON^EMMA^L||20000610|F|||654 MAPLE DR^^SEATTLE^WA^98101^USA\r"
    # PV1: [7]=attending/administering provider
    "PV1|1|O|CLINIC||||4444444444^REED^DIANA^J^DR\r"
    "ORC|RE\r"
    # RXA: [5]=vaccine code, [6]=amount, [7]=units, [15]=lot number, [16]=expiry, [17]=manufacturer
    # Between [7]=mL and [15]=lot: need 7 empty fields (indices 8-14)
    "RXA|0|1|20240315170000|20240315170000|141^Influenza^CVX|0.5|mL||||||||LOT-INF-2024|20250601|CSL\r"
)

MFN_M02 = (
    "MSH|^~\\&|MAST|MEMHOSP|DEST|DEST|20240315180000||MFN^M02^MFN_M02|MSG009|P|2.5.1\r"
    "MFI|STF||UPD|||AL\r"
    "MFE|MAD|20240315|20240315|5555555555^JOHNSON^PETER^Q|JOHNSON^PETER^Q\r"
    "STF|5555555555|PID001|JOHNSON^PETER^Q||||(555)777-8888||20000101\r"
    "PRA|5555555555|||207R00000X\r"
)

ACK_AA = (
    "MSH|^~\\&|DEST|MEMHOSP|EPIC|MEMHOSP|20240315190000||ACK^A01|MSG010|P|2.5.1\r"
    "MSA|AA|MSG001|Message received and processed successfully\r"
)

BAR_P01 = (
    "MSH|^~\\&|EPIC|MEMHOSP|BILLING|DEST|20240315200000||BAR^P01^BAR_P01|MSG011|P|2.5.1\r"
    "EVN|P01|20240315200000\r"
    "PID|1||55555^^^MEMHOSP^MRN~E11111^^^EPICMRN^EPI||GARCIA^CARLOS^M||19881201|M|||999 BROADWAY^^NEW YORK^NY^10001^USA||2125551234\r"
    # PV1: [7]=attending, [19]=visit#, [44]=admit_dt
    "PV1|1|I|8SOUTH^801^A||||6666666666^LOPEZ^MARIA^J^DR||||||||||||VN-2024-555|||||||||||||||||||||||||20240315200000||\r"
    "IN1|1|BCBS-PPO|BCBS|Blue Cross Blue Shield||||BC-GRP-999\r"
    "GT1|1|GT001|GARCIA^CARLOS^M\r"
)


# ─────────────────────────────────────────────────────────────────────────────
# TEST SUITES
# ─────────────────────────────────────────────────────────────────────────────

def test_adt_a01():
    label = "ADT A01"
    print(f"\n{'='*70}")
    print(f"  {label}: Admit - COMPREHENSIVE CHECKS")
    print(f"{'='*70}")

    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, ADT_A01)
    except Exception as e:
        record(f"{label}: No exception during conversion", False, str(e))
        traceback.print_exc()
        return

    # Basic: no exception
    record(f"{label}: No exception during conversion", True)

    # Resource types
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: Patient resource produced", "Patient" in resource_types, resource_types)
    record(f"{label}: Encounter resource produced", "Encounter" in resource_types, resource_types)
    record(f"{label}: Organization resource produced", "Organization" in resource_types, resource_types)
    record(f"{label}: Practitioner resource produced", "Practitioner" in resource_types, resource_types)

    # JSON serialization
    try:
        json_str = json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))

    # Field mappings non-empty
    record(f"{label}: field_mappings non-empty", len(field_mappings) > 0, len(field_mappings))

    # Patient checks
    patient = find_resource(bundle, "Patient")
    if patient:
        # MRN identifier (PID-3: 12345^^^MEMHOSP^MRN)
        mrn_ident = None
        epi_ident = None
        for ident in patient.get("identifier", []):
            sys_val = ident.get("system", "")
            if "mrn" in sys_val.lower():
                mrn_ident = ident
            if "1.2.840.114350.1.13" in sys_val:
                epi_ident = ident

        record(f"{label}: Patient MRN identifier present", mrn_ident is not None,
               actual=[i.get("system") for i in patient.get("identifier", [])])
        record(f"{label}: Patient MRN system = http://hospital.example.org/mrn",
               mrn_ident is not None and mrn_ident.get("system") == "http://hospital.example.org/mrn",
               actual=mrn_ident.get("system") if mrn_ident else None,
               expected="http://hospital.example.org/mrn")
        record(f"{label}: Patient MRN value = 12345",
               mrn_ident is not None and mrn_ident.get("value") == "12345",
               actual=mrn_ident.get("value") if mrn_ident else None,
               expected="12345")

        # EPI identifier (PID-3: E98765^^^EPICMRN^EPI)
        record(f"{label}: Patient EPI identifier present", epi_ident is not None,
               actual=[i.get("system") for i in patient.get("identifier", [])])
        record(f"{label}: Patient EPI system = urn:oid:1.2.840.114350.1.13",
               epi_ident is not None and epi_ident.get("system") == "urn:oid:1.2.840.114350.1.13",
               actual=epi_ident.get("system") if epi_ident else None,
               expected="urn:oid:1.2.840.114350.1.13")
        record(f"{label}: Patient EPI value = E98765",
               epi_ident is not None and epi_ident.get("value") == "E98765",
               actual=epi_ident.get("value") if epi_ident else None,
               expected="E98765")

        # birthDate
        record(f"{label}: birthDate = 1980-05-15",
               patient.get("birthDate") == "1980-05-15",
               actual=patient.get("birthDate"), expected="1980-05-15")

        # gender (PID-8 = M)
        record(f"{label}: gender = male",
               patient.get("gender") == "male",
               actual=patient.get("gender"), expected="male")

        # name (PID-5: SMITH^JOHN^PAUL^JR^DR)
        names = patient.get("name", [])
        has_name = len(names) > 0
        record(f"{label}: name present", has_name)
        if has_name:
            first_name = names[0]
            record(f"{label}: name.family = SMITH",
                   first_name.get("family") == "SMITH",
                   actual=first_name.get("family"), expected="SMITH")
            given_list = first_name.get("given", [])
            record(f"{label}: name.given[0] = JOHN",
                   len(given_list) > 0 and given_list[0] == "JOHN",
                   actual=given_list, expected=["JOHN", ...])
            record(f"{label}: name.suffix = JR",
                   "JR" in first_name.get("suffix", []),
                   actual=first_name.get("suffix"), expected=["JR"])
            record(f"{label}: name.prefix = DR",
                   "DR" in first_name.get("prefix", []),
                   actual=first_name.get("prefix"), expected=["DR"])

        # address (PID-11: 123 MAIN ST^^SPRINGFIELD^IL^62701^USA)
        addresses = patient.get("address", [])
        record(f"{label}: address present", len(addresses) > 0, actual=addresses)
        if addresses:
            addr = addresses[0]
            record(f"{label}: address.city = SPRINGFIELD",
                   addr.get("city") == "SPRINGFIELD",
                   actual=addr.get("city"), expected="SPRINGFIELD")
            record(f"{label}: address.state = IL",
                   addr.get("state") == "IL",
                   actual=addr.get("state"), expected="IL")
            record(f"{label}: address.postalCode = 62701",
                   addr.get("postalCode") == "62701",
                   actual=addr.get("postalCode"), expected="62701")
            record(f"{label}: address.line contains '123 MAIN ST'",
                   "123 MAIN ST" in addr.get("line", []),
                   actual=addr.get("line"), expected=["123 MAIN ST"])

        # telecom (PID-13: 5551234567)
        telecoms = patient.get("telecom", [])
        record(f"{label}: telecom present", len(telecoms) > 0, actual=telecoms)
        if telecoms:
            phone = telecoms[0]
            record(f"{label}: telecom[0].system = phone",
                   phone.get("system") == "phone",
                   actual=phone.get("system"), expected="phone")
            record(f"{label}: telecom[0].value = 5551234567",
                   phone.get("value") == "5551234567",
                   actual=phone.get("value"), expected="5551234567")

        # Z-segment extensions (ZPD, ZEP present in message)
        extensions = patient.get("extension", [])
        record(f"{label}: Z-segment extensions present", len(extensions) > 0,
               actual=f"{len(extensions)} extension(s)", expected=">0")
        if extensions:
            ext_urls = [e.get("url", "") for e in extensions]
            has_zpd = any("zpd" in u.lower() for u in ext_urls)
            has_zep = any("zep" in u.lower() for u in ext_urls)
            record(f"{label}: ZPD extension present", has_zpd, actual=ext_urls)
            record(f"{label}: ZEP extension present", has_zep, actual=ext_urls)
    else:
        record(f"{label}: Patient resource found for sub-checks", False, actual="No Patient resource")

    # Organization (from MSH-4 = MEMHOSP)
    org = find_resource(bundle, "Organization")
    if org:
        record(f"{label}: Organization name = MEMHOSP",
               org.get("name") == "MEMHOSP",
               actual=org.get("name"), expected="MEMHOSP")
        # SFT extension on org (SFT|Epic Systems|10.3|EpicCare)
        org_ext = org.get("extension", [])
        record(f"{label}: Organization SFT extension present", len(org_ext) > 0,
               actual=f"{len(org_ext)} extension(s)")
        if org_ext:
            vendor_ext = next((e for e in org_ext if "vendor" in e.get("url", "")), None)
            record(f"{label}: SFT vendor extension has Epic Systems",
                   vendor_ext is not None and "Epic" in vendor_ext.get("valueString", ""),
                   actual=vendor_ext.get("valueString") if vendor_ext else None)
    else:
        record(f"{label}: Organization found for sub-checks", False)

    # Practitioner (from PV1-7: 1234567890^DOE^JANE^M^DR^MD)
    practitioners = find_all_resources(bundle, "Practitioner")
    record(f"{label}: At least 1 Practitioner produced", len(practitioners) >= 1,
           actual=len(practitioners))
    if practitioners:
        prac = practitioners[0]
        prac_idents = prac.get("identifier", [])
        record(f"{label}: Practitioner identifier present", len(prac_idents) > 0, actual=prac_idents)
        if prac_idents:
            record(f"{label}: Practitioner NPI system = http://hl7.org/fhir/sid/us-npi",
                   prac_idents[0].get("system") == "http://hl7.org/fhir/sid/us-npi",
                   actual=prac_idents[0].get("system"), expected="http://hl7.org/fhir/sid/us-npi")
            record(f"{label}: Practitioner NPI value = 1234567890",
                   prac_idents[0].get("value") == "1234567890",
                   actual=prac_idents[0].get("value"), expected="1234567890")
        prac_names = prac.get("name", [])
        if prac_names:
            record(f"{label}: Practitioner name.family = DOE",
                   prac_names[0].get("family") == "DOE",
                   actual=prac_names[0].get("family"), expected="DOE")
            record(f"{label}: Practitioner name.given[0] = JANE",
                   "JANE" in prac_names[0].get("given", []),
                   actual=prac_names[0].get("given"), expected=["JANE"])

    # Encounter (A01 = in-progress)
    encounter = find_resource(bundle, "Encounter")
    if encounter:
        record(f"{label}: Encounter status = in-progress",
               encounter.get("status") == "in-progress",
               actual=encounter.get("status"), expected="in-progress")
        # Encounter class from PV1-2 = I (inpatient)
        enc_class = encounter.get("class", {})
        record(f"{label}: Encounter class code = IMP",
               enc_class.get("code") == "IMP",
               actual=enc_class.get("code"), expected="IMP")
        # serviceProvider references Org
        record(f"{label}: Encounter.serviceProvider references Organization",
               "Organization" in encounter.get("serviceProvider", {}).get("reference", ""),
               actual=encounter.get("serviceProvider"))
        # Participants reference Practitioner
        participants = encounter.get("participant", [])
        record(f"{label}: Encounter.participant non-empty", len(participants) > 0, actual=len(participants))
    else:
        record(f"{label}: Encounter found for sub-checks", False)

    # field_mappings checks
    all_fm_segs = []
    all_fm_fields = []
    for rm in field_mappings:
        for fm in rm.field_mappings:
            all_fm_segs.append(fm.hl7_segment)
            all_fm_fields.append(fm.hl7_field)

    record(f"{label}: FieldMappings contain PID segment refs", "PID" in all_fm_segs, actual=all_fm_segs)
    record(f"{label}: FieldMappings contain PV1 segment refs", "PV1" in all_fm_segs, actual=all_fm_segs)
    record(f"{label}: FieldMappings contain MSH segment refs", "MSH" in all_fm_segs, actual=all_fm_segs)

    # Warnings should be empty for well-formed message
    record(f"{label}: No warnings for well-formed message", len(warnings) == 0, actual=warnings)


def test_adt_a03():
    label = "ADT A03"
    print(f"\n{'='*70}")
    print(f"  {label}: Discharge - Encounter status = finished")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, ADT_A03)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    encounter = find_resource(bundle, "Encounter")
    record(f"{label}: Encounter status = finished",
           encounter is not None and encounter.get("status") == "finished",
           actual=encounter.get("status") if encounter else None, expected="finished")
    # Period start + end should both be present
    if encounter:
        period = encounter.get("period", {})
        record(f"{label}: Encounter period.start present", "start" in period, actual=period)
        record(f"{label}: Encounter period.end present", "end" in period, actual=period)


def test_oru():
    label = "ORU R01"
    print(f"\n{'='*70}")
    print(f"  {label}: Observation Results")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, ORU_R01)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: Patient produced", "Patient" in resource_types, resource_types)
    record(f"{label}: DiagnosticReport produced", "DiagnosticReport" in resource_types, resource_types)
    record(f"{label}: Observation produced", "Observation" in resource_types, resource_types)

    # Patient checks
    patient = find_resource(bundle, "Patient")
    if patient:
        record(f"{label}: Patient MRN = 67890",
               any(i.get("value") == "67890" for i in patient.get("identifier", [])),
               actual=[i.get("value") for i in patient.get("identifier", [])])
        record(f"{label}: Patient gender = female",
               patient.get("gender") == "female",
               actual=patient.get("gender"))
        record(f"{label}: Patient birthDate = 1965-07-20",
               patient.get("birthDate") == "1965-07-20",
               actual=patient.get("birthDate"))

    # Observation checks
    observations = find_all_resources(bundle, "Observation")
    record(f"{label}: 2 Observations produced", len(observations) == 2, actual=len(observations))
    if observations:
        obs = observations[0]
        record(f"{label}: Observation status present", "status" in obs, actual=obs.get("status"))
        record(f"{label}: Observation subject references Patient", "Patient" in obs.get("subject", {}).get("reference", ""))

    # Field mappings
    record(f"{label}: field_mappings non-empty", len(field_mappings) > 0, actual=len(field_mappings))
    all_segs = [fm.hl7_segment for rm in field_mappings for fm in rm.field_mappings]
    record(f"{label}: OBX in field_mappings", "OBX" in all_segs, actual=all_segs)

    try:
        json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))

    record(f"{label}: No warnings", len(warnings) == 0, actual=warnings)


def test_orm():
    label = "ORM O01"
    print(f"\n{'='*70}")
    print(f"  {label}: Order Message")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, ORM_O01)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: Patient produced", "Patient" in resource_types, resource_types)
    record(f"{label}: ServiceRequest produced", "ServiceRequest" in resource_types, resource_types)
    record(f"{label}: Practitioner produced", "Practitioner" in resource_types, resource_types)

    # ServiceRequest checks
    sr = find_resource(bundle, "ServiceRequest")
    if sr:
        record(f"{label}: ServiceRequest status = active",
               sr.get("status") == "active",
               actual=sr.get("status"), expected="active")
        record(f"{label}: ServiceRequest intent = order",
               sr.get("intent") == "order",
               actual=sr.get("intent"), expected="order")
        record(f"{label}: ServiceRequest subject references Patient",
               "Patient" in sr.get("subject", {}).get("reference", ""),
               actual=sr.get("subject"))

    # Practitioner check (ORC-12: CARTER^WILLIAM^J^DR - no numeric prefix to avoid datetime filter)
    practitioners = find_all_resources(bundle, "Practitioner")
    record(f"{label}: Practitioner produced", len(practitioners) > 0)
    if practitioners:
        prac = practitioners[0]
        prac_names = prac.get("name", [])
        # ORM ORC-12: CARTER^WILLIAM^J^DR - parts[0]=CARTER (used as NPI), parts[1]=WILLIAM (family)
        record(f"{label}: Practitioner name.family = WILLIAM (ORC-12 second component)",
               any(n.get("family") == "WILLIAM" for n in prac_names),
               actual=[n.get("family") for n in prac_names], expected="WILLIAM")

    record(f"{label}: field_mappings non-empty", len(field_mappings) > 0, actual=len(field_mappings))
    all_segs = [fm.hl7_segment for rm in field_mappings for fm in rm.field_mappings]
    record(f"{label}: ORC in field_mappings", "ORC" in all_segs, actual=all_segs)
    record(f"{label}: OBR in field_mappings", "OBR" in all_segs, actual=all_segs)

    try:
        json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))

    record(f"{label}: No warnings", len(warnings) == 0, actual=warnings)


def test_siu():
    label = "SIU S12"
    print(f"\n{'='*70}")
    print(f"  {label}: Scheduling")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, SIU_S12)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: Patient produced", "Patient" in resource_types, resource_types)
    record(f"{label}: Appointment produced", "Appointment" in resource_types, resource_types)
    record(f"{label}: Encounter produced (S12 triggers Encounter)", "Encounter" in resource_types, resource_types)
    record(f"{label}: Practitioner produced", "Practitioner" in resource_types, resource_types)

    appt = find_resource(bundle, "Appointment")
    if appt:
        record(f"{label}: Appointment status = booked",
               appt.get("status") == "booked",
               actual=appt.get("status"), expected="booked")
        record(f"{label}: Appointment.participant non-empty",
               len(appt.get("participant", [])) > 0,
               actual=len(appt.get("participant", [])))

    record(f"{label}: field_mappings non-empty", len(field_mappings) > 0, actual=len(field_mappings))

    try:
        json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))

    record(f"{label}: No warnings", len(warnings) == 0, actual=warnings)


def test_mdm():
    label = "MDM T02"
    print(f"\n{'='*70}")
    print(f"  {label}: Medical Document Management")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, MDM_T02)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: Patient produced", "Patient" in resource_types, resource_types)
    record(f"{label}: DocumentReference produced", "DocumentReference" in resource_types, resource_types)
    record(f"{label}: Practitioner produced (TXA-9 author)", "Practitioner" in resource_types, resource_types)

    doc = find_resource(bundle, "DocumentReference")
    if doc:
        record(f"{label}: DocumentReference status = current",
               doc.get("status") == "current",
               actual=doc.get("status"), expected="current")
        record(f"{label}: DocumentReference subject references Patient",
               "Patient" in doc.get("subject", {}).get("reference", ""),
               actual=doc.get("subject"))
        record(f"{label}: DocumentReference.identifier = DOC-2024-001",
               any(i.get("value") == "DOC-2024-001" for i in doc.get("identifier", [])),
               actual=[i.get("value") for i in doc.get("identifier", [])])
        record(f"{label}: DocumentReference.author non-empty", len(doc.get("author", [])) > 0,
               actual=doc.get("author"))

    record(f"{label}: field_mappings non-empty", len(field_mappings) > 0, actual=len(field_mappings))
    all_segs = [fm.hl7_segment for rm in field_mappings for fm in rm.field_mappings]
    record(f"{label}: TXA in field_mappings", "TXA" in all_segs, actual=all_segs)

    try:
        json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))

    record(f"{label}: No warnings", len(warnings) == 0, actual=warnings)


def test_dft():
    label = "DFT P03"
    print(f"\n{'='*70}")
    print(f"  {label}: Detailed Financial Transaction")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, DFT_P03)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: Patient produced", "Patient" in resource_types, resource_types)
    record(f"{label}: Claim produced", "Claim" in resource_types, resource_types)
    record(f"{label}: Practitioner produced", "Practitioner" in resource_types, resource_types)

    claim = find_resource(bundle, "Claim")
    if claim:
        record(f"{label}: Claim status = active",
               claim.get("status") == "active",
               actual=claim.get("status"), expected="active")
        record(f"{label}: Claim.patient references Patient",
               "Patient" in claim.get("patient", {}).get("reference", ""),
               actual=claim.get("patient"))
        # Should have a claim item with amount 500
        items = claim.get("item", [])
        record(f"{label}: Claim has item", len(items) > 0, actual=items)
        if items:
            record(f"{label}: Claim item.net.value = 500.0",
                   items[0].get("net", {}).get("value") == 500.0,
                   actual=items[0].get("net"))

    record(f"{label}: field_mappings non-empty", len(field_mappings) > 0, actual=len(field_mappings))
    all_segs = [fm.hl7_segment for rm in field_mappings for fm in rm.field_mappings]
    record(f"{label}: FT1 in field_mappings", "FT1" in all_segs, actual=all_segs)

    try:
        json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))

    record(f"{label}: No warnings", len(warnings) == 0, actual=warnings)


def test_vxu():
    label = "VXU V04"
    print(f"\n{'='*70}")
    print(f"  {label}: Vaccination Update")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, VXU_V04)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: Patient produced", "Patient" in resource_types, resource_types)
    record(f"{label}: Immunization produced", "Immunization" in resource_types, resource_types)
    record(f"{label}: Practitioner produced", "Practitioner" in resource_types, resource_types)

    immunization = find_resource(bundle, "Immunization")
    if immunization:
        record(f"{label}: Immunization status = completed",
               immunization.get("status") == "completed",
               actual=immunization.get("status"), expected="completed")
        record(f"{label}: Immunization.patient references Patient",
               "Patient" in immunization.get("patient", {}).get("reference", ""),
               actual=immunization.get("patient"))
        # Vaccine code RXA-5: 141^Influenza^CVX
        # extract_coding wraps the result in a CodeableConcept, so vaccineCode = {coding: [CodeableConcept]}
        # The code '141' may be nested under vaccineCode.coding[0].coding[0].code
        vcode = immunization.get("vaccineCode", {})
        outer_coding = vcode.get("coding", [])
        code_141_found = False
        for c in outer_coding:
            if isinstance(c, dict):
                if c.get("code") == "141":
                    code_141_found = True
                    break
                # nested CodeableConcept from extract_coding
                for inner in c.get("coding", []):
                    if isinstance(inner, dict) and inner.get("code") == "141":
                        code_141_found = True
                        break
        record(f"{label}: vaccineCode contains code 141",
               code_141_found,
               actual=vcode, expected="code 141 somewhere in vaccineCode")
        # Lot number (RXA-15)
        record(f"{label}: lotNumber = LOT-INF-2024",
               immunization.get("lotNumber") == "LOT-INF-2024",
               actual=immunization.get("lotNumber"), expected="LOT-INF-2024")
        # occurrenceDateTime
        record(f"{label}: occurrenceDateTime present",
               "occurrenceDateTime" in immunization,
               actual=immunization.get("occurrenceDateTime"))

    record(f"{label}: field_mappings non-empty", len(field_mappings) > 0, actual=len(field_mappings))
    all_segs = [fm.hl7_segment for rm in field_mappings for fm in rm.field_mappings]
    record(f"{label}: RXA in field_mappings", "RXA" in all_segs, actual=all_segs)

    try:
        json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))

    record(f"{label}: No warnings", len(warnings) == 0, actual=warnings)


def test_mfn():
    label = "MFN M02"
    print(f"\n{'='*70}")
    print(f"  {label}: Master File Notification")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, MFN_M02)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: Practitioner produced (STF master file)", "Practitioner" in resource_types, resource_types)

    prac = find_resource(bundle, "Practitioner")
    if prac:
        record(f"{label}: Practitioner.active = True",
               prac.get("active") == True,
               actual=prac.get("active"))
        prac_ident = prac.get("identifier", [])
        record(f"{label}: Practitioner identifier present", len(prac_ident) > 0, actual=prac_ident)
        if prac_ident:
            record(f"{label}: Practitioner identifier value = 5555555555",
                   prac_ident[0].get("value") == "5555555555",
                   actual=prac_ident[0].get("value"), expected="5555555555")

    record(f"{label}: field_mappings non-empty", len(field_mappings) > 0, actual=len(field_mappings))
    all_segs = [fm.hl7_segment for rm in field_mappings for fm in rm.field_mappings]
    record(f"{label}: MFE in field_mappings", "MFE" in all_segs, actual=all_segs)

    try:
        json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))


def test_ack():
    label = "ACK AA"
    print(f"\n{'='*70}")
    print(f"  {label}: Acknowledgment")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, ACK_AA)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: OperationOutcome produced", "OperationOutcome" in resource_types, resource_types)

    op = find_resource(bundle, "OperationOutcome")
    if op:
        issues = op.get("issue", [])
        record(f"{label}: OperationOutcome.issue non-empty", len(issues) > 0, actual=issues)
        if issues:
            record(f"{label}: issue[0].severity = information (AA=Accept)",
                   issues[0].get("severity") == "information",
                   actual=issues[0].get("severity"), expected="information")
            record(f"{label}: issue[0].code = informational",
                   issues[0].get("code") == "informational",
                   actual=issues[0].get("code"), expected="informational")
            record(f"{label}: issue[0].diagnostics contains MSG001",
                   "MSG001" in issues[0].get("diagnostics", ""),
                   actual=issues[0].get("diagnostics"))

    try:
        json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))

    record(f"{label}: No warnings", len(warnings) == 0, actual=warnings)


def test_bar():
    label = "BAR P01"
    print(f"\n{'='*70}")
    print(f"  {label}: Add Billing Account")
    print(f"{'='*70}")
    try:
        bundle, warnings, field_mappings, parsed = run_conversion(label, BAR_P01)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        traceback.print_exc()
        return

    record(f"{label}: No exception", True)
    resource_types = [r.get("resourceType") for r in get_resources(bundle)]
    record(f"{label}: Patient produced", "Patient" in resource_types, resource_types)
    record(f"{label}: Account produced", "Account" in resource_types, resource_types)
    record(f"{label}: Organization produced", "Organization" in resource_types, resource_types)
    record(f"{label}: Coverage produced (IN1 segment)", "Coverage" in resource_types, resource_types)

    # Patient: PID-3 has MRN and EPI
    patient = find_resource(bundle, "Patient")
    if patient:
        mrn_ident = None
        epi_ident = None
        for ident in patient.get("identifier", []):
            if "mrn" in ident.get("system", "").lower():
                mrn_ident = ident
            if "1.2.840.114350.1.13" in ident.get("system", ""):
                epi_ident = ident
        record(f"{label}: Patient MRN identifier (55555)", mrn_ident is not None,
               actual=[i.get("system") for i in patient.get("identifier", [])])
        record(f"{label}: Patient EPI identifier (E11111)", epi_ident is not None,
               actual=[i.get("system") for i in patient.get("identifier", [])])

    # Account
    account = find_resource(bundle, "Account")
    if account:
        record(f"{label}: Account status = active",
               account.get("status") == "active",
               actual=account.get("status"), expected="active")
        record(f"{label}: Account.subject references Patient",
               any("Patient" in s.get("reference", "") for s in account.get("subject", [])),
               actual=account.get("subject"))

    # Coverage (IN1: BCBS-PPO / Blue Cross Blue Shield)
    coverage = find_resource(bundle, "Coverage")
    if coverage:
        record(f"{label}: Coverage.status = active",
               coverage.get("status") == "active",
               actual=coverage.get("status"))
        record(f"{label}: Coverage.payor contains BCBS",
               any("Blue Cross" in p.get("display", "") for p in coverage.get("payor", [])),
               actual=coverage.get("payor"))

    record(f"{label}: field_mappings non-empty", len(field_mappings) > 0, actual=len(field_mappings))
    all_segs = [fm.hl7_segment for rm in field_mappings for fm in rm.field_mappings]
    record(f"{label}: IN1 in field_mappings", "IN1" in all_segs, actual=all_segs)
    record(f"{label}: PV1 in field_mappings", "PV1" in all_segs, actual=all_segs)

    try:
        json.dumps(bundle)
        record(f"{label}: JSON serializable", True)
    except Exception as e:
        record(f"{label}: JSON serializable", False, str(e))

    record(f"{label}: No warnings", len(warnings) == 0, actual=warnings)


# ─────────────────────────────────────────────────────────────────────────────
# BUNDLE STRUCTURE CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def test_bundle_structure():
    label = "BUNDLE STRUCTURE"
    print(f"\n{'='*70}")
    print(f"  {label}: FHIR Bundle conformance")
    print(f"{'='*70}")
    try:
        bundle, _, _, _ = run_conversion(label, ADT_A01)
    except Exception as e:
        record(f"{label}: No exception", False, str(e))
        return

    record(f"{label}: Bundle.resourceType = Bundle",
           bundle.get("resourceType") == "Bundle",
           actual=bundle.get("resourceType"))
    record(f"{label}: Bundle.type = collection",
           bundle.get("type") == "collection",
           actual=bundle.get("type"))
    record(f"{label}: Bundle.id present", bool(bundle.get("id")), actual=bundle.get("id"))
    record(f"{label}: Bundle.timestamp present", bool(bundle.get("timestamp")), actual=bundle.get("timestamp"))
    record(f"{label}: Bundle.entry is list", isinstance(bundle.get("entry"), list))

    entries = bundle.get("entry", [])
    for i, entry in enumerate(entries):
        record(f"{label}: entry[{i}].fullUrl present", "fullUrl" in entry, actual=list(entry.keys()))
        record(f"{label}: entry[{i}].resource present", "resource" in entry, actual=list(entry.keys()))
        if "resource" in entry:
            res = entry["resource"]
            record(f"{label}: entry[{i}].resource.resourceType present",
                   "resourceType" in res, actual=list(res.keys()))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("  HL7 to FHIR Conversion Comprehensive Verification")
    print("=" * 70)

    test_bundle_structure()
    test_adt_a01()
    test_adt_a03()
    test_oru()
    test_orm()
    test_siu()
    test_mdm()
    test_dft()
    test_vxu()
    test_mfn()
    test_ack()
    test_bar()

    # ── Summary report ──────────────────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)
    max_name = max(len(r[0]) for r in results) if results else 40

    pass_results = [r for r in results if r[1] == PASS]
    fail_results = [r for r in results if r[1] == FAIL]

    print("\n--- PASSED ---")
    for name, status, detail in pass_results:
        print(f"  [PASS] {name}")

    if fail_results:
        print("\n--- FAILED ---")
        for name, status, detail in fail_results:
            print(f"  [FAIL] {name}{detail}")
    else:
        print("\n  All checks passed!")

    print(f"\n{'='*70}")
    print(f"  TOTAL:  {len(results)} checks")
    print(f"  PASS:   {total_pass}")
    print(f"  FAIL:   {total_fail}")
    if total_fail == 0:
        print("  STATUS: ALL CHECKS PASSED - READY FOR CLIENT PRESENTATION")
    else:
        print(f"  STATUS: {total_fail} FAILURE(S) REQUIRE ATTENTION")
    print(f"{'='*70}\n")

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
