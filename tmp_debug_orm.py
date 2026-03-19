from app.core.parser import HL7Parser
from app.converters.orm import ORMConverter

msg = '''MSH|^~\&|OE_SYSTEM|CITY_HOSPITAL|LAB_SYSTEM|CITY_LAB|20240315151500||ORM^O01|ORM20240315001|P|2.5
PID|1||MRN78965^^^CITYHOSP^MR||JOHNSON^MICHAEL^DAVID||19750820|M
PV1|1|O|CLINIC^101^A
ORC|NW|ORD002||GRP20240315001|||||20240315151500|||NPI9876543^SMITH^RACHEL^M
OBR|1|ORD002||80053^COMPREHENSIVE METABOLIC PANEL^LN|||20240315151500|||||||||NPI9876543^SMITH^RACHEL|||R'''

parser = HL7Parser()
converter = ORMConverter()
parsed = parser.parse(msg)
resources, warnings, field_mappings = converter.convert(parsed)

print('resources:', [r['resourceType'] for r in resources])
print('warnings:', warnings)
print('field_mappings count:', len(field_mappings))
for fm in field_mappings:
    print('---', fm.resource_type, fm.resource_id, 'mappings:', len(fm.field_mappings))
    for m in fm.field_mappings[:5]:
        print('   ', m.fhir_field, m.hl7_segment, m.hl7_field, m.hl7_value)
