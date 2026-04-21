# AI-Driven Secure IoMT Monitoring Anomaly Detection Platform

This repository hosts the foundation for a secure Internet of Medical Things (IoMT) monitoring platform designed to collect telemetry from connected medical devices, analyze behavior in near real time, and surface anomalies that may indicate operational faults, cyber threats, or patient-safety risks.

## Project Description

Modern IoMT environments include infusion pumps, patient monitors, imaging systems, wearable sensors, and other connected assets that continuously generate data. These systems improve care delivery, but they also expand the attack surface and increase the difficulty of maintaining visibility across devices, users, and networks.

This project aims to provide a unified platform that helps security and operations teams:

- monitor device health and activity across distributed IoMT environments
- collect and normalize telemetry from heterogeneous sources
- detect abnormal device, network, or user behavior using AI and statistical methods
- correlate anomalies with security-relevant context
- support investigation, alerting, and operational response workflows

The long-term goal is to create an end-to-end system that combines observability, analytics, and security controls in a way that is practical for healthcare environments where reliability, privacy, and safety are critical.

## Core Objectives

- Build a secure ingestion pipeline for IoMT telemetry and device events
- Normalize incoming data into a consistent schema for analytics
- Detect anomalies using rule-based, statistical, and machine learning approaches
- Provide dashboards and alerts for rapid triage
- Preserve auditability, privacy, and access control across the platform

## Architecture Overview

The platform is planned as a layered system where each layer has a focused responsibility.

```text
IoMT Devices / Sensors / Gateways
                |
                v
     Data Ingestion and Collection Layer
                |
                v
      Data Processing and Normalization
                |
                v
   Feature Extraction and Anomaly Detection
                |
                v
      Alerting, Visualization, and Response
                |
                v
   Security, Audit, and Administrative Controls
```

## Planned Architecture Components

### 1. Device and Data Source Layer

This layer represents the origin of system data, including:

- connected medical devices
- hospital gateways and edge collectors
- network telemetry sources
- system and application logs
- user and administrative activity records

### 2. Ingestion Layer

The ingestion layer is responsible for securely receiving raw telemetry from devices and upstream systems. It may include APIs, message brokers, streaming connectors, or edge forwarding agents. This layer should support authentication, rate limiting, schema validation, and reliable transport.

### 3. Processing and Normalization Layer

Incoming data is cleaned, validated, enriched, and transformed into a standardized structure. This enables downstream analytics to work consistently across device types and protocols. Metadata such as device identity, timestamps, location, and risk tags can be attached here.

### 4. Analytics and Detection Layer

This layer applies anomaly detection logic to processed telemetry. Detection strategies may include:

- threshold and rule-based checks
- time-series drift analysis
- behavioral profiling
- unsupervised anomaly detection
- supervised classification where labeled data exists

### 5. Alerting and Response Layer

When suspicious or abnormal events are detected, the platform should generate alerts, risk scores, and investigation artifacts. This layer can feed dashboards, notification systems, case management workflows, and response automation.

### 6. Security and Governance Layer

Because the platform operates in a sensitive healthcare context, security controls cut across every layer. Key concerns include:

- strong authentication and authorization
- encryption in transit and at rest
- tenant and role isolation where needed
- audit logging
- compliance-aware data handling
- secure configuration and secrets management

## High-Level Data Flow

1. IoMT devices and supporting infrastructure produce telemetry and event data.
2. The ingestion layer securely receives and routes that data.
3. Processing services normalize, enrich, and store the incoming information.
4. Detection services analyze current and historical behavior for anomalies.
5. Alerts and insights are exposed to dashboards, analysts, and response workflows.

## Current Status

The repository has moved beyond initialization and now includes a working backend and AI foundation:

- a FastAPI backend with health, device registration, device-authenticated telemetry ingestion, and alert retrieval endpoints
- SQLAlchemy models and Alembic migrations for devices, telemetry, alerts, and anomaly-related fields
- an AI pipeline covering preprocessing, feature extraction, model training, persisted artifacts, live inference, model version tracking, prediction logging, and runtime performance monitoring

The platform is still an early-stage implementation rather than a finished product, but it is no longer documentation-only. The current codebase provides an executable base for iterating on detection quality, operational workflows, and frontend/dashboard capabilities.

## Testing

Run the backend API unit tests:

```bash
pytest tests/backend/test_api_unit.py
```

Run AI training and inference integration tests:

```bash
pytest tests/ai/test_ai_pipeline_integration.py
```

Run the complete test suite:

```bash
pytest
```

## Load Testing

The repository includes two options for ingestion load testing.

1. Multi-device simulation with anomaly injection:

```bash
python backend/scripts/iomt_device_simulator.py \
  --base-url http://127.0.0.1:8000 \
  --auth-email admin@example.com \
  --auth-password StrongPass123! \
  --device-count 25 \
  --duration-seconds 120 \
  --ingest-mode batch
```

2. Focused API stress testing for a single authenticated device:

```bash
python backend/scripts/load_test.py \
  --base-url http://127.0.0.1:8000 \
  --mode batch \
  --batch-size 100 \
  --concurrency 20 \
  --duration-seconds 90 \
  --api-key <device-api-key>
```

## Demo Setup

For a full-stack local demo:

1. Prepare environment:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

2. Start the backend API:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

3. Start the frontend app (separate terminal):

```bash
cd frontend
npm install
npm run dev
```

4. Optional full infrastructure demo with containers:

```bash
cp .env.production.example .env.production
docker compose up --build
```

This boots PostgreSQL, backend, frontend, Nginx, Prometheus, and Grafana.

## Recent Stability and Performance Enhancements

- Improved SQLite compatibility for local testing by adding safe engine settings.
- Reduced telemetry batch ingestion overhead by flushing telemetry rows in grouped batches.
- Applied the same batch-flush strategy to streaming ingestion worker processing.
- Reduced Prometheus route-label cardinality by preferring route templates over raw paths.
- Hardened model prediction/performance file logging with thread-safe writes.
