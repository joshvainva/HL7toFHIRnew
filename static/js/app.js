/* ============================================================
   HL7 → FHIR Converter — Frontend Application
   ============================================================ */

'use strict';

// ---------------------------------------------------------------------------
// Sample HL7 messages
// ---------------------------------------------------------------------------
const SAMPLES = {
  adt: `MSH|^~\\&|ADT_SYSTEM|CITY_HOSPITAL|FHIR_SERVER|HQ|20240315143022||ADT^A01|MSG20240315001|P|2.5
EVN|A01|20240315143022|||NURSE^JANE^A
PID|1||MRN78965^^^CITYHOSP^MR~SSN123456789^^^NPI^SS||JOHNSON^MICHAEL^DAVID^JR^MR||19750820|M|||742 EVERGREEN TER^^SPRINGFIELD^IL^62701^USA||(217)555-0142^PRN^PH~mjohnson@email.com^NET^Internet||ENG|M|||SSN123456789
NK1|1|JOHNSON^SARAH^ANN|SPO|742 EVERGREEN TER^^SPRINGFIELD^IL^62701|(217)555-0143
PV1|1|I|MED^302^A^CITYHOSP|E|||NPI9876543^SMITH^RACHEL^M^DR|||IM|||||ADM|||V|||||||||||||||||||||CITY||||20240315143022`,

  oru: `MSH|^~\\&|LAB_SYSTEM|CITY_LAB|FHIR_SERVER|HQ|20240315150000||ORU^R01|LAB20240315001|P|2.5
PID|1||MRN78965^^^CITYHOSP^MR||JOHNSON^MICHAEL^DAVID||19750820|M
OBR|1|ORD20240315001|FILL20240315001|85025^CBC WITH DIFFERENTIAL^LN|||20240315140000|||||||||NPI9876543^SMITH^RACHEL|||F
OBX|1|NM|718-7^Hemoglobin^LN||14.2|g/dL^Grams per Deciliter^UCUM|13.5-17.5|N|||F|||20240315145500
OBX|2|NM|789-8^Erythrocytes^LN||4.85|10*6/uL^Million per microliter^UCUM|4.5-5.5|N|||F|||20240315145500
OBX|3|NM|6690-2^WBC^LN||7.2|10*3/uL^Thousand per microliter^UCUM|4.5-11.0|N|||F|||20240315145500
OBX|4|NM|777-3^Platelets^LN||220|10*3/uL^Thousand per microliter^UCUM|150-400|N|||F|||20240315145500
OBX|5|NM|4544-3^Hematocrit^LN||42.1|%^Percent^UCUM|41.0-53.0|N|||F|||20240315145500`,

  orm: `MSH|^~\\&|OE_SYSTEM|CITY_HOSPITAL|LAB_SYSTEM|CITY_LAB|20240315151500||ORM^O01|ORM20240315001|P|2.5
PID|1||MRN78965^^^CITYHOSP^MR||JOHNSON^MICHAEL^DAVID||19750820|M
PV1|1|O|CLINIC^101^A
ORC|NW|ORD20240315002||GRP20240315001|||||20240315151500|||NPI9876543^SMITH^RACHEL^M
OBR|1|ORD20240315002||80053^COMPREHENSIVE METABOLIC PANEL^LN|||20240315151500|||||||||NPI9876543^SMITH^RACHEL|||R`,

  // ── EHR Vendor Sample Messages ───────────────────────────────────────────
  // ── EPIC ─────────────────────────────────────────────────────────────────

  epic_adt: `MSH|^~\\&|EPIC|EPICFACILITY|INTERFACE|DEST|20260318080000||ADT^A01^ADT_A01|EPIC20260318001|P|2.5.1|||AL|NE|USA
SFT|Epic Systems Corporation|10.1|EpicCare Ambulatory|1.0.0.1||20260101
EVN|A01|20260318080000|||1234567890^SMITH^JAMES^E^^^MD^NPI
PID|1||E123456789^^^EPIC^MR~987654321^^^SSA^SS||RODRIGUEZ^MARIA^ELENA^MRS^^L|GARCIA|19680415|F|||500 PINE STREET^APT 3B^CHICAGO^IL^60601^USA^H||^PRN^PH^^^312^5550198~^NET^Internet^mrodriguez@email.com||SPA^Spanish^ISO639|M^Married^HL70002|CAT^Catholic^HL70006|A98765432|||N^Not Hispanic or Latino^HL70189|||||||N
PD1||||1234567890^SMITH^JAMES^E^^^MD^NPI
NK1|1|RODRIGUEZ^CARLOS^A|SPO^Spouse^HL70063|500 PINE STREET^APT 3B^CHICAGO^IL^60601|^PRN^PH^^^312^5550199||EC^Emergency Contact^HL70131
PV1|1|I|4N^420^B^EPICFAC|E^Emergency^HL70007||1234567890^SMITH^JAMES^E^^^MD^NPI|9876543210^JONES^SARAH^B^^^MD^NPI||INT^Internal Medicine^HL70069||||A^Admitted^HL70007|||1234567890^SMITH^JAMES^E^^^MD^NPI|INP^Inpatient^HL70007|VIS20260318001|||||||||||||||||||EPICFAC||||20260318075500
PV2|||^Acute chest pain evaluation|||||20260318075500|20260325000000
GT1|1|GUAR20260318001|RODRIGUEZ^MARIA^ELENA||500 PINE STREET^APT 3B^CHICAGO^IL^60601|^PRN^PH^^^312^5550198|||19680415|F|SEL^Self^HL70063
IN1|1|BCBS-PPO^Blue Cross PPO^HL70072|BCBS-IL001|BLUE CROSS BLUE SHIELD|PO BOX 805107^^CHICAGO^IL^60680||^WPN^PH^^^312^9388000|GRP-EPIC-001|RODRIGUEZ MARIA|SUB20260318001|20260101|20261231||||||SEL^Self^HL70063|19680415
AL1|1|DA^Drug Allergy^HL70127|SULFA^Sulfonamides^RXNORM|MO^Moderate^HL70128|Rash and itching|20150601
AL1|2|EA^Environmental Allergy^HL70127|LATEX^Latex^L|MI^Mild^HL70128|Contact dermatitis
DG1|1||I20.9^Unstable angina^ICD-10||20260318|A^Active^HL70052`,

  epic_oru: `MSH|^~\\&|EPIC_LAB|EPICFACILITY|EHR_INTERFACE|DEST|20260318120000||ORU^R01^ORU_R01|EPICLAB20260318001|P|2.5.1|||AL|NE|USA
SFT|Epic Systems Corporation|10.1|Beaker LIS|1.0.0.1||20260101
PID|1||E123456789^^^EPIC^MR||RODRIGUEZ^MARIA^ELENA||19680415|F
PV1|1|I|4N^420^B^EPICFAC||||1234567890^SMITH^JAMES^E^^^MD
ORC|RE|EPICORD001|EPICFILL001|EPICGRP001|CM||||20260318100000|||1234567890^SMITH^JAMES^E^^^MD
OBR|1|EPICORD001|EPICFILL001|10524-7^Cardiac enzymes panel^LN|||20260318093000|20260318110000||||||BLOOD|1234567890^SMITH^JAMES^E^^^MD||EPICFILL001|||F||1^^^20260318090000^^R
NTE|1|L|Specimen collected from left antecubital vein. STAT order.
OBX|1|NM|6598-7^Troponin I.cardiac^LN||0.04|ng/mL^Nanograms per milliliter^UCUM|<0.04|N|N||F|||20260318110000||1234567890^SMITH^JAMES^E^^^MD
OBX|2|NM|2157-6^Creatine kinase^LN||145|U/L^Units per liter^UCUM|30-170|N|||F|||20260318110000
OBX|3|NM|13969-1^CK-MB^LN||3.2|ng/mL^Nanograms per milliliter^UCUM|0.0-4.9|N|||F|||20260318110000
OBX|4|NM|33762-6^NT-proBNP^LN||320|pg/mL^Picograms per milliliter^UCUM|<125|H|A||F|||20260318110000
OBX|5|NM|2093-3^Cholesterol^LN||210|mg/dL^Milligrams per deciliter^UCUM|<200|H|||F|||20260318110000
OBX|6|NM|2085-9^HDL Cholesterol^LN||38|mg/dL^Milligrams per deciliter^UCUM|>40|L|||F|||20260318110000
OBX|7|NM|13457-7^LDL Cholesterol^LN||148|mg/dL^Milligrams per deciliter^UCUM|<100|H|A||F|||20260318110000
OBX|8|NM|2571-8^Triglycerides^LN||185|mg/dL^Milligrams per deciliter^UCUM|<150|H|||F|||20260318110000
OBR|2|EPICORD002|EPICFILL002|58410-2^CBC with Differential^LN|||20260318093000|20260318113000||||||BLOOD|1234567890^SMITH^JAMES^E^^^MD||EPICFILL002|||F
NTE|1|L|Routine CBC with 5-part differential.
OBX|1|NM|6690-2^WBC^LN||8.9|10*3/uL^Thousand per microliter^UCUM|4.5-11.0|N|||F|||20260318113000
OBX|2|NM|718-7^Hemoglobin^LN||11.2|g/dL^Grams per deciliter^UCUM|12.0-16.0|L|A||F|||20260318113000
OBX|3|NM|4544-3^Hematocrit^LN||33.8|%^Percent^UCUM|37.0-47.0|L|||F|||20260318113000
OBX|4|NM|777-3^Platelets^LN||345|10*3/uL^Thousand per microliter^UCUM|150-400|N|||F|||20260318113000
OBX|5|NM|770-8^Neutrophils^LN||72.1|%^Percent^UCUM|50-70|H|||F|||20260318113000
RXA|0|1|20260318|20260318|108^Aspirin^CVX|325|mg^milligram^UCUM||01^Historical^NIP001|1234567890^SMITH^JAMES^E^^^MD|^^^EPICFAC||||LOT-ASA-001|20271231
RXR|PO^Oral^HL70162|MOUTH^Oral^HL70163`,

  epic_orm: `MSH|^~\\&|EPIC_OE|EPICFACILITY|LAB_INTERFACE|DEST|20260318090000||ORM^O01^ORM_O01|EPICORM20260318001|P|2.5.1|||AL|NE|USA
SFT|Epic Systems Corporation|10.1|EpicCare Inpatient|1.0.0.1||20260101
PID|1||E123456789^^^EPIC^MR~987654321^^^SSA^SS||RODRIGUEZ^MARIA^ELENA||19680415|F|||500 PINE STREET^APT 3B^CHICAGO^IL^60601
PD1||||1234567890^SMITH^JAMES^E^^^MD^NPI
PV1|1|I|4N^420^B^EPICFAC|E|||1234567890^SMITH^JAMES^E^^^MD^NPI|||INT||||A|||1234567890^SMITH^JAMES^E^^^MD^NPI|INP|VIS20260318001
ORC|NW|EPICORD003|EPICFILL003|EPICGRP003|SC||||20260318090000|||1234567890^SMITH^JAMES^E^^^MD^NPI|||EPICFAC
OBR|1|EPICORD003|EPICFILL003|723-4^Renal panel^LN^RENAL^Renal Function Panel^EPIC|||20260318090000||||||BLOOD^Venous Blood^HL70070|1234567890^SMITH^JAMES^E^^^MD||EPICFILL003|20260318090000|||R||1^^^20260318090000^^ROUTINE
NTE|1|L|STAT order - patient being evaluated for acute kidney injury. Please expedite.
ORC|NW|EPICORD004|EPICFILL004|EPICGRP003|SC||||20260318090000|||1234567890^SMITH^JAMES^E^^^MD^NPI|||EPICFAC
OBR|2|EPICORD004|EPICFILL004|24357-6^Urinalysis^LN|||20260318090000||||||URINE^Clean Catch Urine^HL70070|1234567890^SMITH^JAMES^E^^^MD||EPICFILL004|20260318090000|||R
NTE|1|L|Clean catch midstream specimen required.
ORC|NW|EPICORD005|EPICFILL005|EPICGRP003|SC||||20260318090500|||1234567890^SMITH^JAMES^E^^^MD^NPI|||EPICFAC
OBR|3|EPICORD005|EPICFILL005|11529-5^Surgical pathology report^LN|||20260318090500||||||TISSUE^Tissue Sample^L|1234567890^SMITH^JAMES^E^^^MD||EPICFILL005|||R
NTE|1|L|Biopsy sample from cardiac catheterization procedure.`,

  // ── CERNER ───────────────────────────────────────────────────────────────
  cerner_adt: `MSH|^~\\&|CERNER|CERNERHOSP|EXTERNAL|DEST|20260318083000||ADT^A01^ADT_A01|CERNER20260318001|P|2.5|||AL|NE|USA
EVN|A01|20260318083000|||RN22345^WALKER^LINDA^K^RN
PID|1||C987654321^^^CERNER^MR~876543210^^^SSN^SS||PATEL^ARUN^KUMAR^^MR^^L|SHARMA|19550912|M|||2200 BROADWAY AVE^UNIT 12^NEW YORK^NY^10025^USA^H||^PRN^PH^^^212^5550342~^NET^Internet^apatel@email.com||HIN^Hindi^ISO639|M^Married^HL70002||C-VISIT-2026-001|||2186-5^Not Hispanic^HL70189
PD1|||CERNER HEALTH^^C100^NPI|RNP55678^NGUYEN^LISA^T^^^MD^NPI
NK1|1|PATEL^PRIYA^S|SPO^Spouse^HL70063|2200 BROADWAY AVE^UNIT 12^NEW YORK^NY^10025|^PRN^PH^^^212^5550343
PV1|1|I|6W^612^A^CERNERHOSP|U^Urgent^HL70007||RNP55678^NGUYEN^LISA^T^^^MD|CRN66789^CHEN^ROBERT^W^^^MD||HEM^Hematology^HL70069||||A|||RNP55678^NGUYEN^LISA^T^^^MD|INP^Inpatient^HL70007|CVIS20260318001|||||||||||||||||||CERNERHOSP||||ADM|20260318082500
PV2|||^Hematology workup - suspected anemia||||20260318082500|20260325000000
GT1|1|CGUAR20260318|PATEL^ARUN^KUMAR||2200 BROADWAY AVE^UNIT 12^NEW YORK^NY^10025|^PRN^PH^^^212^5550342|||19550912|M|SEL^Self^HL70063
IN1|1|AETNA-HMO^Aetna HMO^HL70072|AETNA-NY001|AETNA HEALTH INC|PO BOX 981106^^EL PASO^TX^79998||^WPN^PH^^^800^8723862|AETNA-GRP-2026|PATEL ARUN|AETNA-SUB-001|20260101|20261231
AL1|1|MA^Medication Allergy^HL70127|NSAIDS^NSAIDs^RXNORM|SE^Severe^HL70128|GI Bleeding|20180301
DG1|1||D50.9^Iron deficiency anemia unspecified^ICD-10||20260318|A^Active^HL70052
DG1|2||K92.1^Melena^ICD-10||20260318|A^Active^HL70052`,

  cerner_oru: `MSH|^~\\&|CERNER_LAB|CERNERHOSP|EHR_DEST|EXTERNAL|20260318140000||ORU^R01^ORU_R01|CERNLAB20260318001|P|2.5|||AL|NE|USA
PID|1||C987654321^^^CERNER^MR||PATEL^ARUN^KUMAR||19550912|M
PV1|1|I|6W^612^A^CERNERHOSP||||RNP55678^NGUYEN^LISA^T^^^MD
ORC|RE|CRNORD001|CRNFILL001|CRNGRP001|CM||||20260318120000|||RNP55678^NGUYEN^LISA^T^^^MD
OBR|1|CRNORD001|CRNFILL001|58410-2^CBC with Differential^LN|||20260318120000|20260318132000||||||BLOOD|RNP55678^NGUYEN^LISA^T^^^MD||CRNFILL001|||F
NTE|1|L|STAT CBC ordered for suspected iron deficiency anemia workup.
OBX|1|NM|718-7^Hemoglobin^LN||7.8|g/dL^Grams per deciliter^UCUM|13.5-17.5|LL|C||F|||20260318132000||RNP55678^NGUYEN^LISA^T^^^MD
OBX|2|NM|4544-3^Hematocrit^LN||24.2|%^Percent^UCUM|41.0-53.0|LL|||F|||20260318132000
OBX|3|NM|787-2^MCV^LN||68.4|fL^Femtoliters^UCUM|80.0-100.0|L|||F|||20260318132000
OBX|4|NM|785-6^MCH^LN||21.3|pg^Picograms^UCUM|27.0-33.0|L|||F|||20260318132000
OBX|5|NM|777-3^Platelets^LN||420|10*3/uL^Thousand per microliter^UCUM|150-400|H|||F|||20260318132000
OBX|6|NM|6690-2^WBC^LN||9.8|10*3/uL^Thousand per microliter^UCUM|4.5-11.0|N|||F|||20260318132000
OBR|2|CRNORD002|CRNFILL002|24362-6^Iron panel^LN|||20260318120000|20260318135000||||||BLOOD|RNP55678^NGUYEN^LISA^T^^^MD||CRNFILL002|||F
OBX|1|NM|2498-4^Iron^LN||28|ug/dL^Micrograms per deciliter^UCUM|60-170|LL|C||F|||20260318135000
OBX|2|NM|2714-4^TIBC^LN||520|ug/dL^Micrograms per deciliter^UCUM|250-370|H|||F|||20260318135000
OBX|3|NM|2284-8^Ferritin^LN||4|ng/mL^Nanograms per milliliter^UCUM|12-300|L|A||F|||20260318135000
OBX|4|NM|4679-7^Reticulocytes^LN||1.2|%^Percent^UCUM|0.5-1.5|N|||F|||20260318135000`,

  cerner_orm: `MSH|^~\\&|CERNER_OE|CERNERHOSP|RADIOLOGY|DEST|20260318090000||ORM^O01^ORM_O01|CRNORM20260318001|P|2.5|||AL|NE|USA
PID|1||C987654321^^^CERNER^MR||PATEL^ARUN^KUMAR||19550912|M|||2200 BROADWAY AVE^UNIT 12^NEW YORK^NY^10025
PV1|1|I|6W^612^A^CERNERHOSP|U|||RNP55678^NGUYEN^LISA^T^^^MD
ORC|NW|CRNORD003|CRNFILL003|CRNGRP002|SC||||20260318090000|||RNP55678^NGUYEN^LISA^T^^^MD
OBR|1|CRNORD003|CRNFILL003|36643-5^Abdominal CT^LN|||20260318090000||||||N/A|RNP55678^NGUYEN^LISA^T^^^MD||CRNFILL003|||R
NTE|1|L|Rule out GI bleed source. Patient has melena x 3 days. Prior colonoscopy 2 years ago was normal.
ORC|NW|CRNORD004|CRNFILL004|CRNGRP002|SC||||20260318090000|||RNP55678^NGUYEN^LISA^T^^^MD
OBR|2|CRNORD004|CRNFILL004|13292-1^Upper GI endoscopy^LN|||20260318090500||||||N/A|RNP55678^NGUYEN^LISA^T^^^MD||CRNFILL004|||R
NTE|1|L|GI consult ordered. Suspected peptic ulcer disease as source of blood loss.`,

  // ── MEDITECH ─────────────────────────────────────────────────────────────
  meditech_adt: `MSH|^~\\&|MEDITECH|MTFACILITY|INTERFACE|EXTERNAL|20260318091500||ADT^A01^ADT_A01|MT20260318001|P|2.4|||AL|NE
EVN|A01|20260318091500|||MT-RN-001^HARRIS^CAROL^J^RN
PID|1||MT4567890^^^MEDITECH^MR||WILLIAMS^DOROTHY^MAE^^MRS^^L|THOMPSON|19430718|F|||87 ELM STREET^^BOSTON^MA^02101^USA^H||^PRN^PH^^^617^5550876|ENG^English^ISO639|W^Widowed^HL70002||MT-ACCT-2026-001
PD1|||MTPROVIDER^^MT200^NPI|MT-MD-001^BROWN^RICHARD^A^^^MD^NPI
NK1|1|WILLIAMS^JAMES^A|SON^Son^HL70063|12 OAK LANE^^CAMBRIDGE^MA^02138|^PRN^PH^^^617^5550877
PV1|1|I|3E^350^A^MTFACILITY|E^Emergency^HL70007||MT-MD-001^BROWN^RICHARD^A^^^MD|MT-MD-002^TAYLOR^SUSAN^M^^^MD||CARD^Cardiology^HL70069||||A|||MT-MD-001^BROWN^RICHARD^A^^^MD|INP^Inpatient^HL70007|MTVIS20260318001|||||||||||||||||||MTFACILITY||||ADM|20260318091000
PV2|||^Cardiac monitoring - atrial fibrillation with rapid ventricular response
GT1|1|MTGUAR001|WILLIAMS^DOROTHY^MAE||87 ELM STREET^^BOSTON^MA^02101|^PRN^PH^^^617^5550876|||19430718|F|SEL
IN1|1|MEDICARE-A^Medicare Part A^HL70072|MEDICARE|CENTERS FOR MEDICARE AND MEDICAID|7500 SECURITY BLVD^^BALTIMORE^MD^21244||^WPN^PH^^^800^6334227|MEDICARE-PART-A|WILLIAMS DOROTHY|1EG4-TE5-MK72|20260101|20261231
AL1|1|DA^Drug Allergy^HL70127|WARFARIN^Warfarin^RXNORM|SV^Severe^HL70128|Hemorrhage
DG1|1||I48.0^Paroxysmal atrial fibrillation^ICD-10||20260318|A^Active^HL70052
DG1|2||I50.9^Heart failure unspecified^ICD-10||20260318|A^Active^HL70052
DG1|3||E11.9^Type 2 Diabetes Mellitus^ICD-10||20260318|A^Active^HL70052`,

  meditech_oru: `MSH|^~\\&|MEDITECH_LAB|MTFACILITY|EHR_DEST|EXTERNAL|20260318150000||ORU^R01^ORU_R01|MTLAB20260318001|P|2.4
PID|1||MT4567890^^^MEDITECH^MR||WILLIAMS^DOROTHY^MAE||19430718|F
PV1|1|I|3E^350^A^MTFACILITY||||MT-MD-001^BROWN^RICHARD^A^^^MD
ORC|RE|MTORD001|MTFILL001||CM||||20260318130000|||MT-MD-001^BROWN^RICHARD^A^^^MD
OBR|1|MTORD001|MTFILL001|55905-3^Cardiac monitoring panel^LN|||20260318130000|20260318143000||||||BLOOD|MT-MD-001^BROWN^RICHARD^A^^^MD||MTFILL001|||F
NTE|1|L|Patient in atrial fibrillation on admission. Rate control initiated.
OBX|1|NM|8867-4^Heart rate^LN||134|/min^Per minute^UCUM|60-100|H|C||F|||20260318143000||MT-MD-001^BROWN^RICHARD^A^^^MD
OBX|2|NM|8480-6^Systolic BP^LN||158|mm[Hg]^Millimeters mercury^UCUM|90-120|H|||F|||20260318143000
OBX|3|NM|8462-4^Diastolic BP^LN||94|mm[Hg]^Millimeters mercury^UCUM|60-80|H|||F|||20260318143000
OBX|4|NM|2160-0^Creatinine^LN||1.42|mg/dL^Milligrams per deciliter^UCUM|0.6-1.2|H|||F|||20260318143000
OBX|5|NM|3094-0^BUN^LN||28|mg/dL^Milligrams per deciliter^UCUM|7-25|H|||F|||20260318143000
OBX|6|NM|17861-6^Calcium^LN||9.1|mg/dL^Milligrams per deciliter^UCUM|8.5-10.5|N|||F|||20260318143000
OBX|7|NM|2823-3^Potassium^LN||3.3|mEq/L^Milliequivalents per liter^UCUM|3.5-5.0|L|A||F|||20260318143000
OBX|8|NM|2951-2^Sodium^LN||138|mEq/L^Milliequivalents per liter^UCUM|136-145|N|||F|||20260318143000
OBX|9|CWE|8601-7^EKG impression^LN||AFIB^Atrial Fibrillation with RVR^LOCAL||||F|||20260318145000`,

  // ── ALLSCRIPTS ───────────────────────────────────────────────────────────
  allscripts_adt: `MSH|^~\\&|ALLSCRIPTS|ALLFACILITY|INTERFACE|EXTERNAL|20260318094500||ADT^A04^ADT_A04|ALL20260318001|P|2.5|||AL|NE|USA
EVN|A04|20260318094500|||ALL-NP-001^GARCIA^PATRICIA^M^NP
PID|1||ALL78901^^^ALLSCRIPTS^MR||CHEN^JENNIFER^LI^^MS^^L||19920303|F|||456 MAPLE DRIVE^SUITE 2^SEATTLE^WA^98101^USA^H||^PRN^PH^^^206^5550654~^NET^Internet^jchen@email.com||ENG^English^ISO639|S^Single^HL70002|BUD^Buddhist^HL70006|ALL-ACCT-2026-001|||2186-5^Not Hispanic^HL70189
PD1|||ALLPROVIDER^^ALL100^NPI|ALL-MD-001^MARTINEZ^CARLOS^R^^^MD^NPI
NK1|1|CHEN^DAVID^Q|BRO^Brother^HL70063|789 FERN AVE^^BELLEVUE^WA^98004|^PRN^PH^^^425^5550655
PV1|1|O|AMB^1001^A^ALLFACILITY||ALL-MD-001^MARTINEZ^CARLOS^R^^^MD|||||AMB^Ambulatory^HL70007||||N|||ALL-MD-001^MARTINEZ^CARLOS^R^^^MD|OUT^Outpatient^HL70007|ALLVIS20260318001|||||||||||||||||||ALLFACILITY||||20260318094000
PV2|||^Annual wellness visit and preventive care
IN1|1|PREMERA-PPO^Premera Blue Cross PPO^HL70072|PREMERA-WA|PREMERA BLUE CROSS|PO BOX 91059^^SEATTLE^WA^98111||^WPN^PH^^^800^7224670|PREMERA-GRP-2026|CHEN JENNIFER|PREMERA-MBR-001|20260101|20261231
AL1|1|FA^Food Allergy^HL70127|GLUTEN^Gluten^L|MO^Moderate^HL70128|Celiac disease symptoms
DG1|1||K90.0^Celiac disease^ICD-10||20260318|A^Active^HL70052
DG1|2||F32.1^Major depressive disorder moderate^ICD-10||20260318|A^Active^HL70052
PR1|1||99395^Preventive visit 18-39^CPT||20260318094000|SELF`,

  allscripts_oru: `MSH|^~\\&|ALLSCRIPTS_LAB|ALLFACILITY|EHR_DEST|EXTERNAL|20260318110000||ORU^R01^ORU_R01|ALLLAB20260318001|P|2.5
PID|1||ALL78901^^^ALLSCRIPTS^MR||CHEN^JENNIFER^LI||19920303|F
PV1|1|O|AMB^1001^A^ALLFACILITY||||ALL-MD-001^MARTINEZ^CARLOS^R^^^MD
ORC|RE|ALLORD001|ALLFILL001|ALLGRP001|CM||||20260318095000|||ALL-MD-001^MARTINEZ^CARLOS^R^^^MD
OBR|1|ALLORD001|ALLFILL001|57698-3^Lipid panel^LN|||20260318095000|20260318104500||||||BLOOD FASTING|ALL-MD-001^MARTINEZ^CARLOS^R^^^MD||ALLFILL001|||F
NTE|1|L|Fasting lipid panel as part of annual wellness visit. Patient confirmed 12-hour fast.
OBX|1|NM|2093-3^Cholesterol^LN||178|mg/dL^Milligrams per deciliter^UCUM|<200|N|||F|||20260318104500
OBX|2|NM|2085-9^HDL Cholesterol^LN||62|mg/dL^Milligrams per deciliter^UCUM|>50|N|||F|||20260318104500
OBX|3|NM|13457-7^LDL Cholesterol^LN||98|mg/dL^Milligrams per deciliter^UCUM|<100|N|||F|||20260318104500
OBX|4|NM|2571-8^Triglycerides^LN||92|mg/dL^Milligrams per deciliter^UCUM|<150|N|||F|||20260318104500
OBR|2|ALLORD002|ALLFILL002|24331-1^Metabolic panel^LN|||20260318095000|20260318105500||||||BLOOD|ALL-MD-001^MARTINEZ^CARLOS^R^^^MD||ALLFILL002|||F
OBX|1|NM|2345-7^Glucose^LN||89|mg/dL^Milligrams per deciliter^UCUM|70-99|N|||F|||20260318105500
OBX|2|NM|1742-6^ALT^LN||22|U/L^Units per liter^UCUM|7-56|N|||F|||20260318105500
OBX|3|NM|1920-8^AST^LN||19|U/L^Units per liter^UCUM|10-40|N|||F|||20260318105500
OBX|4|NM|1975-2^Total Bilirubin^LN||0.7|mg/dL^Milligrams per deciliter^UCUM|0.1-1.2|N|||F|||20260318105500
OBX|5|NM|2157-6^Creatinine^LN||0.82|mg/dL^Milligrams per deciliter^UCUM|0.5-1.1|N|||F|||20260318105500
OBX|6|NM|38483-4^Creatinine Urine^LN||1.1|mg/dL|||N|||F|||20260318105500`,

  // ── ATHENA HEALTH ────────────────────────────────────────────────────────
  athena_adt: `MSH|^~\\&|ATHENA|ATHENAFAC|INTERFACE|EXTERNAL|20260318100000||ADT^A01^ADT_A01|ATH20260318001|P|2.5|||AL|NE|USA
EVN|A01|20260318100000|||ATH-MA-001^JOHNSON^KAREN^L^MA
PID|1||ATH112233^^^ATHENA^MR||THOMPSON^ROBERT^EARL^^MR^^L|JACKSON|19670824|M|||3300 SUNSET BLVD^^LOS ANGELES^CA^90028^USA^H||^PRN^PH^^^323^5550789~^NET^Internet^rthompson@email.com||ENG^English^ISO639|M^Married^HL70002||ATH-ACCT-2026-001|||2135-2^Hispanic or Latino^HL70189
PD1|||ATHPRACTICE^^ATH300^NPI|ATH-MD-001^PATEL^PRIYA^K^^^MD^NPI
NK1|1|THOMPSON^LINDA^M|SPS^Spouse^HL70063|3300 SUNSET BLVD^^LOS ANGELES^CA^90028|^PRN^PH^^^323^5550790
PV1|1|I|5S^510^A^ATHENAFAC|E^Emergency^HL70007||ATH-MD-001^PATEL^PRIYA^K^^^MD|ATH-MD-002^KIM^JAMES^S^^^MD||ORTHO^Orthopedics^HL70069||||A|||ATH-MD-001^PATEL^PRIYA^K^^^MD|INP^Inpatient^HL70007|ATHVIS20260318001|||||||||||||||||||ATHENAFAC||||ADM|20260318095500
PV2|||^Right hip fracture - surgical repair planned
GT1|1|ATHGUAR001|THOMPSON^ROBERT^EARL||3300 SUNSET BLVD^^LOS ANGELES^CA^90028|^PRN^PH^^^323^5550789|||19670824|M|SEL
IN1|1|BLUESHIELD-CA-PPO^Blue Shield CA PPO^HL70072|BSCA-001|BLUE SHIELD OF CALIFORNIA|PO BOX 272570^^CHICO^CA^95927||^WPN^PH^^^800^7943034|BSCA-GRP-2026|THOMPSON ROBERT|BSCA-MBR-001|20260101|20261231
IN2|||ATH-EMP-001|THOMPSON INDUSTRIES LLC
AL1|1|DA^Drug Allergy^HL70127|CODEINE^Codeine^RXNORM|MO^Moderate^HL70128|Nausea and vomiting|20100301
AL1|2|DA^Drug Allergy^HL70127|ASPIRIN^Aspirin^RXNORM|MI^Mild^HL70128|GI upset
DG1|1||S72.001A^Fracture right femoral neck initial encounter^ICD-10||20260318|A^Active^HL70052
DG1|2||M81.0^Age-related osteoporosis without fracture^ICD-10||20260318|A^Active^HL70052
PR1|1||27130^Total hip arthroplasty^CPT||20260318110000|PLANNED`,

  athena_oru: `MSH|^~\\&|ATHENA_LAB|ATHENAFAC|EHR_DEST|EXTERNAL|20260318130000||ORU^R01^ORU_R01|ATHLAB20260318001|P|2.5
PID|1||ATH112233^^^ATHENA^MR||THOMPSON^ROBERT^EARL||19670824|M
PV1|1|I|5S^510^A^ATHENAFAC||||ATH-MD-001^PATEL^PRIYA^K^^^MD
ORC|RE|ATHORD001|ATHFILL001|ATHGRP001|CM||||20260318110000|||ATH-MD-001^PATEL^PRIYA^K^^^MD
OBR|1|ATHORD001|ATHFILL001|57021-8^CBC W Auto Differential^LN|||20260318110000|20260318121000||||||BLOOD|ATH-MD-001^PATEL^PRIYA^K^^^MD||ATHFILL001|||F
NTE|1|L|Pre-operative CBC for right total hip arthroplasty.
OBX|1|NM|718-7^Hemoglobin^LN||11.8|g/dL^Grams per deciliter^UCUM|13.5-17.5|L|A||F|||20260318121000||ATH-MD-001^PATEL^PRIYA^K^^^MD
OBX|2|NM|4544-3^Hematocrit^LN||36.2|%^Percent^UCUM|41.0-53.0|L|||F|||20260318121000
OBX|3|NM|6690-2^WBC^LN||10.2|10*3/uL^Thousand per microliter^UCUM|4.5-11.0|N|||F|||20260318121000
OBX|4|NM|777-3^Platelets^LN||287|10*3/uL^Thousand per microliter^UCUM|150-400|N|||F|||20260318121000
OBR|2|ATHORD002|ATHFILL002|24331-1^Basic metabolic panel^LN|||20260318110000|20260318123000||||||BLOOD|ATH-MD-001^PATEL^PRIYA^K^^^MD||ATHFILL002|||F
NTE|1|L|Pre-op BMP to assess renal function and electrolytes.
OBX|1|NM|2345-7^Glucose^LN||102|mg/dL^Milligrams per deciliter^UCUM|70-99|H|||F|||20260318123000
OBX|2|NM|2160-0^Creatinine^LN||1.1|mg/dL^Milligrams per deciliter^UCUM|0.7-1.3|N|||F|||20260318123000
OBX|3|NM|3094-0^BUN^LN||18|mg/dL^Milligrams per deciliter^UCUM|7-25|N|||F|||20260318123000
OBX|4|NM|2823-3^Potassium^LN||4.1|mEq/L^Milliequivalents per liter^UCUM|3.5-5.0|N|||F|||20260318123000
OBX|5|NM|2951-2^Sodium^LN||141|mEq/L^Milliequivalents per liter^UCUM|136-145|N|||F|||20260318123000
OBX|6|NM|17861-6^Calcium^LN||9.4|mg/dL^Milligrams per deciliter^UCUM|8.5-10.5|N|||F|||20260318123000
OBX|7|NM|2028-9^CO2^LN||24|mEq/L^Milliequivalents per liter^UCUM|22-29|N|||F|||20260318123000`,
};

