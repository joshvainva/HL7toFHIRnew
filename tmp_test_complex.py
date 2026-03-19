from app.core.mapper import FHIRMapper
from app.core.parser import HL7Parser

mapper = FHIRMapper()
parser = HL7Parser()

msg = (
"MSH|^~\\&|ULTRA_LIS|ULTRA_FAC|HYPER_EHR|HYPER_FAC|20260318161230||ORU^R01^ORU_R01|ULTRA123456789|P|2.5.1\r"
"SFT|EpicMegaBuild|2026.1.45|Build202603A|Epic|HYPERCONNECT|20260318160000\r"
"PID|1||999888777^^^HOSP^MR~1122334455^^^NATIONAL^NI||Hyper^Test^Patient^Ultra^III^^L||19720101|M|||101 Galaxy Way^Suite 500^St Louis^MO^63101^USA^H^20260318||314-555-1000~314-555-2000|ENG^English^ISO639-2|M|CAT|999-22-1111\r"
"NK1|1|Hyper^Relative^Max^^^L|BRO|202 High Point Ln^^St Louis^MO^63105|314-555-9911\r"
"PV1|1|O|B1^1102^A^HYPERFAC||||12345^SuperDoc^Omega^MD|67890^UltraDoc^Zeta^DO|CONS||F||||1|1234567890|V1|20260318155500|20260318155800|TeleVisit|||||||||||||||||||HYPERVIS\r"
"GT1|1|Hyper^Guarantor^Greg||555 Wealth Ave^^St Louis^MO^63103|314-555-7777|19700101|M|GUA\r"
"IN1|1|BIGINS|PPO12345|Big Insurance Co|P.O. Box 9999^^St Louis^MO^63102|800-555-1212|GRP999|Hyper^Subscriber^Hank|SUB999888|||\r"
"AL1|1|DA|PCN^Penicillin^RXNORM|SV^Severe Hives^SEV||20200101\r"
"DG1|1||E11.9^Type 2 Diabetes Mellitus^ICD10||||F\r"
"PR1|1||99214^Office Visit Complex^CPT||20260318155800|THIRD\r"
"ORC|RE|ORD12345|FILL98765|UFID445566||CM||||20260318155900|12345^SuperDoc^Omega^MD\r"
"OBR|1|ORD12345|FILL98765|80053^Comprehensive Metabolic Panel^LN^CMP^COMPREHENSIVE METABOLIC PANEL^LNCOMP|||20260318155930|20260318160010||||||12345^SuperDoc^Omega^MD||||||LAB^Main Lab^HYPER||||F\r"
"NTE|1|L|Fasting state confirmed by patient; verified 12-hour fast.\r"
"OBX|1|NM|2345-7^Glucose^LN^GLUC^Serum Glucose^LOCAL||145|mg/dL|65-99|H|A|||20260318160000\r"
"OBX|2|CWE|1234-5^Result Status^LN||F^Final^HL70123&FN^Final Result^V3|^^^LOCAL|N||F\r"
"OBX|3|CE|99999^Interpretation^LN||H^High^HL70078&1.2.840.10008.2.16.4^High-Interpretation^SNOMED||A\r"
"OBX|4|CX|112233^^^LIS^ACC||12345&Component1&Sub1^Component1Detail&SubDetail1&DeepDetail1^Namespace1&MV1&EXT1|||||F\r"
"OBX|5|CWE|3094-0^CO2^LN||25^mmol/L^^ISO^25.0&NormalRange&1.0&SubRef&Deep1^NESTLEX||||F\r"
"OBX|6|CWE|7777-1^NestedComplexObservation^LN||A^Alpha^SYS1&SubA&DeepA~B^Beta^SYS2&SubB&DeepB~C^Gamma^SYS3&SubC&DeepC|^Level3&Level4&Level5|N|||F\r"
"OBX|7|NM|2160-0^Creatinine^LN||1.15|mg/dL|0.6-1.3|N|F\r"
"OBX|8|RP|IMG1234^Chest X-Ray^L|^^^PACSSYS&STL&MO^2026-03-18&MIDLINE|XRayFile.dcm^DICOMFILE^APPLICATION/DICOM|||R\r"
"OBX|9|ED|PDFREP^Full PDF Report^L|^^^PDFSYS&GEN&&LVL3|PDF^Base64^TEXT^JVBERi0xLjQKJc...LongBase64EncodedPDF...=||||F\r"
"OBX|10|CWE|99988^UltraNested^LN||A^Alpha^S1&SS1&SSS1^D1&DD1&DDD1~B^Beta^S2&SS2&SSS2^D2&DD2&DDD2~C^Gamma^S3&SS3&SSS3^D3&DD3&DDD3|^^^&L4&L5|A|||F\r"
"OBR|2|ORD556677|FILL888899|58410-2^CBC with Differential^LN|||20260318160200|20260318161000||||||||||||LAB\r"
"NTE|1|L|Mild hemolysis observed. Results may reflect borderline variability.\r"
"OBX|1|NM|6690-2^WBC^LN||6.4|10^3/uL|4.0-11.0|N|F\r"
"OBX|2|NM|789-8^Hemoglobin^LN||13.8|g/dL|13.0-17.0|N|F\r"
"OBX|3|NM|785-6^Hematocrit^LN||40.7|%|39-49|N|F\r"
"OBX|4|NM|777-3^Platelets^LN||210|10^3/uL|150-400|N|F\r"
"OBX|5|CWE|8567^Blood Smear^L||NORMAL^Normal Morphology^LOCAL&SMEAR&LVL3/LVL4/LVL5|||N|F\r"
"RXA|0|1|20260318150000|20260318150000|207^COVID19 mRNA Vaccine^CVX|0.5|mL^^UCUM||00^New Immunization^NIP001||||||||CP\r"
"RXR|IM^Intramuscular^HL70162|LA^Left Arm^HL70163\r"
"ZDS|1|Deep^CustomData^Segment|A^ALevel^SYS1&Sub1&Deep1|B^BLevel^SYS2&Sub2&Deep2|C^CLevel^SYS3&Sub3&Deep3\r"
)

