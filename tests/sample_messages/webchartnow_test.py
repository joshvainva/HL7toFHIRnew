import requests
import re

API_URL = "http://localhost:8000/api/convert"
SAMPLES_FILE = "../tests/sample_messages/webchartnow_samples.hl7"
RESULTS_FILE = "../tests/sample_messages/webchartnow_results.csv"

# Delimiter for each message
DELIMITER = re.compile(r"^---(.+?)---$", re.MULTILINE)

# Read HL7 samples
with open(SAMPLES_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# Split into messages
splits = DELIMITER.split(content)
# splits[0] is header, then alternating: [type, message, type, message, ...]
messages = []
for i in range(1, len(splits), 2):
    msg_type = splits[i].strip()
    msg = splits[i+1].strip()
    messages.append((msg_type, msg))

results = []

for idx, (msg_type, msg) in enumerate(messages):
    payload = {"hl7_message": msg}
    try:
        resp = requests.post(API_URL, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            status = "success" if data.get("success", True) else "fail"
            fhir = data.get("fhir_resource", "")
            error = data.get("error", "")
        else:
            status = "http_error"
            fhir = ""
            error = f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:
        status = "exception"
        fhir = ""
        error = str(e)
    results.append([idx+1, msg_type, status, error])
    print(f"[{idx+1}] {msg_type}: {status} - {error}")

# Write CSV
with open(RESULTS_FILE, "w", encoding="utf-8") as f:
    f.write("Index,Type,Status,Error\n")
    for row in results:
        f.write(",".join(str(x).replace("\n", " ") for x in row) + "\n")

print(f"\nResults written to {RESULTS_FILE}")