// ---------------------------------------------------------------------------
// FHIR Sample Bundles
// ---------------------------------------------------------------------------
const FHIR_SAMPLES = {
  adt: {
    resourceType: "Bundle", type: "collection",
    entry: [
      { resource: { resourceType: "Patient", id: "p1",
          name: [{ use: "official", family: "JOHNSON", given: ["MICHAEL", "DAVID"] }],
          birthDate: "1975-08-20", gender: "male",
          identifier: [{ system: "http://hospital.example.org/mrn", value: "MRN78965" }],
          address: [{ line: ["742 EVERGREEN TER"], city: "SPRINGFIELD", state: "IL", postalCode: "62701", country: "USA" }],
          telecom: [{ system: "phone", value: "(217)555-0142", use: "home" }]
      }},
      { resource: { resourceType: "Organization", id: "org1", name: "CITY_HOSPITAL" }},
      { resource: { resourceType: "Encounter", id: "enc1", status: "finished",
          class: { code: "IMP", display: "inpatient" },
          subject: { reference: "Patient/p1" },
          period: { start: "2024-03-15T14:30:22", end: "2024-03-20T10:00:00" },
          identifier: [{ value: "VN20240315001" }]
      }},
      { resource: { resourceType: "Practitioner", id: "dr1",
          identifier: [{ system: "http://hl7.org/fhir/sid/us-npi", value: "NPI9876543" }],
          name: [{ use: "official", family: "SMITH", given: ["RACHEL", "M"] }]
      }}
    ]
  },
  oru: {
    resourceType: "Bundle", type: "collection",
    entry: [
      { resource: { resourceType: "Patient", id: "p1",
          name: [{ family: "JOHNSON", given: ["MICHAEL"] }],
          birthDate: "1975-08-20", gender: "male",
          identifier: [{ system: "http://hospital.example.org/mrn", value: "MRN78965" }]
      }},
      { resource: { resourceType: "Practitioner", id: "dr1",
          identifier: [{ system: "http://hl7.org/fhir/sid/us-npi", value: "NPI9876543" }],
          name: [{ family: "SMITH", given: ["RACHEL"] }]
      }},
      { resource: { resourceType: "DiagnosticReport", id: "dr1",
          status: "final",
          code: { coding: [{ system: "http://loinc.org", code: "85025", display: "CBC WITH DIFFERENTIAL" }] },
          subject: { reference: "Patient/p1" },
          effectiveDateTime: "2024-03-15T14:00:00",
          identifier: [
            { type: { coding: [{ code: "PLAC" }] }, value: "ORD20240315001" },
            { type: { coding: [{ code: "FILL" }] }, value: "FILL20240315001" }
          ],
          result: [{ reference: "Observation/obs1" }, { reference: "Observation/obs2" }]
      }},
      { resource: { resourceType: "Observation", id: "obs1", status: "final",
          code: { coding: [{ system: "http://loinc.org", code: "718-7", display: "Hemoglobin" }] },
          valueQuantity: { value: 14.2, unit: "g/dL", system: "http://unitsofmeasure.org" },
          referenceRange: [{ text: "13.5-17.5" }], interpretation: [{ coding: [{ code: "N" }] }]
      }},
      { resource: { resourceType: "Observation", id: "obs2", status: "final",
          code: { coding: [{ system: "http://loinc.org", code: "6690-2", display: "WBC" }] },
          valueQuantity: { value: 7.2, unit: "10*3/uL", system: "http://unitsofmeasure.org" },
          referenceRange: [{ text: "4.5-11.0" }], interpretation: [{ coding: [{ code: "N" }] }]
      }}
    ]
  },
  orm: {
    resourceType: "Bundle", type: "collection",
    entry: [
      { resource: { resourceType: "Patient", id: "p1",
          name: [{ family: "JOHNSON", given: ["MICHAEL"] }],
          birthDate: "1975-08-20", gender: "male",
          identifier: [{ system: "http://hospital.example.org/mrn", value: "MRN78965" }]
      }},
      { resource: { resourceType: "Practitioner", id: "dr1",
          identifier: [{ system: "http://hl7.org/fhir/sid/us-npi", value: "NPI9876543" }],
          name: [{ family: "SMITH", given: ["RACHEL", "M"] }]
      }},
      { resource: { resourceType: "ServiceRequest", id: "sr1",
          status: "active", intent: "order", priority: "routine",
          subject: { reference: "Patient/p1" },
          requester: { reference: "Practitioner/dr1" },
          code: { coding: [{ system: "http://loinc.org", code: "80053", display: "COMPREHENSIVE METABOLIC PANEL" }] },
          identifier: [
            { type: { coding: [{ code: "PLAC" }] }, value: "ORD20240315002" }
          ],
          authoredOn: "2024-03-15T15:15:00"
      }}
    ]
  }
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentResult = null;
let currentBatch = null;   // stores all batch results for multi-message export
window._ehrExcelIsTableFormat = false;
let uploadedFile = null;
let historyItems = [];
let conversionDirection = 'hl7_to_fhir';
let aiModeEnabled = false;

// ---------------------------------------------------------------------------
// AI Mode Toggle
// ---------------------------------------------------------------------------
window.toggleAIMode = function() {
  const checkbox = document.getElementById('ai-toggle-checkbox');
  if (checkbox) {
    aiModeEnabled = checkbox.checked;
  }
  const sw = document.getElementById('ai-toggle-switch');
  const banner = document.getElementById('ai-active-banner');
  const convertBtnEl = document.getElementById('convert-btn');
  const btnIcon = document.getElementById('convert-btn-icon');
  const spinnerLabel = document.getElementById('spinner-label');
  const aiOutputBadge = document.getElementById('ai-output-badge');

  sw.classList.toggle('on', aiModeEnabled);
  banner.classList.toggle('hidden', !aiModeEnabled);
  const maskLabel = document.getElementById('mask-phi-label');
  if (maskLabel) maskLabel.classList.toggle('hidden', !aiModeEnabled);
  const providerGroup = document.getElementById('ai-provider-group');
  if (providerGroup) providerGroup.classList.toggle('hidden', !aiModeEnabled);
  if (aiModeEnabled) updateAIProviderBadge();
  convertBtnEl.classList.toggle('ai-btn', aiModeEnabled);

  if (aiModeEnabled) {
    btnIcon.textContent = '✨';
    spinnerLabel.textContent = 'AI Converting…';
  } else {
    btnIcon.textContent = '⚡';
    spinnerLabel.textContent = 'Converting…';
  }

  // Hide AI output badge until next conversion
  if (aiOutputBadge) aiOutputBadge.classList.add('hidden');
};

function getAIProvider() {
  const sel = document.querySelector('input[name="ai-provider"]:checked');
  return sel ? sel.value : 'groq';
}

window.updateAIProviderBadge = function() {
  const provider = getAIProvider();
  const banner = document.getElementById('ai-active-banner');
  if (banner) {
    const model = provider === 'claude' ? 'Claude Sonnet 4.6' : 'Groq AI (Llama 3.3)';
    const brand = provider === 'claude' ? 'claude-brand' : 'gemini-brand';
    banner.innerHTML = `✨ <strong>AI Mode ON</strong> — Powered by <span class="${brand}">${model}</span>`;
  }
};

// ---------------------------------------------------------------------------
// Direction toggle
// ---------------------------------------------------------------------------
window.setDirection = function(dir) {
  conversionDirection = dir;
  const isHL7  = dir === 'hl7_to_fhir';
  const isFHIR = dir === 'fhir_to_hl7';
  const isEHR  = dir === 'ehr_to_fhir';

  // Toggle direction buttons
  document.getElementById('btn-hl7-to-fhir').classList.toggle('active', isHL7);
  document.getElementById('btn-fhir-to-hl7').classList.toggle('active', isFHIR);
  document.getElementById('btn-ehr-to-fhir').classList.toggle('active', isEHR);

  // Toggle input areas inside the text tab
  document.getElementById('hl7-input-area').classList.toggle('hidden', !isHL7);
  document.getElementById('fhir-input-area').classList.toggle('hidden', !isFHIR);
  document.getElementById('ehr-input-area').classList.toggle('hidden', !isEHR);

  // Update text tab label
  document.getElementById('in-tab-text').textContent = isHL7 ? 'Paste HL7' : isFHIR ? 'Paste FHIR' : 'Paste EHR Data';

  // Hide Mapping Rules tab in FHIR→HL7 direction
  const tabMapping = document.getElementById('in-tab-mapping');
  if (tabMapping) tabMapping.classList.toggle('hidden', !isHL7);

  // Update drop zone hint text
  const dropHint = document.querySelector('.drop-hint');
  const fileAcceptInput = document.getElementById('file-input');
  if (isHL7 || isEHR) {
    if (dropHint) dropHint.textContent = 'Supported: .hl7 · .txt · .csv · .xlsx · .xls · .docx';
    if (fileAcceptInput) fileAcceptInput.accept = '.hl7,.txt,.csv,.xlsx,.xls,.docx';
  } else {
    if (dropHint) dropHint.textContent = 'Supported: .json (FHIR Bundle)';
    if (fileAcceptInput) fileAcceptInput.accept = '.json';
  }

  // EHR mode works with or without AI

  // If currently on a now-hidden tab, switch back to text tab
  const activeInTab = document.querySelector('.input-tabs .tab-btn.active');
  if (activeInTab && activeInTab.classList.contains('hidden')) {
    document.getElementById('in-tab-text').click();
  }

  // Update convert button label
  document.getElementById('convert-btn-label').textContent =
    isHL7 ? 'Convert to FHIR' : isFHIR ? 'Convert to HL7' : 'Convert EHR to FHIR';

  // HL7→FHIR output tabs: FHIR JSON, XML, Human Readable, Summary, Field Mappings (no HL7 Message)
  // FHIR→HL7 output tabs: HL7 Message only
  const outTabs = ['json', 'xml', 'readable', 'summary', 'mappings'];
  outTabs.forEach(t => {
    const el = document.getElementById('out-tab-' + t);
    if (el) el.classList.toggle('hidden', !isHL7);
  });
  const hl7outTab = document.getElementById('out-tab-hl7out');
  if (hl7outTab) hl7outTab.classList.toggle('hidden', isHL7);

  // Reset output panel
  outputPanel.classList.add('hidden');
  hideError();
  statusBar.classList.add('hidden');
};

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const hl7Input      = document.getElementById('hl7-input');
const convertBtn    = document.getElementById('convert-btn');
const spinner       = document.getElementById('spinner');
const statusBar     = document.getElementById('status-bar');
const statusBadges  = document.getElementById('status-badges');
const warningList   = document.getElementById('warning-list');
const errorPanel    = document.getElementById('error-panel');
const errorMessage  = document.getElementById('error-message');
const errorList     = document.getElementById('error-list');
const outputPanel   = document.getElementById('output-panel');
const jsonOutput    = document.getElementById('json-output');
const xmlOutput     = document.getElementById('xml-output');
const pdfPreview     = document.getElementById('pdf-preview');
const summaryContent = document.getElementById('summary-content');
const dropZone      = document.getElementById('drop-zone');
const fileInput     = document.getElementById('file-input');
const fileInfo      = document.getElementById('file-info');
const clearBtn      = document.getElementById('clear-btn');
const refreshHistoryBtn = document.getElementById('refresh-history-btn');
const clearHistoryBtn = document.getElementById('clear-history-btn');
const historyList = document.getElementById('history-list');
const convertBar = document.querySelector('.convert-bar');

// ---------------------------------------------------------------------------
// Input tab switching
// ---------------------------------------------------------------------------
document.querySelectorAll('.input-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.input-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    // Hide convert bar if history or mapping tab is active
    if (btn.dataset.tab === 'history' || btn.dataset.tab === 'mapping') {
      convertBar.style.display = 'none';
    } else {
      convertBar.style.display = '';
    }
  });
});

