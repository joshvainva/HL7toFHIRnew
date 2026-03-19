"""
Comprehensive FHIR → HL7 verification test.
Run from project root: python tmp_fhir_to_hl7_verify.py
"""
import sys
sys.path.insert(0, ".")

from app.converters.fhir_to_hl7.adt import ADTtoHL7Converter
from app.converters.fhir_to_hl7.oru import ORUtoHL7Converter
from app.converters.fhir_to_hl7.orm import ORMtoHL7Converter
from app.core.fhir_mapper import detect_message_type

passes = []
failures = []

def check(name, condition, actual=""):
    if condition:
        passes.append(f"  [PASS] {name}")
    else:
        failures.append(f"  [FAIL] {name}  => got: {repr(actual)}")

def seg(msg, name):
    for s in msg.split("\r"):
        if s.startswith(name + "|"):
            return s.split("|")
    return []

def all_segs(msg, name):
    return [s.split("|") for s in msg.split("\r") if s.startswith(name + "|")]

# ============================================================
# ADT Bundle
# ============================================================
adt_bundle = {
    "resourceType": "Bundle", "type": "collection",
    "entry": [
        {"resource": {
            "resourceType": "Patient", "id": "p1",
            "identifier": [
                {"system": "urn:oid:1.2.840.114350.1.13", "value": "E98765",
                 "type": {"coding": [{"code": "EPI"}]}},
                {"system": "http://hospital.example.org/mrn", "value": "12345",
                 "type": {"coding": [{"code": "MR"}]}}
            ],
            "name": [{"use": "official", "family": "SMITH", "given": ["JOHN", "A"],
                      "suffix": ["JR"], "prefix": ["DR"]}],
            "birthDate": "1980-05-15",
            "gender": "male",
            "address": [{"line": ["123 MAIN ST"], "city": "SPRINGFIELD",
                         "state": "IL", "postalCode": "62701", "country": "USA"}],
            "telecom": [
                {"system": "phone", "value": "5551234567", "use": "home"},
                {"system": "email", "value": "john@test.com"}
            ],
            "maritalStatus": {"coding": [{"code": "M"}]},
        }},
        {"resource": {"resourceType": "Organization", "id": "o1", "name": "MEMHOSP"}},
        {"resource": {
            "resourceType": "Practitioner", "id": "pr1",
            "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "1234567890"}],
            "name": [{"family": "DOE", "given": ["JANE"]}]
        }},
        {"resource": {
            "resourceType": "Encounter", "id": "e1",
            "status": "in-progress",
            "class": {"code": "IMP", "display": "inpatient encounter"},
            "identifier": [{"value": "V20240315001"}],
            "period": {"start": "2024-03-15T14:30:00"},
            "participant": [
                {"type": [{"coding": [{"code": "ATND"}]}],
                 "individual": {"reference": "Practitioner/pr1"}}
            ],
        }},
    ]
}

# ADT A03 (discharge)
adt_discharge = {
    "resourceType": "Bundle", "type": "collection",
    "entry": [
        {"resource": {"resourceType": "Patient", "id": "p9",
            "identifier": [{"system": "http://hospital.example.org/mrn", "value": "99999"}],
            "name": [{"family": "TEST"}], "gender": "unknown"
        }},
        {"resource": {"resourceType": "Encounter", "id": "e9",
            "status": "finished",
            "class": {"code": "IMP"},
            "period": {"start": "2024-03-14T08:00:00", "end": "2024-03-15T16:00:00"}
        }},
    ]
}

print("=" * 70)
print("  FHIR → HL7 Comprehensive Verification")
print("=" * 70)

# ---- Run ADT ----
adt_msg = ADTtoHL7Converter().convert(adt_bundle)
print("\n--- ADT (A01 Inpatient Admit) ---")
for s in adt_msg.split("\r"):
    print(s)

msh = seg(adt_msg, "MSH")
evn = seg(adt_msg, "EVN")
pid = seg(adt_msg, "PID")
pv1 = seg(adt_msg, "PV1")

