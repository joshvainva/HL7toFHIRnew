# HL7 & EHR → FHIR Converter — Docker Setup Guide

**Innova Solutions | Healthcare Interoperability Platform**

Convert HL7 v2.x messages, raw EHR records, and FHIR R4 bundles — rule-based and AI-powered (Claude Sonnet 4.6 / Groq Llama 3.3 70B).

---

## Prerequisites

| Tool | Minimum Version | Download |
|---|---|---|
| Docker Desktop | 24+ | https://www.docker.com/products/docker-desktop |
| Docker Compose | v2 (bundled with Docker Desktop) | — |

> **No Python, no pip, no virtual environment needed.** Everything runs inside the container.

---

## Quick Start (3 Steps)

### Step 1 — Get the project files

```bash
git clone https://github.com/joshvainva/HL7toFHIRnew.git
cd HL7toFHIRnew
```

Or unzip the shared folder, then open a terminal inside it.

### Step 2 — Set up your API keys

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Open `.env` in any text editor and fill in your keys:

```env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx   # from console.anthropic.com
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx          # from console.groq.com (free tier available)
```

> **AI keys are optional.** The app works in full rule-based mode without any API keys.
> AI Mode (Claude or Groq) requires at least one key.

### Step 3 — Build and run

```bash
docker compose up --build
```

First build: ~2–3 minutes (downloads Python image + installs packages).
Subsequent starts: ~5 seconds.

Open your browser: **http://localhost:8000**

#### Run the Docker image directly

If you want to run the application from the built image without Compose:

```bash
docker build -t hl7-fhir-converter:2.0.0 .
docker run -p 8000:8000 --env-file .env hl7-fhir-converter:2.0.0
```

This starts the same production image inside a single container.

---

## Stopping the App

```bash
# Stop and keep data
docker compose down

# Stop and remove all volumes
docker compose down -v
```

---

## Running in the Background

```bash
# Start in detached mode
docker compose up --build -d

# View live logs
docker compose logs -f

# Stop
docker compose down
```

---

## Changing the Port

Edit `.env`:

```env
APP_PORT=9000
```

Restart: `docker compose up -d`
Open: **http://localhost:9000**

---

## Rebuilding After Code Changes

```bash
docker compose up --build
```

Always use `--build` after pulling new code or editing source files.

---

## What's Included

| Feature | Description |
|---|---|
| **HL7 → FHIR** | Converts ADT, ORM, ORU, SIU, MDM, DFT, VXU, MFN, BAR, ACK |
| **FHIR → HL7** | Converts FHIR R4 Bundle back to HL7 v2.x |
| **EHR → FHIR** | Converts pipe-delimited EHR records (text or Excel table-format) |
| **Multi-Patient Excel** | Table-format .xlsx with one sheet per record type, multiple rows per patient |
| **AI Mode** | Claude Sonnet 4.6 (Anthropic) or Groq Llama 3.3 70B |
| **PHI Masking** | Masks name, MRN, SSN, DOB, NK1 fields before sending to AI |
| **Unmask Button** | Restores original PHI values in displayed output after conversion |
| **Downloads** | FHIR JSON (per-patient), XML, PDF Report, CSV (ZIP), Excel |
| **Batch Files** | Upload .hl7, .txt, .csv, .xlsx, .docx with multiple messages |
| **Dark / Light Theme** | Toggle in the header |
| **Guided Tour** | Interactive walkthrough of all features |
| **Conversion History** | Last 10 conversions stored in-session |
| **Field Mapping Tab** | Every source field → FHIR resource mapping shown |
| **FHIR Validator** | Validates output bundle structure |

---

## Supported HL7 Message Types

`ADT` · `ORM` · `ORU` · `SIU` · `MDM` · `DFT` · `VXU` · `MFN` · `BAR` · `ACK`

All major EHR vendors: **Epic · Cerner · Meditech · Allscripts · athenahealth · eClinicalWorks · NextGen**

---

## Troubleshooting

### Port already in use

```bash
# Change port in .env
APP_PORT=8080
docker compose up -d
```

### Container won't start

```bash
docker compose logs hl7-fhir-converter
```

### AI conversion fails — "API key not set"

- Ensure your `.env` file has the correct key
- Restart after editing `.env`: `docker compose up -d`
- Rule-based conversion always works without API keys

### Groq "daily token limit reached"

Switch to **Claude** using the AI provider selector in the convert bar.
Groq free tier: 100,000 tokens/day, resets at midnight UTC.

### Changes not showing in browser

Do a hard refresh: **Ctrl+Shift+R** (Windows/Linux) or **Cmd+Shift+R** (Mac).

### Rebuild not picking up changes

```bash
docker compose down
docker compose up --build
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(empty)_ | Claude Sonnet 4.6 API key |
| `GROQ_API_KEY` | _(empty)_ | Groq Llama 3.3 API key |
| `APP_PORT` | `8000` | Host port to expose |
| `WORKERS` | `2` | Uvicorn worker processes |
| `LOG_LEVEL` | `info` | debug / info / warning / error |
| `ALLOWED_ORIGINS` | `*` | CORS origins — set your domain in production |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · FastAPI · Uvicorn |
| AI | Anthropic SDK (Claude Sonnet 4.6) · Groq SDK (Llama 3.3 70B) · json-repair |
| Frontend | Vanilla JS · CSS3 · jsPDF · SheetJS (xlsx-js-style) · JSZip |
| HL7 Parsing | python-hl7 · Custom per-type converters |
| Container | Docker multi-stage · non-root user · ~200 MB image |

---

*Built by Innova Solutions — 2026 AI Hackathon CS06*