// Output tab switching
document.querySelectorAll('.output-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.output-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.out-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`out-${btn.dataset.outTab}`).classList.add('active');
  });
});

// ---------------------------------------------------------------------------
// Sample buttons
// ---------------------------------------------------------------------------
const EHR_SAMPLE = `PATIENT|MRN-2026-009901|James|Rivera|1978-03-22|Male|Spanish|214-555-0187|5821 Oak Creek Drive|Dallas|TX|75201

ENCOUNTER|VIS-2026-1001|Outpatient|Clinic Room 101|98765|Dr. Linda Park|2026-02-10T14:30:00|2026-02-10T14:45:00

ALLERGY|1|Sulfonamides|Moderate rash|2015-03-01

DIAGNOSIS|1|J45.20|Mild persistent asthma
DIAGNOSIS|2|I10|Essential hypertension

LAB_ORDER|ORD-2026-881|General Health Panel|2026-02-10T14:35:00

LAB_RESULT|1|2345-7|Glucose|95|mg/dL|65-99|Normal
LAB_RESULT|2|2160-0|Creatinine|1.0|mg/dL|0.6-1.3|Normal
LAB_RESULT|3|718-7|Hemoglobin|15.1|g/dL|13.5-17.5|Normal

VITAL|BP|132/84|mmHg
VITAL|HR|78|bpm
VITAL|WEIGHT|82.4|kg

IMMUNIZATION|Influenza|2026-02-10|0.5|mL|Intramuscular|Right Arm

INSURANCE|BlueCross BlueShield Texas|PPO-TX-22|GRP-TX-9900|MBR-776543`;

