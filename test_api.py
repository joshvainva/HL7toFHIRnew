import urllib.request
import json

# Simple ADT message
oru_message = """MSH|^~\\&|SND|FAC|RCV|DEST|20240101120000||ADT^A01|MSG001|P|2.5
EVN|A01|20240101120000
PID|1||MRN001^^^HOSP^MR||DOE^JOHN^A||19800315|M
PV1|1|I|ICU^101^A|E|||NPI123^SMITH^JANE|||SUR"""

data = {
    "message_type": "ADT",
    "hl7_message": oru_message
}

try:
    json_data = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(
        "http://localhost:8000/api/convert/text",
        data=json_data,
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        print("Success! Response received.")
    with urllib.request.urlopen(req) as response:
        response_data = response.read().decode('utf-8')
        print(f"Raw response length: {len(response_data)}")
        print(f"Beginning of response: {response_data[:500]}...")
        print(f"End of response: ...{response_data[-500:]}")
        
        result = json.loads(response_data)
        print("Success! Response received.")
        print(f"Success: {result.get('success')}")
        print(f"Message type: {result.get('message_type')}")
        print(f"Errors: {result.get('errors', [])}")
        print(f"Warnings: {result.get('warnings', [])}")

        # Check field mappings
        field_mappings = result.get('field_mappings', [])
        print(f"Field mappings: {len(field_mappings)} resource mappings")
        if field_mappings:
            for mapping in field_mappings[:2]:  # Show first 2
                print(f"  {mapping['resource_type']} ({mapping['resource_id']}): {len(mapping['field_mappings'])} field mappings")
                for fm in mapping['field_mappings'][:3]:  # Show first 3 field mappings
                    print(f"    {fm['fhir_field']} <- {fm['hl7_segment']}-{fm['hl7_field']}: {fm['hl7_value']}")

        if 'fhir_json' in result and result['fhir_json']:
            bundle = result['fhir_json']
            print(f"Bundle type: {bundle.get('resourceType')}")
            entries = bundle.get('entry', [])
            print(f"Bundle contains {len(entries)} resources")
            if entries:
                types = [e["resource"]["resourceType"] for e in entries]
                print(f"Resource types: {types}")
            else:
                print("No entries in bundle")
        else:
            print("No FHIR JSON in response")
except Exception as e:
    print(f"Request failed: {e}")