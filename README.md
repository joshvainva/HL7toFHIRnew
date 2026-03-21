# HL7 & EHR → FHIR Converter

A premium, production-ready healthcare interoperability platform that converts **HL7 v2.x** and **Raw EHR Data** into **FHIR R4** resources. Designed for high-end presentation and automated clinical data mapping.

## ✨ Premium Features

| Category | Capability |
|---|---|
| **EHR Logic** | **AI-Powered Conversion** for raw unstructured clinical data (Epic, Cerner, Meditech, etc.) |
| **HL7 Engine** | Auto-detects version (2.3–2.8+) and message types (ADT, ORU, ORM, SIU, MDM, etc.) |
| **Premium UI** | **Dark Glassmorphism** design with animated backgrounds and branded Innova watermarks |
| **Styled Exports**| **Excel (Styled)** with brand-consistent headers, **CSV**, and human-readable **PDF Reports** |
| **Batch Support**| **Multi-Patient Processing** with automatic ZIP packaging and context partitioning |
| **Audit Ready** | **Sequential Timestamping** on all export filenames for easy tracking and versioning |

## 🚀 Quick Start (Docker)

```bash
# Build and start the platform
docker compose up --build

# Open browser
open http://localhost:8000
```

## 🏥 Supported Data Types

### Standard HL7 v2
- **ADT**: Patient, Encounter, Practitioner, Organization
- **ORU**: Patient, DiagnosticReport, Observation
- **ORM**: Patient, ServiceRequest, Practitioner
- **SIU/MDM/DFT/VXU/MFN**: Full mapping support for all major segments.

### EHR Raw Data (AI-Driven)
- Supports structured and unstructured text from major vendors:
  - **Epic** / **Cerner** / **Meditech** / **Allscripts** / **Athena**
- Converts clinical notes, patient summaries, and demographics directly to FHIR R4.

---

## 🎨 UI & Branding
The application features a **Premium Dark UI Overhaul**:
- **Branded Innova Logo**: Integrated into the header and browser tab (favicon).
- **Background Watermarks**: 20% opacity logo branding behind all input and output fields.
- **Glassmorphism Panels**: Semi-transparent containers with backdrop-blur for a modernized clinical feel.
- **Electric Accents**: Vibrant neon color-coding for different clinical resource types.

## 📁 Project Structure

```
hl7-fhir-converter/
├── app/
│   ├── main.py                   # FastAPI application entry point
│   ├── converters/               # HL7 & EHR specialized mapping logic
│   ├── file_handlers/            # Support for .hl7, .csv, .xlsx, .docx
│   └── templates/                # Branded Jinja2 UI templates
├── static/
│   ├── css/style.css             # Premium Dark Theme stylesheet
│   ├── js/app.js                 # Frontend logic, export partitioning, and ZIP handling
│   └── innova_logo_alpha.png     # Transparent branding asset
├── Dockerfile                    # Multi-stage production build
└── requirements.txt              # Backend dependencies
```

## 📊 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `POST /api/convert/text` | POST | Convert HL7 text or EHR Raw Data |
| `POST /api/convert/file` | POST | Upload and process files (.hl7, .txt, .csv, .xlsx) |
| `GET /api/docs` | GET | Interactive Swagger UI |

---

## 🛠️ Technology Stack
- **Backend**: FastAPI (Python), hl7apy, fhir.resources
- **Frontend**: Vanilla JS, Glassmorphism CSS, Jinja2
- **Libraries**: `xlsx-js-style` (Styled Excel), `JSZip` (Batch Export), `jspdf` (Reports)

## 🐳 Deployment
For advanced production deployment details, cluster configuration, and volume mounting, see [DEPLOYMENT_README.md](DEPLOYMENT_README.md).