parsed = parser.parse(msg)
bundle, warnings, field_mappings = mapper.map(parsed)
entries = bundle.get('entry', [])

print("=== CONVERSION RESULT ===")
print(f"Message:   {parsed.message_type}^{parsed.message_event}  |  HL7 v{parsed.version}")
print(f"Resources: {len(entries)}  |  Mapping groups: {len(field_mappings)}")
print()

counts = {}
for e in entries:
    rt = e.get('resource', {}).get('resourceType', '?')
    counts[rt] = counts.get(rt, 0) + 1
print("--- Resource Summary ---")
for rt, n in sorted(counts.items()):
    print(f"  {rt}: {n}")
print()

# Patient
for e in entries:
    r = e.get('resource', {})
    if r.get('resourceType') == 'Patient':
        names = r.get('name', [])
        n0 = names[0] if names else {}
        given = ' '.join(n0.get('given', [])) if n0.get('given') else ''
        name_str = f"{given} {n0.get('family', '')}".strip()
        suffix = ', '.join(n0.get('suffix', []))
        ids = [i.get('value', '?') for i in r.get('identifier', [])]
        print(f"Patient: {name_str} {suffix}  |  DOB: {r.get('birthDate', '?')}  |  Gender: {r.get('gender', '?')}")
        print(f"  IDs: {ids}")
        addrs = r.get('address', [])
        if addrs:
            a = addrs[0]
            print(f"  Address: {' '.join(a.get('line', []))} {a.get('city', '')} {a.get('state', '')} {a.get('postalCode', '')}")
        telecoms = r.get('telecom', [])
        print(f"  Telecom: {[t.get('value', '') for t in telecoms]}")
        lang = r.get('communication', [{}])[0].get('language', {}).get('text', '?') if r.get('communication') else '?'
        marital = r.get('maritalStatus', {}).get('coding', [{}])[0].get('code', '?')
        print(f"  Language: {lang}  |  Marital: {marital}")
        print()

