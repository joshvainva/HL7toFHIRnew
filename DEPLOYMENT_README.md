# HL7-to-FHIR Converter - Deployment Guide

## 🚀 Quick Start (Docker Hub)
```bash
# Pull and run from Docker Hub
docker run -d \
  --name hl7-fhir-converter \
  -p 8000:8000 \
  joshvainva/hl7-fhir-converter:latest

# Access: http://localhost:8000
```

## 📦 Manual Transfer Method

### On Source Machine:
```bash
# Export the image
docker save hl7-fhir-converter:1.0.0 -o hl7-fhir-converter.tar

# Transfer hl7-fhir-converter.tar to target machine
```

### On Target Machine:
```bash
# Load the image
docker load -i hl7-fhir-converter.tar

# Run the container
docker run -d \
  --name hl7-fhir-converter \
  -p 8000:8000 \
  --restart unless-stopped \
  hl7-fhir-converter:1.0.0
```

## 🐳 Docker Compose Method

### Transfer these files to target machine:
- `docker-compose.yml`
- `.env` (if using environment variables)

```bash
# Run with docker-compose
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs

# Stop
docker compose down
```

## 🔧 Advanced Configuration

### Environment Variables:
```bash
# Create .env file
APP_PORT=8000
ALLOWED_ORIGINS=*
LOG_LEVEL=info
```

### Custom Port:
```bash
docker run -d -p 3000:8000 joshvainva/hl7-fhir-converter:latest
# Access: http://localhost:3000
```

### Volume Mount (for persistent data):
```bash
docker run -d \
  -p 8000:8000 \
  -v /host/path:/app/data \
  joshvainva/hl7-fhir-converter:latest
```

## 🏥 Health Check
```bash
# Check if application is healthy
curl http://localhost:8000/api/health
```

## 🛑 Management Commands
```bash
# Stop container
docker stop hl7-fhir-converter

# Remove container
docker rm hl7-fhir-converter

# Update to latest version
docker pull joshvainva/hl7-fhir-converter:latest
```

## 📋 System Requirements
- Docker Engine 20.10+
- 512MB RAM minimum
- 1GB disk space
- Linux/Windows/macOS with Docker Desktop

## 🎯 Supported Message Types
- ADT (Admit/Discharge/Transfer)
- ORU (Observation Result Unsolicited)
- ORM (Order Message)
- SIU (Scheduling Information Unsolicited)
- MDM (Medical Document Management)
- DFT (Detailed Financial Transaction)
- VXU (Vaccination Update)
- MFN (Master File Notification)
- ACK (Acknowledgment)