document.querySelectorAll('.sample-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const type = btn.dataset.type;
    const ehrType = btn.dataset.ehrType;
    if (ehrType === 'ehr_sample') {
      document.getElementById('ehr-input').value = EHR_SAMPLE;
      document.querySelectorAll('.input-tabs .tab-btn')[0].click();
    } else {
      hl7Input.value = SAMPLES[type] || '';
      document.querySelectorAll('.input-tabs .tab-btn')[0].click();
    }
  });
});

document.getElementById('clear-ehr-btn')?.addEventListener('click', () => {
  document.getElementById('ehr-input').value = '';
});

clearBtn.addEventListener('click', () => { hl7Input.value = ''; });

// FHIR sample buttons
document.querySelectorAll('.fhir-sample-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const type = btn.dataset.fhirType;
    const sample = FHIR_SAMPLES[type];
    if (sample) {
      document.getElementById('fhir-input').value = JSON.stringify(sample, null, 2);
    }
  });
});
document.getElementById('clear-fhir-btn').addEventListener('click', () => {
  document.getElementById('fhir-input').value = '';
});

// ---------------------------------------------------------------------------
// History management
// ---------------------------------------------------------------------------
if (refreshHistoryBtn) refreshHistoryBtn.addEventListener('click', loadHistory);

// Load history when history tab is activated
document.querySelectorAll('.input-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.input-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');

    // Load history when history tab is selected
    if (btn.dataset.tab === 'history') {
      loadHistory();
    }
  });
});

// ---------------------------------------------------------------------------
// File drag-and-drop / browse
// ---------------------------------------------------------------------------
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) setUploadedFile(file);
});
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setUploadedFile(fileInput.files[0]);
});

function setUploadedFile(file) {
  // Validate file type matches current direction
  const isFhirDir = conversionDirection === 'fhir_to_hl7';
  if (isFhirDir && !file.name.toLowerCase().endsWith('.json')) {
    showError('Please upload a .json file containing a FHIR Bundle.', []);
    fileInput.value = '';
    return;
  }
  uploadedFile = file;
  fileInfo.classList.remove('hidden');
  fileInfo.innerHTML = `
    <span>📄</span>
    <span><strong>${escapeHtml(file.name)}</strong> &nbsp;·&nbsp;
    ${formatBytes(file.size)}</span>
    <button onclick="clearFile()" style="margin-left:auto;background:none;border:none;color:#f06060;cursor:pointer;font-size:1rem;">✕</button>
  `;
}

function clearFile() {
  uploadedFile = null;
  fileInput.value = '';
  fileInfo.classList.add('hidden');
  fileInfo.innerHTML = '';
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ---------------------------------------------------------------------------
// Convert button
// ---------------------------------------------------------------------------
convertBtn.addEventListener('click', async () => {
  const activeInputTab = document.querySelector('.input-tabs .tab-btn.active').dataset.tab;

  if (conversionDirection === 'fhir_to_hl7') {
    if (activeInputTab === 'file') {
      if (!uploadedFile) {
        showError('Please select a JSON file to upload.', []);
        return;
      }
      await convertFhirFileToHl7(uploadedFile);
    } else {
      const text = document.getElementById('fhir-input').value.trim();
      if (!text) {
        showError('Please paste a FHIR Bundle JSON or load a sample.', []);
        return;
      }
      let bundle;
      try {
        bundle = JSON.parse(text);
      } catch (e) {
        showError('Invalid JSON: ' + e.message, []);
        return;
      }
      if (aiModeEnabled) {
        await aiConvertFhirToHl7(bundle);
      } else {
        await convertFhirToHl7(bundle);
      }
    }
    return;
  }

  // ── EHR Raw → FHIR ──────────────────────────────────────────────────────
  if (conversionDirection === 'ehr_to_fhir') {
    window._ehrExcelIsTableFormat = false;
    let text = document.getElementById('ehr-input').value.trim();
    // If textarea is empty but a file was uploaded, read the file content
    if (!text && uploadedFile) {
      const fname = uploadedFile.name.toLowerCase();
      const isExcel = fname.endsWith('.xlsx') || fname.endsWith('.xls');
      try {
        if (isExcel) {
          // Use SheetJS to extract EHR pipe-delimited lines from Excel
          text = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = e => {
              try {
                const validTypes = new Set(['PATIENT','ENCOUNTER','ALLERGY','DIAGNOSIS','LAB_ORDER','LAB_RESULT','VITAL','IMMUNIZATION','INSURANCE','NK1','CHIEF_COMPLAINT','SYMPTOM','PROCEDURE','MEDICATION','CLINICAL_NOTE']);
                // Normalize sheet name: uppercase + replace spaces with underscores
                const SHEET_ALIASES = {
                  MEDICATION_STATEMENT:'MEDICATION', MEDICATION_STATEMENTS:'MEDICATION', MEDICATIONS:'MEDICATION',
                  LAB_RESULTS:'LAB_RESULT', VITALS:'VITAL', VITAL_SIGNS:'VITAL',
                  ALLERGIES:'ALLERGY', DIAGNOSES:'DIAGNOSIS', PROCEDURES:'PROCEDURE',
                  IMMUNIZATIONS:'IMMUNIZATION', CHIEF_COMPLAINTS:'CHIEF_COMPLAINT', SYMPTOMS:'SYMPTOM',
                  CLINICAL_NOTES:'CLINICAL_NOTE', INSURANCES:'INSURANCE', ENCOUNTERS:'ENCOUNTER', PATIENTS:'PATIENT',
                };
                const normalizeSheet = n => { const u = n.trim().toUpperCase().replace(/\s+/g,'_'); return SHEET_ALIASES[u] || u; };
                const wb = XLSX.read(e.target.result, { type: 'array' });
                const lines = [];
                let isTableFormat = false;

                // Canonical field order for each EHR record type (header aliases -> position)
                // Format: RECORD_TYPE -> [ [alias,...], ... ] (position = array index)
                const EHR_FIELD_MAP = {
                  PATIENT: [
                    ['mrn','patient id','patient_id','medical record','medical record number','id'],
                    ['first','first name','firstname','given name','given'],
                    ['last','last name','lastname','family name','family','surname'],
                    ['dob','date of birth','dateofbirth','birth date','birthdate'],
                    ['gender','sex'],
                    ['language','preferred language'],
                    ['phone','phone number','telephone'],
                    ['address','street','street address'],
                    ['city'],
                    ['state'],
                    ['zip','zipcode','zip code','postal code'],
                  ],
                  ENCOUNTER: [
                    ['visit id','visitid','encounter id','encounterid','id'],
                    ['visit type','visittype','type','encounter type'],
                    ['location','facility'],
                    ['provider id','providerid'],
                    ['provider name','providername','provider','attending'],
                    ['start','admit date','admitdate','start date','startdate','admission date'],
                    ['end','discharge date','dischargedate','end date','enddate'],
                  ],
                  ALLERGY: [
                    ['seq','sequence','#','no'],
                    ['substance','allergen','allergy','name'],
                    ['reaction'],
                    ['onset','onset date','onsetdate','date'],
                  ],
                  DIAGNOSIS: [
                    ['seq','sequence','#','no'],
                    ['icd code','icdcode','icd','code','diagnosis code'],
                    ['description','diagnosis','name','condition'],
                  ],
                  LAB_ORDER: [
                    ['order id','orderid','id'],
                    ['panel','panel name','panelname','test panel','test'],
                    ['ordered','ordered time','orderedtime','order date','orderdate'],
                  ],
                  LAB_RESULT: [
                    ['seq','sequence','#','no'],
                    ['loinc','loinc code','loinccode','code'],
                    ['test','test name','testname','name'],
                    ['value','result','result value'],
                    ['unit','units'],
                    ['ref range','refrange','reference range','normal range'],
                    ['flag','abnormal flag'],
                  ],
                  VITAL: [
                    ['type','vital type','vitaltype','vital'],
                    ['value','result'],
                    ['unit','units'],
                  ],
                  IMMUNIZATION: [
                    ['vaccine','vaccine name','vaccinename','name'],
                    ['date','administered','administration date'],
                    ['dose'],
                    ['unit','units'],
                    ['route'],
                    ['site'],
                  ],
                  INSURANCE: [
                    ['provider','insurance provider','insuranceprovider','payer'],
                    ['plan','plan name'],
                    ['group','group number','groupnumber'],
                    ['member id','memberid','member'],
                  ],
                  NK1: [
                    ['seq','sequence','#','no'],
                    ['name','contact name','next of kin'],
                    ['relationship','relation'],
                    ['phone','phone number'],
                  ],
                  CHIEF_COMPLAINT: [
                    ['complaint','chief complaint','description','text'],
                  ],
                  SYMPTOM: [
                    ['symptom','name','description'],
                    ['onset','onset date'],
                    ['severity'],
                  ],
                  PROCEDURE: [
                    ['code','procedure code','cpt','cpt code'],
                    ['description','procedure','name'],
                    ['date','procedure date'],
                    ['provider','performing provider'],
                  ],
                  MEDICATION: [
                    ['name','medication','drug','medication name'],
                    ['dose','dosage'],
                    ['route'],
                    ['frequency','freq'],
                    ['start','start date','startdate'],
                    ['end','end date','enddate'],
                    ['status'],
                  ],
                  CLINICAL_NOTE: [
                    ['type','note type','notetype'],
                    ['date','note date'],
                    ['provider','author'],
                    ['text','note','content'],
                  ],
                };

                // Map a data row to canonical pipe-delimited EHR line using header aliases
                function mapRowToEhr(type, headers, dataRow) {
                  const fieldDefs = EHR_FIELD_MAP[type];
                  if (!fieldDefs) {
                    // No mapping defined — just join as-is
                    const vals = dataRow.map(c => String(c === null || c === undefined ? '' : c).trim());
                    return vals.some(v => v) ? type + '|' + vals.join('|') : null;
                  }
                  // Build a header->colIndex map (lowercase)
                  const hdrIdx = {};
                  headers.forEach((h, i) => { hdrIdx[String(h).trim().toLowerCase()] = i; });
                  // For each canonical field, find the best matching column
                  const result = fieldDefs.map(aliases => {
                    for (const alias of aliases) {
                      if (hdrIdx[alias] !== undefined) {
                        const v = dataRow[hdrIdx[alias]];
                        return String(v === null || v === undefined ? '' : v).trim();
                      }
                    }
                    return ''; // field not found
                  });
                  return result.some(v => v) ? type + '|' + result.join('|') : null;
                }

                // First pass: collect all sheets and detect format
                const sheetData = {}; // sheetNorm -> { headers, rows }
                wb.SheetNames.forEach(sheetName => {
                  const ws = wb.Sheets[sheetName];
                  const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
                  const sheetNorm = normalizeSheet(sheetName);
                  if (validTypes.has(sheetNorm)) {
                    isTableFormat = true;
                    const headers = rows[0] ? rows[0].map(h => String(h).trim()) : [];
                    sheetData[sheetNorm] = { headers, rows: rows.slice(1) };
                  } else {
                    // Raw pipe-delimited cells in column A — process immediately
                    rows.forEach(row => {
                      const cell = String(row[0] || '').trim();
                      if (!cell) return;
                      const recType = cell.split('|')[0].trim().toUpperCase();
                      if (validTypes.has(recType)) lines.push(cell);
                    });
                  }
                });

                if (isTableFormat) {
                  const sheetOrder = ['PATIENT','ENCOUNTER','CHIEF_COMPLAINT','SYMPTOM','DIAGNOSIS','PROCEDURE','MEDICATION','ALLERGY','LAB_RESULT','VITAL','IMMUNIZATION','NK1','INSURANCE','LAB_ORDER','CLINICAL_NOTE'];

                  // Find which header column is the patient identifier (Patient Name / DOB)
                  const PATIENT_NAME_ALIASES = ['patient name','full name','patient','name'];
                  const DOB_ALIASES = ['dob','date of birth','dateofbirth','birth date','birthdate'];
                  function findPatientIdCols(headers) {
                    let nameIdx = -1, dobIdx = -1;
                    headers.forEach((h, i) => {
                      const hl = String(h).toLowerCase().trim();
                      if (nameIdx === -1 && PATIENT_NAME_ALIASES.includes(hl)) nameIdx = i;
                      if (dobIdx === -1 && DOB_ALIASES.includes(hl)) dobIdx = i;
                    });
                    return { nameIdx, dobIdx };
                  }

                  // Build ordered patient list from PATIENT sheet (1 row per patient)
                  const patientSheet = sheetData['PATIENT'];
                  const patientList = []; // [{name, dob, row}]
                  if (patientSheet) {
                    const { nameIdx, dobIdx } = findPatientIdCols(patientSheet.headers);
                    patientSheet.rows.forEach(row => {
                      if (!row.some(c => String(c).trim())) return; // skip empty rows
                      const name = nameIdx >= 0 ? String(row[nameIdx] || '').trim() : '';
                      const dob  = dobIdx  >= 0 ? String(row[dobIdx]  || '').trim() : '';
                      patientList.push({ name, dob, row });
                    });
                  }

                  // For each patient, output PATIENT line then all their rows from each sheet
                  const allTypes = [...sheetOrder, ...Object.keys(sheetData).filter(t => !sheetOrder.includes(t))];
                  patientList.forEach(patient => {
                    allTypes.forEach(type => {
                      const sheet = sheetData[type];
                      if (!sheet) return;

                      if (type === 'PATIENT') {
                        // One PATIENT line per patient
                        const line = mapRowToEhr(type, sheet.headers, patient.row);
                        if (line) lines.push(line);
                        return;
                      }

                      // Find identifier columns in this sheet
                      const { nameIdx, dobIdx } = findPatientIdCols(sheet.headers);

                      if (nameIdx >= 0 || dobIdx >= 0) {
                        // Filter rows where patient name and/or DOB matches
                        sheet.rows.forEach(row => {
                          if (!row.some(c => String(c).trim())) return;
                          const rowName = nameIdx >= 0 ? String(row[nameIdx] || '').trim() : '';
                          const rowDob  = dobIdx  >= 0 ? String(row[dobIdx]  || '').trim() : '';
                          const nameMatch = patient.name && rowName ? rowName === patient.name : true;
                          const dobMatch  = patient.dob  && rowDob  ? rowDob  === patient.dob  : true;
                          if (nameMatch && dobMatch && (rowName === patient.name || rowDob === patient.dob)) {
                            const line = mapRowToEhr(type, sheet.headers, row);
                            if (line) lines.push(line);
                          }
                        });
                      } else {
                        // No identifier columns — fall back to same row index as patient
                        const idx = patientList.indexOf(patient);
                        const row = sheet.rows[idx];
                        if (row) {
                          const line = mapRowToEhr(type, sheet.headers, row);
                          if (line) lines.push(line);
                        }
                      }
                    });
                  });
                }

                // Store format flag for download button logic
                window._ehrExcelIsTableFormat = isTableFormat;
                resolve(lines.join('\n'));
              } catch (err) { reject(err); }
            };
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsArrayBuffer(uploadedFile);
          });
        } else {
          text = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = e => resolve(e.target.result.trim());
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsText(uploadedFile);
          });
        }
      } catch (e) {
        showError('Failed to read uploaded file: ' + e.message, []);
        return;
      }
    }
    if (!text) {
      showError('Please paste raw EHR data or upload a file.', []);
      return;
    }

    // Strip label/comment lines (✅ EHR MESSAGE ..., # comments, blank lines with only symbols)
    const validEhrTypes = new Set(['PATIENT','ENCOUNTER','ALLERGY','DIAGNOSIS','LAB_ORDER','LAB_RESULT','VITAL','IMMUNIZATION','INSURANCE','NK1','CHIEF_COMPLAINT','SYMPTOM','PROCEDURE','MEDICATION','CLINICAL_NOTE']);
    const cleanedLines = text.split('\n').filter(line => {
      const trimmed = line.trim();
      if (!trimmed) return false;
      if (trimmed.startsWith('#')) return false;
      const recType = trimmed.split('|')[0].trim().toUpperCase();
      return validEhrTypes.has(recType);
    });
    const cleanedText = cleanedLines.join('\n');
    if (!cleanedText) {
      showError('No valid EHR records found after filtering.', []);
      return;
    }

    // Count PATIENT lines — multi-patient EHR must use local converter (AI mixes data between patients)
    const patientCount = cleanedLines.filter(l => l.trim().split('|')[0].trim().toUpperCase() === 'PATIENT').length;
    const isMultiPatient = patientCount > 1;

    if (aiModeEnabled && isMultiPatient) {
      // Show notice but still convert locally
      const noticeBanner = document.getElementById('ai-active-banner');
      if (noticeBanner) { noticeBanner.textContent = `⚠ Multi-patient EHR (${patientCount} patients) — using local converter for accuracy`; noticeBanner.classList.remove('hidden'); }
    }

    if (aiModeEnabled && !isMultiPatient) {
      await aiConvertEhrToFhir(cleanedText);
    } else {
      await localConvertEhrToFhir(cleanedText);
    }
    return;
  }

  if (activeInputTab === 'file') {
    if (!uploadedFile) {
      showError('Please select a file to upload.', []);
      return;
    }
    await convertFile();
  } else {
    const text = hl7Input.value.trim();
    if (!text) {
      showError('Please paste an HL7 message or load a sample.', []);
      return;
    }
    if (aiModeEnabled) {
      await aiConvertHl7ToFhir(text);
    } else {
      await convertText(text);
    }
  }
});

