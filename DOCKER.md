# HL7 & EHR → FHIR Converter — Docker Setup Guide

**Innova Solutions | Healthcare Interoperability Tool**

Convert HL7 v2.x messages and raw EHR records to FHIR R4 — rule-based and AI-powered (Claude Sonnet 4.6 / Groq Llama 3.3).

---

## Prerequisites

| Tool | Minimum Version | Download |
|------|----------------|---------|
| Docker Desktop | 24+ | https://www.docker.com/products/docker-desktop |
| Docker Compose | v2 (bundled with Docker Desktop) | — |

> **No Python, no pip, no virtual environment needed.** Everything runs inside the container.

---

## Quick Start (3 steps)

### Step 1 — Get the project files

Either clone the repo or unzip the shared folder, then open a terminal in that folder.

```bash
cd hl7-fhir-converter
```

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
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx          # from console.groq.com  (free)
```

> **AI keys are optional.** The app works without them in rule-based mode.
> AI Mode (Claude / Groq) requires at least one key.

### Step 3 — Build and run

```bash
docker compose up --build
```

First build takes ~2–3 minutes (downloads Python + installs packages).
Subsequent starts take ~5 seconds.

Open your browser: **http://localhost:8000**

---

## Stopping the app

```bash
# Stop (keeps data)
docker compose down

# Stop and remove all data
docker compose down -v
```

---

## Running in the background

```bash
docker compose up --build -d        # detached mode
docker compose logs -f              # view live logs
docker compose down                 # stop
```

---

## Changing the port

Edit `.env`:
```env
APP_PORT=9000
```
Then restart: `docker compose up -d`
Open: **http://localhost:9000**

---

## What's included

| Feature | Description |
|---------|-------------|
| HL7 → FHIR | Converts ADT, ORM, ORU, SIU, MDM, DFT, VXU, MFN, BAR, ACK |
| FHIR → HL7 | Converts FHIR R4 Bundle back to HL7 v2.x |
| EHR → FHIR | Converts raw pipe-delimited EHR records |
| AI Mode | Claude Sonnet 4.6 (Anthropic) or Groq Llama 3.3 70B |
| PHI Masking | Masks patient name, MRN, SSN, DOB, NK1 before AI send |
| Downloads | FHIR JSON, XML, PDF Report, CSV, Excel |
| Dark / Light Theme | Toggle in header |
| Guided Tour | Click the Tour button for a feature walkthrough |

---

## Supported HL7 message types

`ADT` · `ORM` · `ORU` · `SIU` · `MDM` · `DFT` · `VXU` · `MFN` · `BAR` · `ACK`
All major EHR vendors: **Epic · Cerner · Meditech · Allscripts · athenahealth · eClinicalWorks · NextGen**

---

## Troubleshooting

### Port already in use
```bash
# Change the port in .env
APP_PORT=8080
docker compose up -d
```

### Container won't start — check logs
```bash
docker compose logs hl7-fhir-converter
```

### AI conversion fails — "API key not set"
Make sure `.env` has your key and you ran `docker compose up` **after** editing `.env`.
Rule-based conversion always works without keys.

### Groq "daily token limit reached"
Switch to **✦ Claude** in the AI provider selector in the app convert bar.
Groq free tier: 100,000 tokens/day. Resets at midnight UTC.

### Rebuild after code changes
```bash
docker compose up --build
```

---

## Environment variables reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | _(empty)_ | Claude Sonnet 4.6 API key |
| `GROQ_API_KEY` | _(empty)_ | Groq Llama 3.3 API key |
| `APP_PORT` | `8000` | Host port to expose |
| `WORKERS` | `2` | Uvicorn worker processes |
| `LOG_LEVEL` | `info` | debug / info / warning / error |
| `ALLOWED_ORIGINS` | `*` | CORS origins (set your domain in production) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 · FastAPI · Uvicorn |
| AI | Anthropic SDK (Claude) · Groq SDK · json-repair |
| Frontend | Vanilla JS · CSS3 · jsPDF · SheetJS |
| HL7 Parsing | python-hl7 · Custom converters per message type |
| Container | Docker (multi-stage, non-root, ~200 MB) |

---

*Built by Innova Solutions — 2026 AI Hackathon CS06*