print("\n--- ADT Checks ---")
check("detect_message_type = ADT", detect_message_type(adt_bundle) == "ADT")
check("MSH present", bool(msh))
check("MSH-9 = ADT^A01", len(msh) > 8 and msh[8] == "ADT^A01", msh[8] if len(msh) > 8 else "")
check("MSH-4 facility = MEMHOSP", len(msh) > 3 and msh[3] == "MEMHOSP", msh[3] if len(msh) > 3 else "")
check("MSH-12 version = 2.5", len(msh) > 11 and msh[11] == "2.5", msh[11] if len(msh) > 11 else "")
check("EVN present", bool(evn))
check("EVN-1 event code = A01", len(evn) > 1 and evn[1] == "A01", evn[1] if len(evn) > 1 else "")
check("EVN-2 datetime 14 chars", len(evn) > 2 and len(evn[2]) == 14, evn[2] if len(evn) > 2 else "")
check("EVN-2 starts with 20240315", len(evn) > 2 and evn[2].startswith("20240315"), evn[2] if len(evn) > 2 else "")

check("PID present", bool(pid))
pid3 = pid[3] if len(pid) > 3 else ""
check("PID-3 has EPI value E98765", "E98765" in pid3, pid3)
check("PID-3 EPI has type code EPI", "EPI" in pid3, pid3)
check("PID-3 has MRN value 12345", "12345" in pid3, pid3)
check("PID-3 MRN has type code MR", "MR" in pid3, pid3)
check("PID-3 uses ~ repeat separator for multiple IDs", "~" in pid3, pid3)
pid5 = pid[5] if len(pid) > 5 else ""
check("PID-5 family = SMITH", "SMITH" in pid5, pid5)
check("PID-5 given = JOHN", "JOHN" in pid5, pid5)
check("PID-5 suffix = JR", "JR" in pid5, pid5)
check("PID-5 prefix = DR", "DR" in pid5, pid5)
pid7 = pid[7] if len(pid) > 7 else ""
check("PID-7 DOB = 19800515", pid7 == "19800515", pid7)
pid8 = pid[8] if len(pid) > 8 else ""
check("PID-8 gender = M", pid8 == "M", pid8)
pid11 = pid[11] if len(pid) > 11 else ""
check("PID-11 street = 123 MAIN ST", "123 MAIN ST" in pid11, pid11)
check("PID-11 city = SPRINGFIELD", "SPRINGFIELD" in pid11, pid11)
check("PID-11 state = IL", "IL" in pid11, pid11)
check("PID-11 zip = 62701", "62701" in pid11, pid11)
pid13 = pid[13] if len(pid) > 13 else ""
check("PID-13 phone = 5551234567", "5551234567" in pid13, pid13)
check("PID-13 phone type = PRN^PH", "PRN^PH" in pid13, pid13)
check("PID-13 email present", "john@test.com" in pid13, pid13)
check("PID-13 email type = NET^Internet", "NET^Internet" in pid13, pid13)
pid16 = pid[16] if len(pid) > 16 else ""
check("PID-16 marital status = M (not full URI)", pid16 == "M", pid16)

check("PV1 present", bool(pv1))
check("PV1-2 patient class = I", len(pv1) > 2 and pv1[2] == "I", pv1[2] if len(pv1) > 2 else "")
pv1_7 = pv1[7] if len(pv1) > 7 else ""
check("PV1-7 attending NPI = 1234567890", "1234567890" in pv1_7, pv1_7)
check("PV1-7 attending family = DOE", "DOE" in pv1_7, pv1_7)
check("PV1-7 attending given = JANE", "JANE" in pv1_7, pv1_7)
pv1_19 = pv1[19] if len(pv1) > 19 else ""
check("PV1-19 visit = V20240315001", pv1_19 == "V20240315001", pv1_19)
pv1_44 = pv1[44] if len(pv1) > 44 else ""
check("PV1-44 admit datetime 14 chars", len(pv1_44) == 14, pv1_44)
check("PV1-44 = 20240315143000", pv1_44 == "20240315143000", pv1_44)

# ---- ADT A03 discharge ----
dis_msg = ADTtoHL7Converter().convert(adt_discharge)
print("\n--- ADT (A03 Discharge) ---")
for s in dis_msg.split("\r"):
    print(s)