// ---------------------------------------------------------------------------
// API Configuration
// ---------------------------------------------------------------------------
const API_BASE = window.location.protocol + '//' + window.location.hostname + ':8000';

async function convertText(text) {
  setLoading(true);
  try {
    const resp = await fetch(API_BASE + '/api/convert/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hl7_message: text }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'Conversion failed.', []);
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
  }
}

async function convertFhirToHl7(bundle) {
  setLoading(true);
  try {
    const resp = await fetch(API_BASE + '/api/convert/fhir-to-hl7', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fhir_bundle: bundle }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'Conversion failed.', []);
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
  }
}

async function convertFhirFileToHl7(file) {
  setLoading(true);
  try {
    const text = await file.text();
    let bundle;
    try {
      bundle = JSON.parse(text);
    } catch (e) {
      showError('File does not contain valid JSON: ' + e.message, []);
      return;
    }
    const resp = await fetch(API_BASE + '/api/convert/fhir-to-hl7', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fhir_bundle: bundle }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'Conversion failed.', []);
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
  }
}

// ---------------------------------------------------------------------------
// PHI masking helper — stores original values in phiMap for later unmask
// ---------------------------------------------------------------------------
let phiMap = null;

function maskPhiIfEnabled(text) {
  const cb = document.getElementById('mask-phi-checkbox');
  if (!cb || !cb.checked) { phiMap = null; return text; }

  phiMap = {};

  const masked = text.split('\n').map(line => {
    const fields = line.split('|');
    const seg = fields[0];

    // HL7 PID segment
    if (seg === 'PID') {
      if (fields[3]) phiMap.mrn = fields[3].split('^')[0].trim();
      if (fields[5]) {
        const n = fields[5].split('^');
        phiMap.lastName  = (n[0] || '').trim();
        phiMap.firstName = (n[1] || '').trim();
      }
      if (fields[7]) phiMap.dob = fields[7].trim(); // YYYYMMDD
      if (fields[11]) phiMap.address = fields[11].trim();
      if (fields[13]) phiMap.phone = fields[13].trim();

      if (fields[19]) phiMap.ssn = fields[19].trim();

      if (fields[3]  !== undefined) fields[3]  = '[MRN_MASKED]';
      if (fields[5]  !== undefined) fields[5]  = 'PATIENT^MASKED';
      if (fields[7]  !== undefined) fields[7]  = '19000101';
      if (fields[11] !== undefined) fields[11] = '123 MASKED ST^^CITY^ST^00000';
      if (fields[13] !== undefined) fields[13] = '(000)000-0000';
      if (fields[19] !== undefined) fields[19] = '[SSN_MASKED]';
      return fields.join('|');
    }

    // HL7 NK1 segment (next of kin)
    if (seg === 'NK1') {
      if (fields[2]) phiMap.nk1Name    = fields[2].trim();
      if (fields[4]) phiMap.nk1Address = fields[4].trim();
      if (fields[5]) phiMap.nk1Phone   = fields[5].trim();

      if (fields[2] !== undefined) fields[2] = 'NOK^MASKED';
      if (fields[4] !== undefined) fields[4] = '123 MASKED ST^^CITY^ST^00000';
      if (fields[5] !== undefined) fields[5] = '(000)000-0000';
      return fields.join('|');
    }

    // EHR PATIENT row: PATIENT|MRN|FirstName|LastName|DOB|Gender|Language|Phone|Address|City|State|Zip
    if (seg === 'PATIENT') {
      phiMap.mrn       = (fields[1] || '').trim();
      phiMap.firstName = (fields[2] || '').trim();
      phiMap.lastName  = (fields[3] || '').trim();
      phiMap.dob       = (fields[4] || '').trim(); // YYYY-MM-DD
      phiMap.phone     = (fields[7] || '').trim();
      phiMap.address   = (fields[8] || '').trim();
      phiMap.city      = (fields[9] || '').trim();

      if (fields[1] !== undefined) fields[1] = 'MRN_MASKED';
      if (fields[2] !== undefined) fields[2] = 'MASKED';
      if (fields[3] !== undefined) fields[3] = 'PATIENT';
      if (fields[4] !== undefined) fields[4] = '1900-01-01';
      if (fields[7] !== undefined) fields[7] = '(000)000-0000';
      if (fields[8] !== undefined) fields[8] = '123 MASKED ST';
      if (fields[9] !== undefined) fields[9] = 'CITY';
      return fields.join('|');
    }

    return line;
  }).join('\n');

  return masked;
}

