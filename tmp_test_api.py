import json
import urllib.request

url = 'http://127.0.0.1:8000/api/convert/text'

msg = '''MSH|^~\&|OE_SYSTEM|CITY_HOSPITAL|LAB_SYSTEM|CITY_LAB|20240315151500||ORM^O01|ORM20240315001|P|2.5
PID|1||MRN78965^^^CITYHOSP^MR||JOHNSON^MICHAEL^DAVID||19750820|M
PV1|1|O|CLINIC^101^A
ORC|NW|ORD20240315002||GRP20240315001|||||20240315151500|||NPI9876543^SMITH^RACHEL^M
OBR|1|ORD20240315002||80053^COMPREHENSIVE METABOLIC PANEL^LN|||20240315151500|||||||||NPI9876543^SMITH^RACHEL|||R'''

req = urllib.request.Request(
    url,
    data=json.dumps({'hl7_message': msg}).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
)

resp = urllib.request.urlopen(req, timeout=10)
data = json.load(resp)
print('HTTP', resp.getcode())
print('success', data.get('success'))
print('field_mappings count', len(data.get('field_mappings') or []))
if data.get('field_mappings'):
    first = data['field_mappings'][0]
    print('first resource mapping:', first.get('resource_type'), 'fields', len(first.get('field_mappings') or []))
    print('sample mapping:', first.get('field_mappings')[0] if first.get('field_mappings') else None)