msh_d = seg(dis_msg, "MSH")
pv1_d = seg(dis_msg, "PV1")
check("ADT A03: MSH-9 = ADT^A03", len(msh_d) > 8 and msh_d[8] == "ADT^A03", msh_d[8] if len(msh_d) > 8 else "")
check("ADT A03: PV1-44 admit = 20240314080000", len(pv1_d) > 44 and pv1_d[44] == "20240314080000", pv1_d[44] if len(pv1_d) > 44 else "")
check("ADT A03: PV1-45 discharge = 20240315160000", len(pv1_d) > 45 and pv1_d[45] == "20240315160000", pv1_d[45] if len(pv1_d) > 45 else "")

# ============================================================
# ORU Bundle
# ============================================================
oru_bundle = {
    "resourceType": "Bundle", "type": "collection",
    "entry": [
        {"resource": {"resourceType": "Patient", "id": "p2",
            "identifier": [{"system": "http://hospital.example.org/mrn", "value": "67890"}],
            "name": [{"family": "JONES", "given": ["MARY"]}],
            "birthDate": "1965-07-20", "gender": "female"
        }},
        {"resource": {"resourceType": "Organization", "id": "o2", "name": "LABHOSP"}},
        {"resource": {"resourceType": "Practitioner", "id": "pr2",
            "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "9876543210"}],
            "name": [{"family": "LEE", "given": ["CHEN"]}]
        }},
        {"resource": {"resourceType": "DiagnosticReport", "id": "dr1",
            "status": "final",
            "code": {"coding": [{"code": "718-7", "display": "Hemoglobin", "system": "http://loinc.org"}]},
            "identifier": [
                {"type": {"coding": [{"code": "FILL"}]}, "value": "REQ001"},
                {"type": {"coding": [{"code": "PLAC"}]}, "value": "ORD001"}
            ],
            "effectiveDateTime": "2024-03-15T11:00:00",
            "issued": "2024-03-15T11:55:00",
            "result": [{"reference": "Observation/ob1"}, {"reference": "Observation/ob2"}],
            "performer": [{"reference": "Practitioner/pr2"}]
        }},
        {"resource": {"resourceType": "Observation", "id": "ob1",
            "status": "final",
            "code": {"coding": [{"code": "718-7", "display": "Hemoglobin", "system": "http://loinc.org"}]},
            "valueQuantity": {"value": 13.5, "unit": "g/dL", "system": "http://unitsofmeasure.org"},
            "referenceRange": [{"text": "12.0-17.5"}],
            "interpretation": [{"coding": [{"code": "N"}]}],
            "effectiveDateTime": "2024-03-15T11:00:00"
        }},
        {"resource": {"resourceType": "Observation", "id": "ob2",
            "status": "final",
            "code": {"coding": [{"code": "4544-3", "display": "Hematocrit", "system": "http://loinc.org"}]},
            "valueQuantity": {"value": 41.2, "unit": "%", "system": "http://unitsofmeasure.org"},
            "referenceRange": [{"text": "36.0-52.0"}],
            "interpretation": [{"coding": [{"code": "N"}]}],
            "effectiveDateTime": "2024-03-15T11:00:00"
        }},
    ]
}

oru_msg = ORUtoHL7Converter().convert(oru_bundle)
print("\n--- ORU (R01 Lab Results) ---")
for s in oru_msg.split("\r"):
    print(s)

msh_o = seg(oru_msg, "MSH")
pid_o = seg(oru_msg, "PID")
obr_o = seg(oru_msg, "OBR")
obx_list = all_segs(oru_msg, "OBX")