# Encounter
for e in entries:
    r = e.get('resource', {})
    if r.get('resourceType') == 'Encounter':
        cls = r.get('class', {})
        period = r.get('period', {})
        print(f"Encounter: status={r.get('status', '?')}  class={cls.get('code', '?')}({cls.get('display', '')})")
        print(f"  Period: {period.get('start', '?')} -> {period.get('end', '?')}")
        parts = r.get('participant', [])
        print(f"  Participants: {len(parts)}")
        print()

# Allergy
print("--- Allergies ---")
for e in entries:
    r = e.get('resource', {})
    if r.get('resourceType') == 'AllergyIntolerance':
        subst = r.get('code', {}).get('coding', [{}])[0]
        onset = r.get('onsetDateTime', r.get('onsetString', ''))
        print(f"  {subst.get('display') or subst.get('code', '?')}  criticality={r.get('criticality', '?')}  onset={onset}")

print()
print("--- Diagnoses ---")
for e in entries:
    r = e.get('resource', {})
    if r.get('resourceType') == 'Condition':
        code = r.get('code', {}).get('coding', [{}])[0]
        print(f"  {code.get('display') or code.get('code', '?')}")

print()
print("--- DiagnosticReports ---")
for e in entries:
    r = e.get('resource', {})
    if r.get('resourceType') == 'DiagnosticReport':
        code = r.get('code', {}).get('coding', [{}])[0]
        print(f"  [{code.get('code', '?')}] {code.get('display', '?')}  status={r.get('status', '?')}")
        if r.get('conclusion'):
            print(f"    Note: {r['conclusion'][:100]}")

print()
print("--- Observations ---")
for e in entries:
    r = e.get('resource', {})
    if r.get('resourceType') == 'Observation':
        code = r.get('code', {}).get('coding', [{}])[0]
        code_str = code.get('display') or code.get('code', '?')
        val = 'n/a'
        if 'valueQuantity' in r:
            vq = r['valueQuantity']
            val = f"{vq.get('value', '')} {vq.get('unit', '')}"
        elif 'valueCodeableConcept' in r:
            codings = r['valueCodeableConcept'].get('coding', [])
            val = ' | '.join(c.get('display') or c.get('code', '') for c in codings[:3])
        elif 'valueString' in r:
            val = r['valueString'][:60]
        elif 'valueAttachment' in r:
            va = r['valueAttachment']
            val = f"[ATTACHMENT: {va.get('contentType', '')}]"
        interp = r.get('interpretation', [])
        flag = interp[0].get('coding', [{}])[0].get('code', '') if interp else ''
        ref = r.get('referenceRange', [])
        rr = f" (ref: {ref[0].get('text', '')})" if ref else ''
        note = f" [{flag}]" if flag else ''
        print(f"  {code_str}: {val}{rr}{note}  status={r.get('status', '?')}")

print()
print("--- Immunization ---")
for e in entries:
    r = e.get('resource', {})
    if r.get('resourceType') == 'Immunization':
        vc = r.get('vaccineCode', {}).get('coding', [{}])[0]
        dq = r.get('doseQuantity', {})
        dose_str = f"{dq.get('value', '')} {dq.get('unit', '')}"
        route = r.get('route', {}).get('coding', [{}])[0]
        site = r.get('site', {}).get('coding', [{}])[0]
        print(f"  Vaccine: {vc.get('display') or vc.get('code', '?')}  dose={dose_str}")
        print(f"  Route: {route.get('display') or route.get('code', '?')}  Site: {site.get('display') or site.get('code', '?')}")
        print(f"  Occurrence: {r.get('occurrenceDateTime', '?')}  status={r.get('status', '?')}")

print()
print("--- Coverage ---")
for e in entries:
    r = e.get('resource', {})
    if r.get('resourceType') == 'Coverage':
        payor = r.get('payor', [{}])[0].get('display', '?')
        grp = r.get('class', [{}])[0].get('value', '?') if r.get('class') else '?'
        print(f"  Payor: {payor}  Group: {grp}  status={r.get('status', '?')}")

print()
if warnings:
    print("--- Warnings ---")
    for w in warnings:
        print(f"  WARNING: {w}")
else:
    print("No warnings.")