// Replace masked placeholders with original PHI values in a JSON string
function applyPhiRestore(jsonStr) {
  if (!phiMap) return jsonStr;
  let s = jsonStr;
  // Convert HL7 DOB YYYYMMDD → FHIR YYYY-MM-DD if needed
  const dobFhir = phiMap.dob
    ? (phiMap.dob.includes('-') ? phiMap.dob
        : phiMap.dob.replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3'))
    : null;

  if (phiMap.lastName)  s = s.split('"PATIENT"').join(`"${phiMap.lastName}"`);
  if (phiMap.firstName) s = s.split('"MASKED"').join(`"${phiMap.firstName}"`);
  if (phiMap.mrn)       s = s.split('MRN_MASKED').join(phiMap.mrn);
  if (dobFhir)          s = s.split('"1900-01-01"').join(`"${dobFhir}"`);
  if (phiMap.phone)     s = s.split('"(000)000-0000"').join(`"${phiMap.phone}"`);
  if (phiMap.address)   s = s.split('"123 MASKED ST"').join(`"${phiMap.address}"`);
  if (phiMap.city && phiMap.city !== 'CITY')
                        s = s.split('"CITY"').join(`"${phiMap.city}"`);
  if (phiMap.ssn)       s = s.split('SSN_MASKED').join(phiMap.ssn);
  // NK1 / RelatedPerson restore
  if (phiMap.nk1Name) {
    const parts = phiMap.nk1Name.split('^');
    const nkLast  = (parts[0] || '').trim();
    const nkFirst = (parts[1] || '').trim();
    if (nkLast)  s = s.split('"NOK"').join(`"${nkLast}"`);
    if (nkFirst) s = s.split('"MASKED"').join(`"${nkFirst}"`);
  }
  if (phiMap.nk1Phone)   s = s.split('"(000)000-0000"').join(`"${phiMap.nk1Phone}"`);
  if (phiMap.nk1Address) s = s.split('"123 MASKED ST"').join(`"${phiMap.nk1Address}"`);
  return s;
}

let outputIsUnmasked = false;

// Returns FHIR JSON with PHI restored if the user has unmasked the output,
// otherwise returns the original (masked) FHIR JSON.
function getEffectiveFhirJson() {
  if (!currentResult || !currentResult.fhir_json) return null;
  if (!outputIsUnmasked || !phiMap) return currentResult.fhir_json;
  try {
    return JSON.parse(applyPhiRestore(JSON.stringify(currentResult.fhir_json)));
  } catch {
    return currentResult.fhir_json;
  }
}

window.toggleUnmask = function() {
  if (!phiMap || !currentResult) return;
  outputIsUnmasked = !outputIsUnmasked;

  const rawJson = JSON.stringify(currentResult.fhir_json, null, 2);
  const display = outputIsUnmasked ? applyPhiRestore(rawJson) : rawJson;

  const jsonEl = document.getElementById('json-output');
  if (jsonEl) jsonEl.innerHTML = syntaxHighlightJson(display);

  const btn = document.getElementById('unmask-btn');
  if (btn) {
    btn.textContent = outputIsUnmasked ? '🔒 Re-mask' : '🔓 Unmask';
    btn.classList.toggle('tool-btn-active', outputIsUnmasked);
  }
};

// ---------------------------------------------------------------------------
// AI conversion functions
// ---------------------------------------------------------------------------
async function aiConvertHl7ToFhir(text) {
  setLoading(true);
  try {
    const resp = await fetch(API_BASE + '/api/convert/ai/hl7-to-fhir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hl7_message: maskPhiIfEnabled(text), provider: getAIProvider() }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'AI conversion failed.', []);
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
  }
}

async function aiConvertFhirToHl7(bundle) {
  setLoading(true);
  try {
    const resp = await fetch(API_BASE + '/api/convert/ai/fhir-to-hl7', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fhir_bundle: bundle, provider: getAIProvider() }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'AI conversion failed.', []);
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
  }
}

async function localConvertEhrToFhir(ehrData) {
  setLoading(true);
  const spinnerLabel = document.getElementById('spinner-label');
  if (spinnerLabel) spinnerLabel.textContent = 'Converting EHR data to FHIR…';
  try {
    const resp = await fetch(API_BASE + '/api/convert/ehr-to-fhir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ehr_data: ehrData }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'EHR→FHIR conversion failed.', []);
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
    if (spinnerLabel) spinnerLabel.textContent = 'Converting…';
  }
}

async function aiConvertEhrToFhir(ehrData) {
  setLoading(true);
  const spinnerLabel = document.getElementById('spinner-label');
  if (spinnerLabel) spinnerLabel.textContent = 'AI converting EHR data to FHIR…';
  try {
    const resp = await fetch(API_BASE + '/api/convert/ai/ehr-to-fhir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ehr_data: maskPhiIfEnabled(typeof ehrData === 'string' ? ehrData : JSON.stringify(ehrData)), provider: getAIProvider() }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'EHR→FHIR conversion failed.', []);
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
    if (spinnerLabel) spinnerLabel.textContent = 'Converting…';
  }
}

async function convertFile() {
  setLoading(true);
  try {
    const formData = new FormData();
    formData.append('file', uploadedFile);
    const resp = await fetch(API_BASE + '/api/convert/file', {
      method: 'POST',
      body: formData,
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'Conversion failed.', []);
    } else if (data.batch) {
      // Show first successful result for batch; report summary
      const successes = data.results.filter(r => r.success);
      if (successes.length === 0) {
        showError(`None of the ${data.count} messages could be converted.`, []);
      } else {
        currentBatch = successes;  // store all for multi-message Excel/CSV export
        handleResult(successes[0]);
        if (data.count > 1) {
          addWarning(`Batch file: ${data.count} messages found, showing first result. Download to get all.`);
        }
      }
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
  }
}

// ---------------------------------------------------------------------------
// Result handling
// ---------------------------------------------------------------------------
function handleResult(result) {
  currentResult = result;
  if (!currentBatch) currentBatch = null;  // reset if not set by batch handler
  // Reset unmask state for new result
  outputIsUnmasked = false;
  // If this result was NOT from an AI+masked conversion, clear phiMap so unmask button stays hidden
  if (!result.ai_powered) phiMap = null;
  const unmaskBtn = document.getElementById('unmask-btn');
  if (unmaskBtn) {
    unmaskBtn.textContent = '🔓 Unmask';
    unmaskBtn.classList.remove('tool-btn-active');
    unmaskBtn.classList.toggle('hidden', !phiMap);
  }
  hideError();

  if (!result.success) {
    showError('Conversion failed.', result.errors || []);
    return;
  }

  // Show/hide AI output badge
  const aiOutputBadge = document.getElementById('ai-output-badge');
  if (aiOutputBadge) aiOutputBadge.classList.toggle('hidden', !result.ai_powered);

  const isFhirToHl7 = result.direction === 'fhir_to_hl7';
  const isEhrToFhir = result.direction === 'ehr_to_fhir';

  // Status bar
  statusBar.classList.remove('hidden');
  if (isFhirToHl7) {
    statusBadges.innerHTML = `
      <span class="status-badge status-success">✓ Converted</span>
      <span class="status-badge status-direction">FHIR → HL7</span>
      <span class="status-badge status-type">${escapeHtml(result.message_type || '?')}</span>
    `;
  } else if (isEhrToFhir) {
    statusBadges.innerHTML = `
      <span class="status-badge status-success">✓ Converted</span>
      <span class="status-badge status-direction" style="background:rgba(5,150,105,0.15);color:#047857;border-color:rgba(5,150,105,0.3)">⚕ EHR → FHIR</span>
      <span class="status-badge status-type">${escapeHtml(result.message_type || 'EHR')}</span>
      <span class="status-badge status-type">${(result.resource_summary || []).length} FHIR Resources</span>
    `;
  } else {
    statusBadges.innerHTML = `
      <span class="status-badge status-success">✓ Converted</span>
      <span class="status-badge status-version">HL7 ${escapeHtml(result.hl7_version || 'unknown')}</span>
      <span class="status-badge status-type">${escapeHtml(result.message_type || '?')}${result.message_event ? '^' + escapeHtml(result.message_event) : ''}</span>
      <span class="status-badge status-type">${(result.resource_summary || []).length} FHIR Resources</span>
    `;
  }

  warningList.innerHTML = '';
  (result.warnings || []).forEach(w => {
    const el = document.createElement('div');
    el.className = 'warning-item';
    el.innerHTML = `<span>⚠</span><span>${escapeHtml(w)}</span>`;
    warningList.appendChild(el);
  });

  // HL7 output (FHIR→HL7 direction)
  const hl7outEl = document.getElementById('hl7out-output');
  if (hl7outEl) hl7outEl.textContent = result.hl7_output ? result.hl7_output.replace(/\r/g, '\n') : '';

  // Hide CSV/Excel for FHIR→HL7; hide Excel only for table-format Excel EHR input
  const csvBtn = document.getElementById('btn-dl-csv');
  const excelBtn = document.getElementById('btn-dl-excel');
  const isTableExcelInput = isEhrToFhir && (window._ehrExcelIsTableFormat === true);
  if (csvBtn) csvBtn.classList.toggle('hidden', isFhirToHl7);
  if (excelBtn) excelBtn.classList.toggle('hidden', isFhirToHl7 || isTableExcelInput);

  // Show/hide mappings tab based on direction and content
  const mappingsTab = document.getElementById('out-tab-mappings');
  if (mappingsTab) {
    const hasMappings = (result.field_mappings || []).length > 0;
    if (isFhirToHl7 || isEhrToFhir) {
      mappingsTab.classList.toggle('hidden', !hasMappings);
    } else {
      mappingsTab.classList.remove('hidden');
    }
  }

  // Show/hide HL7 Message tab — irrelevant for EHR→FHIR direction
  const hl7outTab = document.getElementById('out-tab-hl7out');
  if (hl7outTab) {
    if (isEhrToFhir) {
      hl7outTab.classList.add('hidden');
    } else if (isFhirToHl7) {
      hl7outTab.classList.remove('hidden');
    } else {
      // HL7→FHIR: keep hidden (it's only for FHIR→HL7 output)
      hl7outTab.classList.add('hidden');
    }
  }

  // Activate the correct output tab for the current direction
  document.querySelectorAll('.output-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.out-content').forEach(c => c.classList.remove('active'));
  if (isFhirToHl7) {
    document.getElementById('out-tab-hl7out').classList.add('active');
    document.getElementById('out-hl7out').classList.add('active');
  } else {
    // Both HL7→FHIR and EHR→FHIR show JSON first
    document.getElementById('out-tab-json').classList.add('active');
    document.getElementById('out-json').classList.add('active');
  }

  // JSON
  const jsonStr = JSON.stringify(result.fhir_json, null, 2);
  jsonOutput.innerHTML = syntaxHighlightJson(jsonStr);

  // XML
  xmlOutput.textContent = result.fhir_xml || '';

  // PDF preview
  renderPDFPreview(result);

  // Summary
  summaryContent.innerHTML = '';
  (result.resource_summary || []).forEach(item => {
    const card = document.createElement('div');
    card.className = `summary-card rt-${item.resource_type}`;
    card.innerHTML = `
      <div class="summary-card-type">${escapeHtml(item.resource_type)}</div>
      <div class="summary-card-desc">${escapeHtml(item.description)}</div>
      <div class="summary-card-id">ID: ${escapeHtml(item.resource_id)}</div>
    `;
    summaryContent.appendChild(card);
  });

  // Field Mappings
  const mappingsContent = document.getElementById('mappings-content');
  mappingsContent.innerHTML = '';
  (result.field_mappings || []).forEach(resourceMapping => {
    const resourceDiv = document.createElement('div');
    resourceDiv.className = 'mapping-resource';

    const header = document.createElement('div');
    header.className = 'mapping-resource-header';
    header.textContent = `${resourceMapping.resource_type} - ${resourceMapping.resource_id}`;
    resourceDiv.appendChild(header);

    const table = document.createElement('table');
    table.className = 'mapping-table';

    const isEhr = result.direction === 'ehr_to_fhir';
    const thead = document.createElement('thead');
    thead.innerHTML = `
      <tr>
        <th style="width:20%">FHIR Field</th>
        <th style="width:15%">${isEhr ? 'EHR Record.Field' : 'HL7 Segment.Field'}</th>
        <th style="width:35%">${isEhr ? 'EHR Value' : 'HL7 Value'}</th>
        <th style="width:30%">Description</th>
      </tr>
    `;
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    (resourceMapping.field_mappings || []).forEach(mapping => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td class="mapping-fhir-field">${escapeHtml(mapping.fhir_field)}</td>
        <td>
          <span class="mapping-hl7-segment">${escapeHtml(mapping.hl7_segment)}</span>
          <span class="mapping-hl7-field">${escapeHtml(mapping.hl7_field)}</span>
        </td>
        <td class="mapping-hl7-value" title="${escapeHtml(mapping.hl7_value || '')}">${escapeHtml(mapping.hl7_value || 'N/A')}</td>
        <td class="mapping-description">${escapeHtml(mapping.description)}</td>
      `;
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    resourceDiv.appendChild(table);
    mappingsContent.appendChild(resourceDiv);
  });

  outputPanel.classList.remove('hidden');
  outputPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function addWarning(msg) {
  const el = document.createElement('div');
  el.className = 'warning-item';
  el.innerHTML = `<span>⚠</span><span>${escapeHtml(msg)}</span>`;
  warningList.appendChild(el);
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// PDF Report
// ---------------------------------------------------------------------------
function renderPDFPreview(result) {
  if (!pdfPreview) return;
  const msgType  = (result.message_type || 'Unknown').toUpperCase();
  const ts       = result.timestamp ? new Date(result.timestamp).toLocaleString() : new Date().toLocaleString();
  const warnings = result.warnings || [];
  const summary  = result.resource_summary || [];
  const mappings = result.field_mappings || [];

  let html = `
    <div class="pdf-prev-header">
      <div class="pdf-prev-title">HL7 → FHIR Conversion Report</div>
      <div class="pdf-prev-meta">
        <span><strong>Message Type:</strong> ${escapeHtml(msgType)}</span>
        <span><strong>Converted:</strong> ${escapeHtml(ts)}</span>
        <span><strong>Resources:</strong> ${summary.length}</span>
        <span><strong>Warnings:</strong> ${warnings.length}</span>
      </div>
    </div>`;

  if (warnings.length) {
    html += `<div class="pdf-prev-section"><div class="pdf-prev-section-title">Warnings</div><ul class="pdf-prev-warnings">`;
    warnings.forEach(w => { html += `<li>${escapeHtml(w)}</li>`; });
    html += `</ul></div>`;
  }

  if (summary.length) {
    html += `<div class="pdf-prev-section"><div class="pdf-prev-section-title">Resource Summary</div>
      <table class="pdf-prev-table"><thead><tr><th>Resource Type</th><th>Resource ID</th><th>Description</th></tr></thead><tbody>`;
    summary.forEach(r => {
      html += `<tr><td><span class="rt-badge rt-${escapeHtml(r.resource_type)}">${escapeHtml(r.resource_type)}</span></td><td class="mono">${escapeHtml(r.resource_id)}</td><td>${escapeHtml(r.description)}</td></tr>`;
    });
    html += `</tbody></table></div>`;
  }

  mappings.forEach(rm => {
    html += `<div class="pdf-prev-section"><div class="pdf-prev-section-title">${escapeHtml(rm.resource_type)} — ${escapeHtml(rm.resource_id)}</div>
      <table class="pdf-prev-table pdf-mapping-table" style="table-layout:fixed;width:100%">
        <colgroup><col style="width:20%"><col style="width:15%"><col style="width:35%"><col style="width:30%"></colgroup>
        <thead><tr><th>FHIR Field</th><th>${currentResult && currentResult.direction === 'ehr_to_fhir' ? 'EHR Record.Field' : 'HL7 Segment.Field'}</th><th>${currentResult && currentResult.direction === 'ehr_to_fhir' ? 'EHR Value' : 'HL7 Value'}</th><th>Description</th></tr></thead><tbody>`;
    (rm.field_mappings || []).forEach(f => {
      html += `<tr>
        <td class="mono" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(f.fhir_field)}</td>
        <td style="white-space:nowrap"><span class="mapping-hl7-segment">${escapeHtml(f.hl7_segment)}</span> <span class="mapping-hl7-field">${escapeHtml(f.hl7_field)}</span></td>
        <td class="mono" style="word-break:break-all;white-space:normal" title="${escapeHtml(f.hl7_value||'')}">${escapeHtml(f.hl7_value||'N/A')}</td>
        <td style="white-space:normal">${escapeHtml(f.description)}</td>
      </tr>`;
    });
    html += `</tbody></table></div>`;
  });

  pdfPreview.innerHTML = html;
}

window.generatePDF = function() {
  if (!currentResult) return;
  const { jsPDF } = window.jspdf;
  if (!jsPDF) { alert('PDF library not loaded. Check your internet connection.'); return; }

  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pageW   = doc.internal.pageSize.getWidth();
  const margin  = 14;
  const colW    = pageW - margin * 2;
  let   y       = 0;

  const msgType  = (currentResult.message_type || 'Unknown').toUpperCase();
  const ts       = currentResult.timestamp ? new Date(currentResult.timestamp).toLocaleString() : new Date().toLocaleString();
  const warnings = currentResult.warnings || [];
  const mappings = currentResult.field_mappings || [];

  // Use effective (possibly unmasked) FHIR JSON to build resource summary for PDF
  const effectiveFhir = getEffectiveFhirJson();
  const summary = effectiveFhir && effectiveFhir.entry
    ? effectiveFhir.entry
        .filter(e => e.resource)
        .map(e => {
          const r = e.resource;
          const rt = r.resourceType || 'Unknown';
          let desc = r.id || '';
          if (rt === 'Patient' && r.name && r.name[0]) {
            const n = r.name[0];
            desc = [n.family, ...(n.given || [])].filter(Boolean).join(', ');
          } else if (r.code && r.code.text) {
            desc = r.code.text;
          } else if (r.medicationCodeableConcept && r.medicationCodeableConcept.text) {
            desc = r.medicationCodeableConcept.text;
          }
          return { resource_type: rt, resource_id: r.id || '', description: desc };
        })
    : (currentResult.resource_summary || []);

  // ---- Header bar ----
  doc.setFillColor(30, 64, 175);          // blue-800
  doc.rect(0, 0, pageW, 22, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('HL7 → FHIR Conversion Report', margin, 9);
  doc.setFontSize(8);
  doc.setFont('helvetica', 'normal');
  doc.text(`Message Type: ${msgType}   |   ${ts}   |   ${summary.length} resource(s)   |   ${warnings.length} warning(s)`, margin, 17);
  y = 28;
  doc.setTextColor(0, 0, 0);

  // ---- Warnings ----
  if (warnings.length) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(180, 100, 0);
    doc.text('Warnings', margin, y);
    y += 4;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(80, 80, 80);
    warnings.forEach(w => {
      const lines = doc.splitTextToSize(`• ${w}`, colW);
      doc.text(lines, margin, y);
      y += lines.length * 4 + 1;
    });
    y += 4;
    doc.setTextColor(0, 0, 0);
  }

  // ---- Resource Summary ----
  if (summary.length) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 64, 175);
    doc.text('Resource Summary', margin, y);
    y += 2;
    doc.setTextColor(0, 0, 0);
    doc.autoTable({
      startY: y,
      margin: { left: margin, right: margin },
      headStyles: { fillColor: [30, 64, 175], textColor: 255, fontStyle: 'bold', fontSize: 8 },
      bodyStyles: { fontSize: 7.5 },
      alternateRowStyles: { fillColor: [240, 245, 255] },
      head: [['Resource Type', 'Resource ID', 'Description']],
      body: summary.map(r => [r.resource_type, r.resource_id, r.description]),
      columnStyles: { 0: { cellWidth: 35 }, 1: { cellWidth: 45 } },
    });
    y = doc.lastAutoTable.finalY + 8;
  }

  // ---- Field Mappings per resource ----
  mappings.forEach(rm => {
    if (y > 260) { doc.addPage(); y = 14; }
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 64, 175);
    doc.text(`${rm.resource_type}  —  ${rm.resource_id}`, margin, y);
    y += 2;
    doc.setTextColor(0, 0, 0);
    const tableWidth = pageW - margin * 2;
    doc.autoTable({
      startY: y,
      margin: { left: margin, right: margin },
      tableWidth: tableWidth,
      headStyles: { fillColor: [51, 102, 204], textColor: 255, fontStyle: 'bold', fontSize: 7.5, halign: 'left' },
      bodyStyles: { fontSize: 7, valign: 'top', overflow: 'linebreak' },
      alternateRowStyles: { fillColor: [245, 247, 255] },
      head: [[
        'FHIR Field',
        currentResult && currentResult.direction === 'ehr_to_fhir' ? 'EHR Record.Field' : 'HL7 Segment.Field',
        currentResult && currentResult.direction === 'ehr_to_fhir' ? 'EHR Value' : 'HL7 Value',
        'Description'
      ]],
      body: (rm.field_mappings || []).map(f => [
        f.fhir_field,
        `${f.hl7_segment}  ${f.hl7_field}`,
        f.hl7_value || 'N/A',
        f.description,
      ]),
      columnStyles: {
        0: { cellWidth: tableWidth * 0.20, fontStyle: 'bold' },
        1: { cellWidth: tableWidth * 0.15 },
        2: { cellWidth: tableWidth * 0.35, font: 'courier', fontSize: 6.5 },
        3: { cellWidth: tableWidth * 0.30 },
      },
    });
    y = doc.lastAutoTable.finalY + 8;
  });

  // ---- Footer on every page ----
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(7);
    doc.setTextColor(150, 150, 150);
    doc.text(`HL7→FHIR Converter  |  Page ${i} of ${pageCount}`, margin, doc.internal.pageSize.getHeight() - 6);
    doc.text(ts, pageW - margin, doc.internal.pageSize.getHeight() - 6, { align: 'right' });
  }

  const safeName = `fhir_report_${msgType}_${Date.now()}.pdf`;
  doc.save(safeName);
};

// Copy & Download
// ---------------------------------------------------------------------------
window.copyOutput = async function(type) {
  if (!currentResult) return;
  let text = '';
  let btnEl;
  if (type === 'json') {
    text = JSON.stringify(getEffectiveFhirJson(), null, 2);
    btnEl = document.querySelector('#out-json .tool-btn');
  } else if (type === 'xml') {
    text = currentResult.fhir_xml || '';
    btnEl = document.querySelector('#out-xml .tool-btn');
  } else if (type === 'hl7out') {
    text = (currentResult.hl7_output || '').replace(/\r/g, '\n');
    btnEl = document.querySelector('#out-hl7out .tool-btn');
  }

  try {
    await navigator.clipboard.writeText(text);
    if (btnEl) {
      const orig = btnEl.innerHTML;
      btnEl.innerHTML = '✓ Copied!';
      btnEl.classList.add('copied');
      setTimeout(() => { btnEl.innerHTML = orig; btnEl.classList.remove('copied'); }, 1800);
    }
  } catch {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
};

// Helper: compact timestamp string "20260320_221302" for filenames
window.getTs = function() {
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
};

// Helper: build a patient-aware base filename e.g. "FHIR_John_Doe_1980-03-15" or "FHIR_Multiple_Patients"
window.getPatientBasename = function() {
  const fhir = getEffectiveFhirJson();
  if (!fhir) return 'FHIR_Export';
  const entries = (fhir.entry || []);
  const patients = entries.filter(e => e.resource && e.resource.resourceType === 'Patient').map(e => e.resource);
  if (patients.length === 0) return 'FHIR_Export';
  if (patients.length > 1) return 'FHIR_Multiple_Patients';
  const p = patients[0];
  let first = 'Patient', last = '', dob = '';
  if (p.name && p.name[0]) {
    if (p.name[0].given) first = p.name[0].given[0] || first;
    if (p.name[0].family) last = p.name[0].family;
  }
  if (p.birthDate) dob = '_' + p.birthDate;
  const name = [first, last].filter(Boolean).join('_').replace(/[^a-z0-9_-]/gi, '_');
  return `FHIR_${name}${dob}`;
};

window.downloadOutput = function(type, filename, mimeType) {
  if (!currentResult) return;
  
  if (type === 'csv' || type === 'xlsx') {
    exportDataToSpreadsheet(type, filename);
    return;
  }

  const effectiveFhir = getEffectiveFhirJson();
  if (type === 'json' && effectiveFhir && effectiveFhir.entry) {
    downloadPatientGroupedJson();
    return;
  }

  let content = '';
  if (type === 'json') {
    content = JSON.stringify(effectiveFhir, null, 2);
  } else if (type === 'xml') {
    content = currentResult.fhir_xml || '';
  } else if (type === 'hl7out') {
    content = (currentResult.hl7_output || '').replace(/\r/g, '\n');
  }
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

function downloadPatientGroupedJson() {
  const effectiveFhir = getEffectiveFhirJson();
  const entries = (effectiveFhir && effectiveFhir.entry) ? effectiveFhir.entry : [];
  const patientGroups = {}; // key: patientId, value: array of entries

  let lastPid = 'unknown';

  // Group entries by their patient reference
  entries.forEach(entry => {
    const r = entry.resource;
    if (!r) return;
    
    let pid = 'unknown';
    if (r.resourceType === 'Patient') {
      pid = r.id || 'unknown';
    } else if (r.subject && r.subject.reference && r.subject.reference.startsWith('Patient/')) {
      pid = r.subject.reference.substring(8);
    } else if (r.patient && r.patient.reference && r.patient.reference.startsWith('Patient/')) {
      pid = r.patient.reference.substring(8);
    }
    
    // Assign orphaned resources (like Practitioner) to the last seen Patient
    if (pid !== 'unknown') {
      lastPid = pid;
    } else {
      pid = lastPid;
    }
    
    if (pid === 'unknown') return; // Exclude anything before the first patient

    if (!patientGroups[pid]) patientGroups[pid] = [];
    patientGroups[pid].push(entry);
  });

  const pids = Object.keys(patientGroups);

  // Fallback if no specific patients exist
  if (pids.length === 0 || (pids.length === 1 && pids[0] === 'unknown')) {
    const content = JSON.stringify(getEffectiveFhirJson(), null, 2);
    downloadFile(content, 'fhir_bundle.json', 'application/json');
    return;
  }

  const generatedFiles = [];

  pids.forEach(pid => {
    const groupEntries = patientGroups[pid];
    const patientEntry = groupEntries.find(e => e.resource && e.resource.resourceType === 'Patient');
    const patientRes = patientEntry ? patientEntry.resource : null;
    
    let fName = 'patient';
    let lName = pid;
    let dob = 'unknown';
    
    // Extract naming metadata
    if (patientRes) {
      if (patientRes.name && patientRes.name[0]) {
        if (patientRes.name[0].given && patientRes.name[0].given.length > 0) fName = patientRes.name[0].given.join('_');
        if (patientRes.name[0].family) lName = patientRes.name[0].family;
      }
      if (patientRes.birthDate) dob = patientRes.birthDate;
    }
    
    // Sanitize filename
    const namepart = [fName, lName].filter(Boolean).join('_');
    let fileName = `FHIR_${namepart}_${dob}`.replace(/[^a-z0-9_-]/gi, '_');
    fileName += '.json';

    const bundle = {
      resourceType: 'Bundle',
      type: 'collection',
      entry: groupEntries
    };
    
    generatedFiles.push({ name: fileName, content: JSON.stringify(bundle, null, 2) });
  });

  if (generatedFiles.length === 1) {
    // Only 1 patient -> Download JSON directly with timestamp
    const ts = getTs();
    downloadFile(generatedFiles[0].content, generatedFiles[0].name.replace('.json', `_${ts}.json`), 'application/json');
  } else {
    // Multiple patients -> Zip them using JSZip with timestamp
    if (!window.JSZip) {
      alert("ZIP library is not loaded. Cannot export multiple JSONs.");
      return;
    }
    const zip = new JSZip();
    generatedFiles.forEach(f => {
      zip.file(f.name, f.content);
    });
    zip.generateAsync({ type: "blob" }).then(function(content) {
      const url = URL.createObjectURL(content);
      const link = document.createElement("a");
      link.href = url;
      link.download = `FHIR_Multiple_Patients_${getTs()}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    });
  }
}

function flattenObject(obj, prefix, result) {
  prefix = prefix || '';
  result = result || {};
  for (const key in obj) {
    if (!Object.prototype.hasOwnProperty.call(obj, key)) continue;
    const val = obj[key];
    const newKey = prefix ? prefix + '.' + key : key;
    if (val === null || val === undefined) {
      result[newKey] = '';
    } else if (Array.isArray(val)) {
      val.forEach((item, i) => {
        if (item !== null && typeof item === 'object') {
          flattenObject(item, newKey, result);
        } else {
          // only add if key not already set (first value wins)
          if (!(newKey in result)) result[newKey] = item;
        }
      });
    } else if (typeof val === 'object') {
      flattenObject(val, newKey, result);
    } else {
      result[newKey] = val;
    }
  }
  return result;
}

function buildSheetsFromResult(result, sheets) {
  // Build rows from field_mappings — skip label-only entries (no actual field data)
  (result.field_mappings || []).forEach(rm => {
    // Skip label/separator entries (no field data)
    if (!rm.field_mappings || rm.field_mappings.length === 0) return;

    let rt = rm.resource_type;
    const seg = rm.field_mappings[0].hl7_segment;
    if (seg) {
      rt = seg.toLowerCase().split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
      if (rt === "Medication") rt = "Medication Statement";
    } else {
      if (rt === "ClinicalImpression") rt = "Clinical note";
      if (rt === "AllergyIntolerance") rt = "Allergy";
    }
    rt = rt.substring(0, 31);

    // Skip any tab whose name looks like a message label (e.g. "Ehr Message 3 – Emergency App")
    if (/^ehr\s+message\s*\d/i.test(rt)) return;
    if (!sheets[rt]) sheets[rt] = [];
    const row = {};
    rm.field_mappings.forEach(f => {
      const colName = f.description || f.fhir_field;
      row[colName] = f.hl7_value || '';
    });
    // Only push rows that start from Patient (skip rows with no meaningful data)
    if (Object.values(row).some(v => v !== '')) sheets[rt].push(row);
  });

  // Fallback: build from FHIR bundle when field_mappings is empty (AI mode)
  if (Object.keys(sheets).length === 0 && result.fhir_json) {
    try {
      const bundle = typeof result.fhir_json === 'string'
        ? JSON.parse(result.fhir_json) : result.fhir_json;
      // Start from Patient — skip entries before first Patient resource
      let patientSeen = false;
      (bundle.entry || []).forEach(entry => {
        const res = entry.resource;
        if (!res) return;
        if (res.resourceType === 'Patient') patientSeen = true;
        if (!patientSeen) return;  // skip entries before Patient
        const rt = (res.resourceType || 'Resource').substring(0, 31);
        if (!sheets[rt]) sheets[rt] = [];
        sheets[rt].push(flattenObject(res));
      });
    } catch (e) { /* ignore */ }
  }
}

function exportDataToSpreadsheet(format, filename) {
  if (!currentResult) return;
  if (!window.XLSX) {
    alert("Spreadsheet library is not loaded. Check internet connection.");
    return;
  }

  const wb = XLSX.utils.book_new();

  // For batch (multiple messages), build one set of sheets per message
  const resultsToExport = currentBatch && currentBatch.length > 1 ? currentBatch : [currentResult];

  if (resultsToExport.length > 1) {
    // Multi-message: prefix each sheet with "Msg1_", "Msg2_", etc.
    resultsToExport.forEach((res, idx) => {
      const prefix = `Msg${idx + 1}_`;
      const sheets = {};
      buildSheetsFromResult(res, sheets);
      // Apply PHI restore if unmasked
      if (outputIsUnmasked && phiMap && Object.keys(sheets).length > 0) {
        const restored = JSON.parse(applyPhiRestore(JSON.stringify(sheets)));
        Object.keys(restored).forEach(k => { sheets[k] = restored[k]; });
      }
      Object.entries(sheets).forEach(([rt, rows]) => {
        if (rows.length === 0) return;
        const sheetName = (prefix + rt).substring(0, 31);
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(rows), sheetName);
      });
    });
  } else {
    // Single message
    const sheets = {};
    buildSheetsFromResult(currentResult, sheets);
    // Apply PHI restore if unmasked
    if (outputIsUnmasked && phiMap && Object.keys(sheets).length > 0) {
      const restored = JSON.parse(applyPhiRestore(JSON.stringify(sheets)));
      Object.keys(restored).forEach(k => { sheets[k] = restored[k]; });
    }
    Object.entries(sheets).forEach(([rt, rows]) => {
      if (rows.length === 0) return;
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(rows), rt);
    });
  }

  if (wb.SheetNames.length === 0) {
    alert("No mapped data available to export.");
    return;
  }

  // Apply styling to all sheets in the workbook
  wb.SheetNames.forEach(sheetName => {
    const ws = wb.Sheets[sheetName];
    if (!ws['!ref']) return;
    const range = XLSX.utils.decode_range(ws['!ref']);
    for (let R = range.s.r; R <= range.e.r; ++R) {
      for (let C = range.s.c; C <= range.e.c; ++C) {
        const address = XLSX.utils.encode_cell({ c: C, r: R });
        if (!ws[address]) continue;
        if (R === 0) {
          ws[address].s = {
            fill: { fgColor: { rgb: "FF4F81BD" } },
            font: { bold: true, color: { rgb: "FFFFFFFF" } },
            border: { top: { style: "thin", color: { rgb: "FF000000" } }, bottom: { style: "thin", color: { rgb: "FF000000" } }, left: { style: "thin", color: { rgb: "FF000000" } }, right: { style: "thin", color: { rgb: "FF000000" } } },
            alignment: { horizontal: "center", vertical: "center" }
          };
        } else {
          ws[address].s = { border: { top: { style: "hair", color: { rgb: "FFCCCCCC" } }, bottom: { style: "hair", color: { rgb: "FFCCCCCC" } }, left: { style: "hair", color: { rgb: "FFCCCCCC" } }, right: { style: "hair", color: { rgb: "FFCCCCCC" } } } };
        }
      }
    }
    // Auto-size columns
    const rows = XLSX.utils.sheet_to_json(ws);
    if (rows.length > 0) {
      const keys = Object.keys(rows[0]);
      ws['!cols'] = keys.map(k => ({ wch: Math.min(50, Math.max(k.length, ...rows.map(r => String(r[k] || '').length)) + 4) }));
    }
  });

  if (format === 'csv') {
    // Build CSV from the workbook sheets already populated above
    if (wb.SheetNames.length === 1) {
      // Single sheet — direct CSV download
      const csvStr = XLSX.utils.sheet_to_csv(wb.Sheets[wb.SheetNames[0]]);
      downloadFile(csvStr, filename.replace('.zip', '.csv'), "text/csv");
      return;
    }
    // Multiple sheets — zip them
    if (!window.JSZip) {
      alert("ZIP library is not loaded. Cannot export multiple CSVs.");
      return;
    }
    const zip = new JSZip();
    wb.SheetNames.forEach(sheetName => {
      const csvStr = XLSX.utils.sheet_to_csv(wb.Sheets[sheetName]);
      zip.file(`${sheetName}.csv`, csvStr);
    });
    zip.generateAsync({ type: "blob" }).then(function(content) {
      const url = URL.createObjectURL(content);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename.replace('.csv', '.zip');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    });
  } else {
    try {
      const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      const blob = new Blob([wbout], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Error generating Excel file:", err);
      // Fallback
      XLSX.writeFile(wb, filename);
    }
  }
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------
function setLoading(loading) {
  convertBtn.disabled = loading;
  spinner.classList.toggle('hidden', !loading);
}

function showError(msg, errors) {
  errorPanel.classList.remove('hidden');
  errorMessage.textContent = msg;
  errorList.innerHTML = '';
  // Detect rate-limit / quota errors and suggest switching AI provider
  const allText = [msg, ...(errors || [])].join(' ').toLowerCase();
  const isRateLimit = allText.includes('rate limit') || allText.includes('daily') || allText.includes('token limit') || allText.includes('quota') || allText.includes('429');
  if (isRateLimit && aiModeEnabled) {
    const provider = getAIProvider();
    const other = provider === 'groq' ? 'Claude' : 'Groq';
    const li = document.createElement('li');
    li.style.cssText = 'color:#f59e0b;font-weight:600;';
    li.textContent = `💡 Tip: Switch to ${other} in the AI provider selector above and try again.`;
    errorList.appendChild(li);
  }
  errors.forEach(e => {
    const li = document.createElement('li');
    li.textContent = e;
    errorList.appendChild(li);
  });
  outputPanel.classList.add('hidden');
  statusBar.classList.add('hidden');
}

function hideError() {
  errorPanel.classList.add('hidden');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// JSON syntax highlighting
// ---------------------------------------------------------------------------
function syntaxHighlightJson(json) {
  return json
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      match => {
        let cls = 'json-num';
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = 'json-key';
          } else {
            cls = 'json-str';
          }
        } else if (/true|false/.test(match)) {
          cls = 'json-bool';
        } else if (/null/.test(match)) {
          cls = 'json-null';
        }
        return `<span class="${cls}">${match}</span>`;
      }
    );
}

// ---------------------------------------------------------------------------
// History functions
// ---------------------------------------------------------------------------
let historyDebounceTimer = null;

// Attach event listeners to new filter inputs
document.getElementById('hist-name-filter')?.addEventListener('input', () => {
  clearTimeout(historyDebounceTimer);
  historyDebounceTimer = setTimeout(loadHistory, 300);
});
document.getElementById('hist-time-filter')?.addEventListener('change', (e) => {
  const wrap = document.getElementById('hist-date-range-wrap');
  if (wrap) wrap.style.display = (e.target.value === 'custom') ? 'flex' : 'none';
  loadHistory();
});
document.getElementById('hist-dob-filter')?.addEventListener('input', () => {
  clearTimeout(historyDebounceTimer);
  historyDebounceTimer = setTimeout(loadHistory, 300);
});
document.getElementById('hist-addr-filter')?.addEventListener('input', () => {
  clearTimeout(historyDebounceTimer);
  historyDebounceTimer = setTimeout(loadHistory, 300);
});
document.getElementById('hist-start-date')?.addEventListener('change', loadHistory);
document.getElementById('hist-end-date')?.addEventListener('change', loadHistory);

async function loadHistory() {
  try {
    const timeFilter = document.getElementById('hist-time-filter')?.value || '1d';
    const startDate = document.getElementById('hist-start-date')?.value || '';
    const endDate = document.getElementById('hist-end-date')?.value || '';
    const nameStr = document.getElementById('hist-name-filter')?.value || '';
    const dobStr = document.getElementById('hist-dob-filter')?.value || '';
    const addrStr = document.getElementById('hist-addr-filter')?.value || '';
    
    const params = new URLSearchParams();
    params.append('time_filter', timeFilter);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (nameStr) params.append('name', nameStr);
    if (dobStr) params.append('dob', dobStr);
    if (addrStr) params.append('address', addrStr);

    const resp = await fetch(API_BASE + '/api/history/db/search?' + params.toString());
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || 'Failed to search patients');
    }
    historyItems = data.results || [];
    renderHistory();
  } catch (err) {
    console.error('Failed to search patients:', err);
    historyItems = [];
    renderHistory();
  }
}