print("\n--- ORU Checks ---")
check("detect_message_type = ORU", detect_message_type(oru_bundle) == "ORU")
check("ORU MSH-9 = ORU^R01", len(msh_o) > 8 and msh_o[8] == "ORU^R01", msh_o[8] if len(msh_o) > 8 else "")
check("ORU PID-3 MRN = 67890", len(pid_o) > 3 and "67890" in pid_o[3], pid_o[3] if len(pid_o) > 3 else "")
check("ORU PID-5 family = JONES", len(pid_o) > 5 and "JONES" in pid_o[5], pid_o[5] if len(pid_o) > 5 else "")
check("ORU PID-7 DOB = 19650720", len(pid_o) > 7 and pid_o[7] == "19650720", pid_o[7] if len(pid_o) > 7 else "")
check("ORU PID-8 gender = F", len(pid_o) > 8 and pid_o[8] == "F", pid_o[8] if len(pid_o) > 8 else "")
check("ORU OBR present", bool(obr_o))
check("ORU OBR-2 placer = ORD001", len(obr_o) > 2 and obr_o[2] == "ORD001", obr_o[2] if len(obr_o) > 2 else "")
check("ORU OBR-3 filler = REQ001", len(obr_o) > 3 and obr_o[3] == "REQ001", obr_o[3] if len(obr_o) > 3 else "")
check("ORU OBR-4 code = 718-7^Hemoglobin^LN", len(obr_o) > 4 and "718-7" in obr_o[4] and "LN" in obr_o[4], obr_o[4] if len(obr_o) > 4 else "")
check("ORU OBR-7 obs datetime present", len(obr_o) > 7 and obr_o[7].startswith("20240315"), obr_o[7] if len(obr_o) > 7 else "")
check("ORU OBR-16 provider NPI = 9876543210", len(obr_o) > 16 and "9876543210" in obr_o[16], obr_o[16] if len(obr_o) > 16 else "")
check("ORU OBR-16 provider family = LEE", len(obr_o) > 16 and "LEE" in obr_o[16], obr_o[16] if len(obr_o) > 16 else "")
check("ORU OBR-25 status = F", len(obr_o) > 25 and obr_o[25] == "F", obr_o[25] if len(obr_o) > 25 else "")
check("ORU 2 OBX segments", len(obx_list) == 2, len(obx_list))
if len(obx_list) >= 1:
    obx1 = obx_list[0]
    check("ORU OBX1-2 type = NM", len(obx1) > 2 and obx1[2] == "NM", obx1[2] if len(obx1) > 2 else "")
    check("ORU OBX1-3 code = 718-7", len(obx1) > 3 and "718-7" in obx1[3], obx1[3] if len(obx1) > 3 else "")
    check("ORU OBX1-3 system = LN", len(obx1) > 3 and "LN" in obx1[3], obx1[3] if len(obx1) > 3 else "")
    check("ORU OBX1-5 value = 13.5", len(obx1) > 5 and obx1[5] == "13.5", obx1[5] if len(obx1) > 5 else "")
    check("ORU OBX1-6 units = g/dL", len(obx1) > 6 and "g/dL" in obx1[6], obx1[6] if len(obx1) > 6 else "")
    check("ORU OBX1-7 ref range = 12.0-17.5", len(obx1) > 7 and "12.0-17.5" in obx1[7], obx1[7] if len(obx1) > 7 else "")
    check("ORU OBX1-8 interp = N", len(obx1) > 8 and obx1[8] == "N", obx1[8] if len(obx1) > 8 else "")
    check("ORU OBX1-11 status = F", len(obx1) > 11 and obx1[11] == "F", obx1[11] if len(obx1) > 11 else "")
    check("ORU OBX1-14 eff datetime present", len(obx1) > 14 and obx1[14].startswith("20240315"), obx1[14] if len(obx1) > 14 else "")
if len(obx_list) >= 2:
    obx2 = obx_list[1]
    check("ORU OBX2-3 code = 4544-3", len(obx2) > 3 and "4544-3" in obx2[3], obx2[3] if len(obx2) > 3 else "")
    check("ORU OBX2-5 value = 41.2", len(obx2) > 5 and obx2[5] == "41.2", obx2[5] if len(obx2) > 5 else "")

# ============================================================
# ORM Bundle
# ============================================================
orm_bundle = {
    "resourceType": "Bundle", "type": "collection",
    "entry": [
        {"resource": {"resourceType": "Patient", "id": "p3",
            "identifier": [{"system": "http://hospital.example.org/mrn", "value": "PT555"}],
            "name": [{"family": "WILSON", "given": ["PATRICIA"]}],
            "birthDate": "1970-01-01", "gender": "female"
        }},
        {"resource": {"resourceType": "Practitioner", "id": "pr3",
            "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "1122334455"}],
            "name": [{"family": "TAYLOR", "given": ["MICHAEL"]}]
        }},
        {"resource": {"resourceType": "ServiceRequest", "id": "sr1",
            "status": "active", "intent": "order",
            "identifier": [
                {"type": {"coding": [{"code": "PLAC"}]}, "value": "ORD20240315001"},
                {"type": {"coding": [{"code": "FILL"}]}, "value": "FILL20240315001"}
            ],
            "code": {"coding": [{"code": "TSH", "display": "Thyroid Stimulating Hormone", "system": "http://loinc.org"}]},
            "priority": "routine",
            "authoredOn": "2024-03-15T14:00:00",
            "requester": {"reference": "Practitioner/pr3"}
        }},
    ]
}

