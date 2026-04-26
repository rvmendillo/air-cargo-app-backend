# Skyler Backend

A **FastAPI**-powered REST API for air cargo dangerous goods (DG) compliance, shipment management, and AI-assisted regulatory analysis. It integrates with the **IATA ONE Record** standard and **Google Gemini AI** to deliver intelligent DGR (Dangerous Goods Regulations) compliance checks.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [API Reference](#api-reference)
- [Modules](#modules)

---

## Features

- **DGR Compliance Checks** — Validate AWB shipments against IATA Dangerous Goods Regulations.
- **AI-Powered Analysis** — Gemini 2.5 Flash integration for natural-language DGR queries, compliance evaluations, and regulation lookups.
- **ONE Record Integration** — Proxy endpoint that authenticates against a ONE Record server and retrieves/parses AWB data in JSON-LD format.
- **XML ↔ JSON Conversion** — Convert Shipper's Declaration for Dangerous Goods (DGD) XML documents into structured JSON.
- **JSON → JSON-LD** — Transform plain JSON payloads into ONE Record-compliant JSON-LD envelopes.
- **Dashboard Stats** — Mock endpoints for dashboard KPIs (active DG shipments, ULD utilisation, weather, Cargo iQ milestones).
- **Semantic Caching** — Embedding-based cache for AI responses to reduce latency and API costs.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| ASGI Server | [Uvicorn](https://www.uvicorn.org/) |
| AI | [Google Gemini](https://ai.google.dev/) (via `google.generativeai`) |
| HTTP Client | [httpx](https://www.python-httpx.org/) (async, for ONE Record API) |
| XML Parsing | [xmltodict](https://github.com/martinblech/xmltodict) |
| Validation | [Pydantic](https://docs.pydantic.dev/) |
| Config | [python-dotenv](https://github.com/theskumar/python-dotenv) |

---

## Project Structure

```
skyler-backend/
├── main.py                          # FastAPI application & route definitions
├── requirements.txt                 # Python dependencies
├── .env                             # Environment variables (API keys, model config)
│
├── ai/                              # AI / Gemini integration module
│   ├── core/
│   │   └── gemini.py                # Gemini SDK initialisation & API key loading
│   ├── models/
│   │   └── request.py               # Pydantic request model for the /ai endpoint
│   └── services/
│       ├── ai_service.py            # Core AI pipeline (intent → cache → Gemini → cache)
│       ├── cache.py                 # Embedding-based semantic cache
│       ├── embeddings.py            # Text embedding generation
│       ├── intent_normalizer.py     # User-intent normalisation
│       ├── prompt_builder.py        # Dynamic prompt construction
│       └── prompts.py              # System prompt for DGR compliance assistant
│
├── conversion/                      # Data-format conversion module
│   └── services/
│       ├── xml_to_json_service.py   # XML → cleaned JSON conversion (DGD documents)
│       ├── json_to_jsonld_service.py # JSON → JSON-LD (ONE Record envelope)
│       └── xsdg_parser.py          # XSD-aware DG document parser
│
└── onerecord/                       # ONE Record protocol module
    ├── __init__.py
    └── parser.py                    # JSON-LD parser (AWB → dashboard-friendly structure)
```

---

## Prerequisites

- **Python 3.9+**
- **pip** (Python package manager)
- A **Gemini API key** from [Google AI Studio](https://aistudio.google.com/)

---

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd skyler-backend

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root (or edit the existing one):

```env
GEMINI_API_KEY=<your-gemini-api-key>
GEMINI_MODEL_NAME=gemini-2.5-flash
```

| Variable | Description | Required |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API key for AI features | Yes |
| `GEMINI_MODEL_NAME` | Gemini model to use | No (defaults to `gemini-2.5-flash`) |

> **Note:** ONE Record credentials (client ID & secret) are currently configured as constants in `main.py`.

---

## Running the Server

```bash
# Start the development server with hot-reload
uvicorn main:app --reload --port 8000
```

The API will be available at **http://localhost:8000**.

Interactive API docs are auto-generated at:
- **Swagger UI** → http://localhost:8000/docs
- **ReDoc** → http://localhost:8000/redoc

---

## API Reference

### Health Check

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Returns API status message |

### Dashboard

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/dashboard/stats` | Dashboard KPIs (active shipments, ULD status, weather) |
| `GET` | `/api/uld/status` | ULD container status and health data |

### DGR Compliance

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/awb/{awb_number}/compliance` | DGR compliance check for a given AWB number |

### Data Conversion

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/dg/create` | Convert raw XML (DGD document) → JSON. Body: raw XML string. |
| `POST` | `/api/convert-json` | Convert JSON → ONE Record JSON-LD envelope. Body: `{ "json_data": "..." }` |

### AI Assistant

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/ai` | Submit a DGR-related question to the Gemini AI assistant. Body: `{ "text": "..." }` |

### ONE Record

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/onerecord/awb/{awb_id}` | Fetch and parse AWB data from the ONE Record server (server-side auth) |

---

## Modules

### `ai/` — AI & Gemini Integration

The AI pipeline processes user queries through the following steps:

1. **Intent Normalisation** — Classifies and normalises the user's intent.
2. **Embedding Generation** — Creates a text embedding for semantic matching.
3. **Cache Lookup** — Checks the semantic cache for similar previous queries.
4. **Gemini Generation** — If no cache hit, sends the prompt (with DGR system context) to Gemini 2.5 Flash.
5. **Response Caching** — Stores the result embedding for future lookups.

### `conversion/` — Data Format Conversion

- **XML → JSON**: Strips XML namespaces, normalises whitespace, removes boilerplate attributes, and wraps all nodes in arrays for consistent downstream processing.
- **JSON → JSON-LD**: Maps flat JSON keys to `cargo:` namespace URIs and applies XSD data types, producing a ONE Record-compliant JSON-LD document.
- **XSD-aware parsing**: Handles DG-specific XSD schemas for structured document parsing.

### `onerecord/` — ONE Record Protocol

Parses raw ONE Record JSON-LD responses into a structured dashboard format:

- **Master Waybill** — Top-level AWB metadata (number, origin, destination, type).
- **House Waybills** — Child waybills linked to the master.
- **Shipments & Pieces** — Cargo details including dangerous goods information (UN numbers, hazard class, packing instructions).
- **DG Declarations** — Shipper's dangerous goods declarations.
- **Checks & Sub-checks** — Compliance check results with certifier information.