async function clearHistory() {
  // UI Clear now resets the filter inputs
  const n = document.getElementById('hist-name-filter'); if (n) n.value = '';
  const d = document.getElementById('hist-dob-filter'); if (d) d.value = '';
  const a = document.getElementById('hist-addr-filter'); if (a) a.value = '';
  const sd = document.getElementById('hist-start-date'); if (sd) sd.value = '';
  const ed = document.getElementById('hist-end-date'); if (ed) ed.value = '';
  const tf = document.getElementById('hist-time-filter'); 
  if (tf) {
    tf.value = '1d';
    const wrap = document.getElementById('hist-date-range-wrap');
    if (wrap) wrap.style.display = 'none';
  }
  loadHistory();
}

// Map FHIR resource types to friendly display labels
const RESOURCE_TYPE_LABELS = {
  Patient:             'Patient Demographics',
  Encounter:           'Encounter / Visit',
  Observation:         'Lab Results / Vitals',
  DiagnosticReport:    'Diagnostic Report',
  AllergyIntolerance:  'Allergies',
  Condition:           'Conditions / Diagnoses',
  Procedure:           'Procedures',
  MedicationRequest:   'Medication Orders',
  MedicationStatement: 'Medications',
  Immunization:        'Immunizations',
  Coverage:            'Insurance / Coverage',
  Organization:        'Organization',
  Practitioner:        'Practitioner',
  RelatedPerson:       'Related Person / NOK',
  ServiceRequest:      'Orders',
  ClinicalImpression:  'Clinical Notes',
};

function friendlyType(t) {
  return RESOURCE_TYPE_LABELS[t] || t;
}

