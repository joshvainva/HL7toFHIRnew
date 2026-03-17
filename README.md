# HL7toFHIR message converter

A production-ready web application that converts **HL7 v2.x** messages into **FHIR R4** resources.

## Features

| Feature | Details |
|---|---|
| **HL7 Detection** | Auto-detects version (2.3–2.8+) and message type (ADT, ORU, ORM, and more) |
| **FHIR Output** | Produces FHIR R4 Bundle with proper references and IDs |
| **Supported Types** | ADT→Patient/Encounter/Practitioner, ORU→Observation/DiagnosticReport, ORM→ServiceRequest |
| **Input Methods** | Paste text · Upload .hl7 · .txt · .csv · .xlsx · .xls · .docx |
| **Output Formats** | FHIR JSON · FHIR XML · Human-readable report |
| **UI** | Dark-mode responsive web UI with copy/download per format |
| **Deployment** | Docker + docker-compose ready |

---

## Quick Start

### Option 1 — Docker Compose (recommended)

```bash
# Clone / enter project directory
cd hl7-fhir-converter

# Build and start
docker compose up --build

# Open browser
open http://localhost:8000
```

### Option 2 — Docker

```bash
docker build -t hl7-fhir-converter .
docker run -p 8000:8000 hl7-fhir-converter
```

### Option 3 — Local Python

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
uvicorn app.main:app --reload --port 8000

# Open browser
open http://localhost:8000
```

---

## Configuration

Copy `.env.example` to `.env` and edit:

```env
APP_PORT=8000
ALLOWED_ORIGINS=*
LOG_LEVEL=info
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | GET | Web UI |
| `POST /api/convert/text` | POST | Convert pasted HL7 text |
| `POST /api/convert/file` | POST | Upload and convert file |
| `GET /api/health` | GET | Health check |
| `GET /api/docs` | GET | Swagger UI |
| `GET /api/redoc` | GET | ReDoc documentation |

### POST /api/convert/text

**Request body (JSON):**
```json
{
  "hl7_message": "MSH|^~\\&|SENDER|FAC|..."
}
```

**Response:**
```json
{
  "success": true,
  "hl7_version": "2.5",
  "message_type": "ADT",
  "message_event": "A01",
  "fhir_json": { "resourceType": "Bundle", ... },
  "fhir_xml": "<?xml version=\"1.0\" ...>",
  "human_readable": "=== HL7 → FHIR CONVERSION REPORT ...",
  "resource_summary": [
    { "resource_type": "Patient", "resource_id": "...", "description": "..." }
  ],
  "warnings": []
}
```

---

## Project Structure

```
hl7-fhir-converter/
├── app/
│   ├── main.py                   # FastAPI application entry point
│   ├── api/
│   │   └── routes.py             # API endpoints
│   ├── core/
│   │   ├── parser.py             # HL7 parsing & version detection
│   │   ├── validator.py          # Input validation
│   │   ├── mapper.py             # Route to correct converter
│   │   └── renderer.py           # JSON / XML / text output
│   ├── converters/
│   │   ├── base.py               # Shared utilities & FHIR helpers
│   │   ├── adt.py                # ADT → Patient, Encounter, Practitioner
│   │   ├── oru.py                # ORU → Observation, DiagnosticReport
│   │   ├── orm.py                # ORM → ServiceRequest
│   │   └── generic.py            # Fallback for unsupported types
│   ├── file_handlers/
│   │   ├── base.py               # Abstract handler interface
│   │   ├── hl7_handler.py        # .hl7 / .txt
│   │   ├── csv_handler.py        # .csv
│   │   ├── excel_handler.py      # .xlsx / .xls
│   │   ├── docx_handler.py       # .docx
│   │   └── registry.py           # Handler registration & lookup
│   ├── models/
│   │   └── schemas.py            # Pydantic request/response models
│   └── templates/
│       └── index.html            # Web UI
├── static/
│   ├── css/style.css
│   └── js/app.js
├── tests/
│   ├── sample_messages/
│   │   ├── adt_a01.hl7
│   │   ├── oru_r01.hl7
│   │   └── orm_o01.hl7
│   └── test_converter.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## Extending the System

### Add a new message type converter

1. Create `app/converters/mytype.py` extending `BaseConverter`
2. Register it in `app/core/mapper.py`:
   ```python
   from app.converters.mytype import MyTypeConverter
   CONVERTER_REGISTRY["MDM"] = MyTypeConverter
   ```

### Add a new file format

1. Create `app/file_handlers/myformat_handler.py` extending `BaseFileHandler`
2. Register it in `app/file_handlers/registry.py`:
   ```python
   from app.file_handlers.myformat_handler import MyFormatHandler
   _HANDLERS.append(MyFormatHandler())
   ```

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Supported HL7 Message Types

| Type | Description | FHIR Resources |
|---|---|---|
| ADT | Admit/Discharge/Transfer | Patient, Encounter, Practitioner, Organization |
| ORU | Observation Result | Patient, DiagnosticReport, Observation |
| ORM | Order Message | Patient, ServiceRequest, Practitioner |
| *Any* | Unsupported types | Patient (if PID present), Parameters (raw data) |
