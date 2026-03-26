# HL7 & EHR → FHIR Converter — Deployment Guide

**Innova Solutions | Healthcare Interoperability Platform**

---

## Option A — Docker Compose (Recommended)

The simplest way to deploy from source.

```bash
git clone https://github.com/joshvainva/HL7toFHIRnew.git
cd HL7toFHIRnew

cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and/or GROQ_API_KEY

docker compose up --build -d
```

Open: **http://localhost:8000**

See [DOCKER.md](DOCKER.md) for full Docker instructions including port changes, logging, and troubleshooting.

---

## Option B — Docker Hub (Pull & Run)

```bash
docker run -d \
  --name hl7-fhir-converter \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  joshvainva/hl7-fhir-converter:latest
```

---

## Option C — Manual Image Transfer (Air-Gapped Environments)

### On the source machine:

```bash
docker save hl7-fhir-converter:latest -o hl7-fhir-converter.tar
# Transfer hl7-fhir-converter.tar to the target machine
```

### On the target machine:

```bash
docker load -i hl7-fhir-converter.tar

docker run -d \
  --name hl7-fhir-converter \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  hl7-fhir-converter:latest
```

---

## Option D — Local Python (No Docker)

```bash
# Python 3.11+ required
git clone https://github.com/joshvainva/HL7toFHIRnew.git
cd HL7toFHIRnew

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Health Check

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{"status": "ok"}
```

---

## System Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 1 core | 2+ cores |
| RAM | 512 MB | 1 GB |
| Disk | 1 GB | 2 GB |
| OS | Linux / Windows / macOS with Docker Desktop | — |
| Docker Engine | 20.10+ | 24+ |

---

## Production Configuration

### Restrict CORS origins

Edit `.env`:

```env
ALLOWED_ORIGINS=https://yourdomain.com
```

### Increase worker count for higher load

```env
WORKERS=4
```

### Enable debug logging

```env
LOG_LEVEL=debug
```

### Use a reverse proxy (nginx example)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

---

## Reverting to a Previous Version

Each stable release is tagged in Git. To roll back:

```bash
# List available tags and recent commits
git log --oneline main

# Revert a specific commit safely (creates a new revert commit)
git revert <commit-hash>
git push origin main

# Or check out a specific tag
git checkout tags/stable-v1
docker compose up --build -d
```

The `stable-v1` tag (`49167a0`) marks the last stable release before AI feature additions.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(empty)_ | Claude Sonnet 4.6 API key — for Claude AI mode |
| `GROQ_API_KEY` | _(empty)_ | Groq Llama 3.3 API key — for Groq AI mode |
| `APP_PORT` | `8000` | Host port to expose |
| `WORKERS` | `2` | Uvicorn worker processes |
| `LOG_LEVEL` | `info` | debug / info / warning / error |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins — restrict in production |

---

## Viewing Logs

```bash
# Docker Compose
docker compose logs -f

# Specific container
docker logs -f hl7-fhir-converter

# Local Python
# Logs print to stdout; redirect as needed:
uvicorn app.main:app --port 8000 >> server.log 2>&1
```

---

## Upgrading

```bash
git pull origin main
docker compose up --build -d
```

Always do a hard refresh in the browser after upgrading: **Ctrl+Shift+R**.

---

*Built by Innova Solutions — 2026 AI Hackathon CS06*