function renderHistory() {
  if (historyItems.length === 0) {
    historyList.innerHTML = `
      <div class="history-empty">
        <span>📋</span>
        <p>No patients found matching your search criteria.</p>
      </div>
    `;
    return;
  }

  const SOURCE_COLORS = {
    'HL7→FHIR':        { bg:'rgba(59,130,246,0.15)',  color:'#3b82f6', border:'rgba(59,130,246,0.35)' },
    'HL7→FHIR (AI)':   { bg:'rgba(139,92,246,0.15)', color:'#8b5cf6', border:'rgba(139,92,246,0.35)' },
    'EHR→FHIR':        { bg:'rgba(16,185,129,0.15)', color:'#10b981', border:'rgba(16,185,129,0.35)' },
    'EHR→FHIR (AI)':   { bg:'rgba(16,185,129,0.2)',  color:'#059669', border:'rgba(16,185,129,0.35)' },
    'FHIR→HL7':        { bg:'rgba(245,158,11,0.15)', color:'#f59e0b', border:'rgba(245,158,11,0.35)' },
  };

  function srcChip(src) {
    const s = SOURCE_COLORS[src] || { bg:'rgba(107,114,128,0.15)', color:'#6b7280', border:'rgba(107,114,128,0.3)' };
    return `<span style="padding:2px 7px; border-radius:10px; font-size:0.72rem;
      background:${s.bg}; color:${s.color}; border:1px solid ${s.border}; white-space:nowrap;">${src}</span>`;
  }

  const html = historyItems.map((item) => {
    const p = item.patient_data || {};
    const mrn = item.patient_mrn;
    const conversions = item.conversions || [];

    // Patient name — from ConversionLog.patient_name or FHIR data
    let displayName = item.patient_name || '';
    if (!displayName && p.name && p.name[0]) {
      const n = p.name[0];
      displayName = [(n.given || []).join(' '), n.family].filter(Boolean).join(' ');
    }
    displayName = displayName || 'Unknown Patient';

    const dob = p.birthDate || '—';
    const gender = p.gender ? ` · ${p.gender.charAt(0).toUpperCase() + p.gender.slice(1)}` : '';
    let addrStr = '';
    if (p.address && p.address[0]) {
      const a = p.address[0];
      addrStr = [(a.line || []).join(' '), a.city, a.state].filter(Boolean).join(', ');
    }

    // Individual audit rows — one per conversion event
    const convRows = conversions.map(c => {
      const ts = new Date(c.converted_at).toLocaleString();
      const warnBadge = (c.warnings || []).length
        ? `<span style="color:#f59e0b;font-size:0.72rem;margin-left:6px;">⚠ ${c.warnings.length} warning(s)</span>` : '';
      const dqBadge = (c.dq_issues || []).length
        ? `<span style="color:#ef4444;font-size:0.72rem;margin-left:6px;">🔍 ${c.dq_issues.length} DQ issue(s)</span>` : '';
      return `
        <tr style="border-top:1px solid var(--border);">
          <td style="padding:6px 8px; font-size:0.82rem; font-family:monospace; white-space:nowrap;">${escapeHtml(c.message_type)}</td>
          <td style="padding:6px 8px;">${srcChip(c.conversion_source)}</td>
          <td style="padding:6px 8px; font-size:0.8rem; color:var(--text-muted); white-space:nowrap;">${escapeHtml(ts)}${warnBadge}${dqBadge}</td>
          <td style="padding:6px 8px; text-align:right;">
            <button onclick="loadLogBundle('${c.log_id}','${escapeHtml(c.message_type)}','${escapeHtml(c.conversion_source)}')"
              style="background:var(--primary); color:white; border:none; padding:4px 12px; border-radius:5px; cursor:pointer; font-size:0.78rem; white-space:nowrap;">
              📂 View
            </button>
          </td>
        </tr>`;
    }).join('');

    return `
      <div class="history-item history-success" data-mrn="${mrn}" style="padding:14px 16px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
          <div>
            <div style="font-weight:700; font-size:1.05rem; color:var(--text);">👤 ${escapeHtml(displayName)}${gender}</div>
            <div style="font-size:0.82rem; color:var(--text-muted); margin-top:2px;">
              <strong>MRN:</strong> <span class="mono">${escapeHtml(mrn)}</span>
              &nbsp;·&nbsp;<strong>DOB:</strong> ${escapeHtml(dob)}
              ${addrStr ? `&nbsp;·&nbsp;<strong>Location:</strong> ${escapeHtml(addrStr)}` : ''}
            </div>
          </div>
          <div style="font-size:0.78rem; color:var(--text-muted); text-align:right;">
            ${conversions.length} conversion record${conversions.length !== 1 ? 's' : ''}
          </div>
        </div>
        <div style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; font-size:0.82rem;">
            <thead>
              <tr style="text-transform:uppercase; font-size:0.68rem; color:var(--text-muted); letter-spacing:0.05em;">
                <th style="padding:4px 8px; text-align:left; font-weight:600;">Message Type</th>
                <th style="padding:4px 8px; text-align:left; font-weight:600;">Conversion</th>
                <th style="padding:4px 8px; text-align:left; font-weight:600;">Date &amp; Time</th>
                <th style="padding:4px 8px; text-align:right; font-weight:600;">Action</th>
              </tr>
            </thead>
            <tbody>${convRows}</tbody>
          </table>
        </div>
      </div>
    `;
  }).join('');

  historyList.innerHTML = html;
}

/**
 * Strip fields that are added synthetically by the FHIR mapper
 * and were NOT present in the original HL7 / EHR message.
 */
function cleanBundleForDisplay(bundle) {
  if (!bundle) return bundle;
  const clean = JSON.parse(JSON.stringify(bundle));
  
  // Recursively remove "system" keys and synthetic UUID-based IDs
  const sanitize = (obj) => {
    if (Array.isArray(obj)) {
      obj.forEach(sanitize);
    } else if (obj !== null && typeof obj === 'object') {
      // 1. Remove "system" key as requested
      if ('system' in obj) delete obj.system;
      
      // 2. Remove UUID-like IDs (synthetic database primary keys)
      if (obj.resourceType && obj.id && /^[0-9a-f]{8,}$/i.test(obj.id)) {
        delete obj.id;
      }
      
      // 3. Remove metadata if it's just profile references
      if (obj.meta) {
        const metaKeys = Object.keys(obj.meta).filter(k => k !== 'profile');
        if (metaKeys.length === 0) delete obj.meta;
      }
      
      // Keep traversing
      Object.values(obj).forEach(sanitize);
    }
  };

  delete clean.id;
  if (Array.isArray(clean.entry)) {
    clean.entry = clean.entry.map(e => {
      delete e.fullUrl;
      if (e.resource) sanitize(e.resource);
      return e;
    });
  }
  return clean;
}

async function loadLogBundle(logId, messageType, conversionSource) {
  try {
    const resp = await fetch(API_BASE + `/api/history/log/${logId}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Failed to load conversion');

    document.getElementById('in-tab-text').click();

    const displayBundle = cleanBundleForDisplay(data.bundle);

    handleResult({
      success: true,
      direction: data.conversion_source.toLowerCase().includes('fhir_to_hl7') ? 'fhir_to_hl7' : 
                 (data.conversion_source.toLowerCase().includes('ehr') ? 'ehr_to_fhir' : 'hl7_to_fhir'),
      message_type: data.message_type || 'EHR',
      fhir_json: displayBundle,
      hl7_output: '',
      warnings: data.warnings || [],
      resource_summary: (data.bundle && data.bundle.entry || []).map(e => {
        const r = e.resource || {};
        let desc = r.id || '';
        if (r.resourceType === 'Patient' && r.name && r.name[0]) {
            const n = r.name[0];
            desc = [n.family, ...(n.given || [])].filter(Boolean).join(', ');
        } else if (r.code && r.code.text) {
            desc = r.code.text;
        }
        return {
          resource_type: r.resourceType || 'Unknown',
          resource_id: r.id || '',
          description: desc
        };
      }),
      field_mappings: data.field_mappings || []
    });

    outputPanel.scrollIntoView({ behavior: 'smooth' });
  } catch (err) {
    console.error('Failed to load conversion log:', err);
    alert('Failed to load this conversion record');
  }
}



function copyHistoryOutput(itemId, format) {
  const item = historyItems.find(h => h.id === itemId);
  if (!item) return;

  let text = '';
  if (format === 'json') {
    text = JSON.stringify(item.fhir_json, null, 2);
  } else if (format === 'xml') {
    text = item.fhir_xml || '';
  } else if (format === 'hl7out') {
    text = (item.hl7_output || '').replace(/\r/g, '\n');
  }

  if (text) {
    copyToClipboard(text);
  }
}

function downloadHistoryOutput(itemId, format) {
  const item = historyItems.find(h => h.id === itemId);
  if (!item) return;

  let content = '';
  let filename = '';
  let mimeType = '';

  if (format === 'json') {
    content = JSON.stringify(item.fhir_json, null, 2);
    filename = `fhir_bundle_${item.id}.json`;
    mimeType = 'application/json';
  } else if (format === 'xml') {
    content = item.fhir_xml || '';
    filename = `fhir_bundle_${item.id}.xml`;
    mimeType = 'application/xml';
  } else if (format === 'hl7out') {
    content = (item.hl7_output || '').replace(/\r/g, '\n');
    filename = `hl7_message_${item.id}.hl7`;
    mimeType = 'text/plain';
  }

  if (content) {
    downloadFile(content, filename, mimeType);
  }
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    // Could add a toast notification here
    console.log('Copied to clipboard');
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    document.body.removeChild(ta);
  });
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ===== DARK MODE TOGGLE =====
window.toggleDarkMode = function() {
  document.body.classList.toggle('light-mode');
  const icon = document.getElementById('dark-toggle-icon');
  if (document.body.classList.contains('light-mode')) {
    icon.textContent = '☀️';
    localStorage.setItem('theme', 'light');
  } else {
    icon.textContent = '🌙';
    localStorage.setItem('theme', 'dark');
  }
};

// Restore theme on load
(function() {
  if (localStorage.getItem('theme') === 'light') {
    document.body.classList.add('light-mode');
    const icon = document.getElementById('dark-toggle-icon');
    if (icon) icon.textContent = '☀️';
  }
})();

// ===== GUIDED TOUR =====
const tourSteps = [
  {
    selector: '#direction-toggle',
    title: '1 · Conversion Direction',
    text: 'Choose your conversion mode:<br><b>HL7 → FHIR</b> — convert any HL7 v2.x message (ADT, ORM, ORU, SIU, MDM, DFT, VXU…)<br><b>FHIR → HL7</b> — convert a FHIR R4 Bundle back to HL7<br><b>EHR → FHIR</b> — convert raw pipe-delimited EHR records'
  },
  {
    selector: '#in-tab-text',
    title: '2 · Paste Your Data',
    text: 'Paste HL7 message, FHIR JSON, or raw EHR pipe-delimited data directly into the text area. The tab label changes based on the selected conversion direction.'
  },
  {
    selector: '#in-tab-file',
    title: '3 · Upload File',
    text: 'Upload HL7 (.hl7/.txt), FHIR JSON (.json), CSV, Excel (.xlsx), or DOCX files. For EHR mode, CSV/Excel records are automatically parsed into pipe-delimited format.'
  },
  {
    selector: '.sample-bar',
    title: '4 · Load Sample Data',
    text: 'Load pre-built sample messages — ADT (Epic/Cerner), ORM, ORU, SIU, MDM, VXU, or EHR pipe-delimited. Great for exploring conversion output before using your own data.'
  },
  {
    selector: '#ai-toggle-wrap',
    title: '5 · AI Mode Toggle',
    text: 'Flip this switch to enable AI-powered conversion using a large language model. AI handles complex, non-standard, or unknown HL7 variants that rule-based parsing cannot process.'
  },
  {
    selector: '#ai-provider-group',
    title: '6 · AI Provider Selection',
    text: '<b>⚡ Groq</b> (Llama 3.3 70B) — fast, free tier (100k tokens/day).<br><b>✦ Claude</b> (Sonnet 4.6, Anthropic) — production-grade accuracy. Switch if Groq daily limit is reached.'
  },
  {
    selector: '#mask-phi-label',
    title: '7 · PHI Masking',
    text: 'Check <b>🔒 Mask PHI</b> before converting to replace patient name, MRN, SSN, DOB, address, phone, and next-of-kin data with placeholders before sending to the AI. Use <b>🔓 Unmask</b> in the output to restore original values.'
  },
  {
    selector: '#convert-btn',
    title: '8 · Convert',
    text: 'Click to run the conversion. The button label and icon update based on mode — rule-based (⚡) or AI (✨). Results appear in the Output panel below.'
  },
  {
    selector: '#in-tab-mapping',
    title: '9 · Mapping Rules',
    text: 'View complete field-level mapping documentation for all supported HL7 segments (PID, PV1, ORC, OBR, OBX, NK1, AL1, DG1, IN1, RXA…), EHR record types, AI engine details, PHI masking reference, and download format guide.'
  },
  {
    selector: '#in-tab-history',
    title: '10 · Conversion History',
    text: 'All successful conversions are saved locally. Click any history entry to reload the FHIR output. History persists across page reloads.'
  },
  {
    selector: '.output-panel',
    title: '11 · Output Panel',
    text: 'Conversion results appear here across 5 tabs:<br><b>FHIR JSON</b> · <b>FHIR XML</b> · <b>PDF Report</b> · <b>Summary</b> · <b>Field Mappings</b><br>Use the toolbar to Copy, download JSON, CSV, Excel, or generate a PDF report.'
  },
  {
    selector: '#unmask-btn',
    title: '12 · Unmask PHI',
    text: 'When PHI Masking was used, click <b>🔓 Unmask</b> to restore all original patient data in the output display. Downloads will include the restored data when unmasked.'
  }
];

let tourIndex = 0;
let tourOverlay = null;
let tourTooltip = null;
let tourHighlighted = null;

window.startTour = function startTour() {
  tourIndex = 0;
  if (!tourOverlay) {
    tourOverlay = document.createElement('div');
    tourOverlay.className = 'tour-overlay';
    tourOverlay.onclick = endTour;
    document.body.appendChild(tourOverlay);
  }
  if (!tourTooltip) {
    tourTooltip = document.createElement('div');
    tourTooltip.className = 'tour-tooltip';
    document.body.appendChild(tourTooltip);
  }
  showTourStep(tourIndex);
}

window.showTourStep = function showTourStep(index) {
  if (tourHighlighted) tourHighlighted.classList.remove('tour-highlight');
  if (index >= tourSteps.length) { endTour(); return; }

  const step = tourSteps[index];
  const el = document.querySelector(step.selector);
  if (!el) { showTourStep(index + 1); return; }

  el.classList.add('tour-highlight');
  tourHighlighted = el;

  const rect = el.getBoundingClientRect();
  tourTooltip.innerHTML = `
    <h4>${step.title}</h4>
    <p>${step.text}</p>
    <div class="tour-actions">
      <button class="tour-skip-btn" onclick="endTour()">Skip tour</button>
      <span class="tour-step-label">Step ${index + 1} / ${tourSteps.length}</span>
      <button class="tour-next-btn" onclick="showTourStep(${index + 1})">${index + 1 < tourSteps.length ? 'Next →' : 'Done'}</button>
    </div>
  `;
  tourTooltip.style.display = 'block';
  tourOverlay.style.display = 'block';

  // Smart positioning: show below element, but flip above if too close to bottom
  const tooltipH = tourTooltip.offsetHeight || 160;
  const tooltipW = Math.min(tourTooltip.offsetWidth || 300, 300);
  const margin = 12;
  let top, left;

  if (rect.bottom + tooltipH + margin < window.innerHeight) {
    top = rect.bottom + margin; // below
  } else {
    top = Math.max(margin, rect.top - tooltipH - margin); // above
  }
  left = Math.min(rect.left, window.innerWidth - tooltipW - margin);
  left = Math.max(margin, left);

  tourTooltip.style.top = top + 'px';
  tourTooltip.style.left = left + 'px';
}

window.endTour = function endTour() {
  if (tourHighlighted) { tourHighlighted.classList.remove('tour-highlight'); tourHighlighted = null; }
  if (tourOverlay) { tourOverlay.style.display = 'none'; }
  if (tourTooltip) { tourTooltip.style.display = 'none'; }
}
