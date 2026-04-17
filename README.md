# HL7 & EHR → FHIR Converter

**Innova Solutions | Healthcare Interoperability Platform**

A production-ready web application that converts **HL7 v2.x messages**, **raw EHR pipe-delimited data**, and **FHIR R4 bundles** into each other — with rule-based and AI-powered conversion modes, FHIR R4 compliance validation, PHI masking, multi-patient batch support, and rich export options.

---

## Features

### Conversion Directions

| Direction | Description |
|---|---|
| **HL7 → FHIR** | Parses any HL7 v2.x message and maps all standard segments to FHIR R4 resources |
| **EHR → FHIR** | Converts pipe-delimited EHR records or table-format Excel files to FHIR R4 |
| **FHIR → HL7** | Converts FHIR R4 Bundle JSON back to HL7 v2.x message format |

### Supported HL7 Message Types

`ADT` · `ORM` · `ORU` · `SIU` · `MDM` · `DFT` · `VXU` · `MFN` · `BAR` · `ACK`

Auto-detects HL7 version (2.3 – 2.8+) and event type from the MSH segment.

### EHR Record Types (Pipe-Delimited Format)

```
PATIENT|MRN|First|Last|DOB|Gender|Language|Phone|Address|City|State|Zip
ENCOUNTER|VisitID|VisitType|Location|ProviderID|ProviderName|Start|End
ALLERGY|Seq|Substance|Reaction|OnsetDate
DIAGNOSIS|Seq|ICDCode|Description
LAB_ORDER|OrderID|PanelName|OrderedTime
LAB_RESULT|Seq|LOINCCode|TestName|Value|Unit|RefRange|Flag
VITAL|Type|Value|Unit
IMMUNIZATION|VaccineName|Date|Dose|Unit|Route|Site
INSURANCE|ProviderName|Plan|Group|MemberID
NK1|Seq|Name|Relationship|Phone
CHIEF_COMPLAINT|Description
SYMPTOM|Symptom|Severity|Duration
PROCEDURE|Code|Description|Date
MEDICATION|Name|Dose|Route|Frequency|StartDate|EndDate|Status
CLINICAL_NOTE|NoteText
```

### EHR Excel Input (Table Format)

Upload an `.xlsx` file where each sheet is named after an EHR record type (e.g. `Patient`, `Encounter`, `Symptom`). Each sheet has column headers — multiple rows per patient are supported. Rows are matched to their patient using the `Patient Name` and `DOB` columns automatically.

**Supported sheet names:** Patient, Encounter, Chief Complaint, Symptom, Diagnosis, Procedure, Medication Statement, Lab Result, Vital, Clinical Note, Immunization, Insurance, Allergy, NK1, Lab Order

### AI Mode

| Provider | Model | Use |
|---|---|---|
| **Claude** (Anthropic) | Claude Sonnet 4.6 | Structured, reliable — recommended |
| **Groq** | Llama 3.3 70B | Fast, free tier available |

AI mode handles unstructured or non-standard EHR data from any vendor (Epic, Cerner, Meditech, Allscripts, athenahealth, eClinicalWorks, NextGen).

> Multi-patient EHR input always uses the local rule-based converter to prevent data mixing across patients.

### PHI Masking

Before sending data to any AI provider, the application automatically masks:
- Patient name (PID-5)
- Date of birth (PID-7)
- MRN / Patient ID (PID-3)
- SSN (PID-19)
- Address (PID-11)
- Phone (PID-13/14)
- NK1 name and phone fields

An **Unmask** button restores original values in the displayed output after conversion.

### Export Formats

| Format | Description |
|---|---|
| **JSON** | FHIR R4 Bundle — per-patient files for multi-patient input |
| **XML** | FHIR R4 Bundle in XML format |
| **Excel** | Branded styled spreadsheet with one tab per resource type |
| **CSV** | ZIP archive with one CSV per resource type |
| **PDF Report** | Human-readable clinical summary with field mappings |

### Other Features

- **Batch file processing** — upload `.hl7`, `.txt`, `.csv`, `.xlsx`, or `.docx` files containing multiple messages
- **Dark / Light theme** toggle
- **Conversion history** panel (last 10 conversions, in-session)
- **Field Mapping tab** — shows every HL7/EHR field → FHIR resource mapping
- **Guided Tour** — interactive walkthrough of all features
- **Mapping Rules tab** — full EHR field format reference
- **FHIR Validator** — validates output bundle structure
- **Summary tab** — resource count and conversion statistics

---

## Quick Start

### Option A — Docker (Recommended)

Docker is the easiest way to run the entire stack (including the database) on any system.

```bash
# 1. Clone and enter repo
git clone https://github.com/joshvainva/HL7toFHIRnew.git
cd HL7toFHIRnew

# 2. Set up API keys
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY and/or GROQ_API_KEY

# 3. Build and run
docker compose up --build

# Open browser to: http://localhost:8000
```
*Docker handles all dependencies and the PostgreSQL database setup automatically.*