orm_msg = ORMtoHL7Converter().convert(orm_bundle)
print("\n--- ORM (O01 Lab Order) ---")
for s in orm_msg.split("\r"):
    print(s)

msh_rm = seg(orm_msg, "MSH")
pid_rm = seg(orm_msg, "PID")
orc_rm = seg(orm_msg, "ORC")
obr_rm = seg(orm_msg, "OBR")

print("\n--- ORM Checks ---")
check("detect_message_type = ORM", detect_message_type(orm_bundle) == "ORM")
check("ORM MSH-9 = ORM^O01", len(msh_rm) > 8 and msh_rm[8] == "ORM^O01", msh_rm[8] if len(msh_rm) > 8 else "")
check("ORM PID-3 MRN = PT555", len(pid_rm) > 3 and "PT555" in pid_rm[3], pid_rm[3] if len(pid_rm) > 3 else "")
check("ORM PID-5 family = WILSON", len(pid_rm) > 5 and "WILSON" in pid_rm[5], pid_rm[5] if len(pid_rm) > 5 else "")
check("ORM PID-7 DOB = 19700101", len(pid_rm) > 7 and pid_rm[7] == "19700101", pid_rm[7] if len(pid_rm) > 7 else "")
check("ORM PID-8 gender = F", len(pid_rm) > 8 and pid_rm[8] == "F", pid_rm[8] if len(pid_rm) > 8 else "")
check("ORM ORC present", bool(orc_rm))
check("ORM ORC-1 = NW", len(orc_rm) > 1 and orc_rm[1] == "NW", orc_rm[1] if len(orc_rm) > 1 else "")
check("ORM ORC-2 placer = ORD20240315001", len(orc_rm) > 2 and orc_rm[2] == "ORD20240315001", orc_rm[2] if len(orc_rm) > 2 else "")
check("ORM ORC-3 filler = FILL20240315001", len(orc_rm) > 3 and orc_rm[3] == "FILL20240315001", orc_rm[3] if len(orc_rm) > 3 else "")
check("ORM ORC-9 authored datetime", len(orc_rm) > 9 and orc_rm[9].startswith("20240315"), orc_rm[9] if len(orc_rm) > 9 else "")
check("ORM ORC-12 requester NPI = 1122334455", len(orc_rm) > 12 and "1122334455" in orc_rm[12], orc_rm[12] if len(orc_rm) > 12 else "")
check("ORM ORC-12 requester family = TAYLOR", len(orc_rm) > 12 and "TAYLOR" in orc_rm[12], orc_rm[12] if len(orc_rm) > 12 else "")
check("ORM OBR-4 code = TSH", len(obr_rm) > 4 and "TSH" in obr_rm[4], obr_rm[4] if len(obr_rm) > 4 else "")
check("ORM OBR-4 system = LN", len(obr_rm) > 4 and "LN" in obr_rm[4], obr_rm[4] if len(obr_rm) > 4 else "")
check("ORM OBR-5 priority = R", len(obr_rm) > 5 and obr_rm[5] == "R", obr_rm[5] if len(obr_rm) > 5 else "")

# ============================================================
# Results
# ============================================================
print("\n" + "=" * 70)
print(f"  TOTAL: {len(passes)+len(failures)}   PASS: {len(passes)}   FAIL: {len(failures)}")
print("=" * 70)
for p in passes:
    print(p)
for f in failures:
    print(f)
if not failures:
    print("\n  ALL CHECKS PASSED - FHIR->HL7 READY FOR CLIENT PRESENTATION")
else:
    print(f"\n  {len(failures)} ISSUES NEED FIXING")