### Option B — Local Python

Use this if you want to run the application directly on your machine. **PostgreSQL 14+** must be installed and running.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize the Database and .env file
# This script will create the database 'innova_fhir' and update your .env
python setup_db.py

# 3. Add AI API Keys (Optional)
# Open .env and add ANTHROPIC_API_KEY for AI-powered conversions.

# 4. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Project Structure

```
HL7toFHIR/
├── app/
│   ├── main.py                        # FastAPI entry point, env loading
│   ├── api/
│   │   └── routes.py                  # API endpoints
│   ├── converters/
│   │   ├── adt.py                     # ADT → FHIR
│   │   ├── orm.py                     # ORM → FHIR (with PV1 Encounter)
│   │   ├── oru.py                     # ORU → FHIR
│   │   ├── siu.py / mdm.py / dft.py   # SIU, MDM, DFT → FHIR
│   │   ├── vxu.py / mfn.py / bar.py   # VXU, MFN, BAR → FHIR
│   │   ├── generic.py                 # Fallback for unknown types
│   │   ├── fhir_to_hl7/               # FHIR → HL7 converters
│   │   └── base.py                    # Shared utilities
│   ├── core/
│   │   ├── ehr_converter.py           # Local EHR pipe-delimited → FHIR
│   │   ├── parser.py                  # HL7 message parser
│   │   ├── mapper.py                  # Field mapping engine
│   │   ├── renderer.py                # FHIR XML renderer
│   │   ├── validator.py               # FHIR bundle validator
│   │   └── history.py                 # Conversion history
│   ├── file_handlers/
│   │   ├── hl7_handler.py             # .hl7 / .txt batch splitter
│   │   ├── excel_handler.py           # .xlsx / .xls — HL7 + EHR table-format
│   │   ├── csv_handler.py             # .csv HL7 extraction
│   │   └── docx_handler.py            # .docx HL7 extraction
│   ├── models/
│   │   └── schemas.py                 # Pydantic request/response models
│   └── templates/
│       └── index.html                 # Main UI (Jinja2)
├── static/
│   ├── css/style.css                  # Dark/Light theme stylesheet
│   ├── js/app.js                      # Frontend logic, exports, PHI masking
│   └── innova_logo_alpha.png          # Branding asset
├── Dockerfile                         # Multi-stage, non-root production build
├── docker-compose.yml                 # Compose with env_file support
├── .env.example                       # Environment variable template
├── requirements.txt                   # Python dependencies
├── DOCKER.md                          # Docker setup guide
└── DEPLOYMENT_README.md               # Production deployment guide
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `POST /api/convert/text` | POST | Convert HL7 text, EHR data, or FHIR JSON |
| `POST /api/convert/file` | POST | Upload and convert a file |
| `POST /api/convert/batch` | POST | Convert multiple HL7 messages at once |
| `GET /api/health` | GET | Health check |
| `GET /docs` | GET | Interactive Swagger UI |

### Request Body — `/api/convert/text`

```json
{
  "input_text": "MSH|^~\\&|...",
  "direction": "hl7_to_fhir",
  "use_ai": false,
  "ai_provider": "claude"
}
```

`direction` values: `hl7_to_fhir` · `ehr_to_fhir` · `fhir_to_hl7`

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(empty)_ | Claude Sonnet 4.6 API key — required for Claude AI mode |
| `GROQ_API_KEY` | _(empty)_ | Groq API key — required for Groq AI mode |
| `APP_PORT` | `8000` | Host port |
| `WORKERS` | `2` | Uvicorn worker count |
| `LOG_LEVEL` | `info` | Logging level |
| `ALLOWED_ORIGINS` | `*` | CORS origins — restrict in production |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ · FastAPI · Uvicorn |
| HL7 Parsing | python-hl7 · Custom per-type converters |
| AI Integration | Anthropic SDK (Claude Sonnet 4.6) · Groq SDK (Llama 3.3 70B) |
| Frontend | Vanilla JS · CSS3 (Dark/Light themes) |
| Excel Export | SheetJS (xlsx-js-style) · JSZip |
| PDF Export | jsPDF |
| Container | Docker multi-stage · non-root user · ~200 MB image |

---

## Reverting Changes

Each release is tagged in Git. To revert `main` to a previous state:

```bash
# View recent commits
git log --oneline main

# Revert a specific commit (safe, creates a new commit)
git revert <commit-hash>
git push origin main
```

The `stable-v1` tag marks the last stable release before AI feature additions (`49167a0`).

---

## Branch Strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready, tested releases |
| `AIchanges` | Active feature development (merged into main after testing) |

---

*Built by Innova Solutions — 2026 AI Hackathon CS06*
