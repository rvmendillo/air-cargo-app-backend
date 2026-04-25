from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import httpx
from conversion.services.xml_to_json_service import convert_xml_string_to_json
from ai.models.request import RequestData
from ai.services.ai_service import run_ai
from onerecord.parser import parse_onerecord_awb

app = FastAPI(title="Air Cargo Dashboard API")

# ── ONE Record configuration ────────────────────────────────────────────────
ONERECORD_AUTH_URL = "https://champ-onerecord.germanywestcentral.cloudapp.azure.com/auth/realms/onerecord/protocol/openid-connect/token"
ONERECORD_API_BASE = "https://champ-onerecord.germanywestcentral.cloudapp.azure.com/api/AIR_CARGO_RANGERS/logistics-objects"
ONERECORD_CLIENT_ID = "onerecord-a1r-cargo-rangers"
ONERECORD_CLIENT_SECRET = "ZuH40SeVGWrt7xgaLbuMILAHKJGSgY69"

# Setup CORS for the Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class JSONPayload(BaseModel):
    json_data: str

@app.post("/api/dg/create")
async def convert_xml_to_json(request: Request):
    """
    Accepts raw XML string directly in the body.
    """
    try:
        raw_body = await request.body()
        
        xml_string = raw_body.decode("utf-8")
        
        if not xml_string:
            raise HTTPException(status_code=400, detail="No XML data provided")

        result = convert_xml_string_to_json(xml_string)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

@app.post("/api/convert-json")
def convert_json_endpoint(payload: JSONPayload):
    try:
        import json
        source = json.loads(payload.json_data)

        # Build a ONE Record JSON-LD envelope from the incoming JSON
        context = {
            "@vocab": "https://onerecord.iata.org/ns/cargo#",
            "cargo": "https://onerecord.iata.org/ns/cargo#",
            "xsd": "http://www.w3.org/2001/XMLSchema#"
        }

        def to_camel(s: str) -> str:
            parts = s.replace("-", "_").split("_")
            return parts[0] + "".join(p.title() for p in parts[1:])

        def map_value(v):
            if isinstance(v, dict):
                return jsonld_map(v)
            if isinstance(v, list):
                return [map_value(i) for i in v]
            if isinstance(v, bool):
                return {"@value": str(v).lower(), "@type": "xsd:boolean"}
            if isinstance(v, (int, float)):
                return {"@value": v, "@type": "xsd:decimal"}
            return {"@value": v}

        def jsonld_map(obj: dict) -> dict:
            result = {}
            for k, v in obj.items():
                key = "cargo:" + to_camel(k)
                result[key] = map_value(v)
            return result

        body = jsonld_map(source)
        body["@context"] = context
        body["@type"] = "cargo:Shipment"
        body["@id"] = "urn:one-record:" + str(source.get("messageId", "unknown"))

        return body
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "Air Cargo API is running"}

@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    return {
        "activeDgrShipments": 42,
        "flaggedDgrShipments": 3,
        "uldUtilization": 91.4,
        "uldActive": 1204,
        "uldInTransit": 82,
        "cargoIqMilestoneCompletion": 98,
        "weather": {
            "hub": "FRA HUB (FRANKFURT)",
            "condition": "Clear Sky",
            "visibility": "10,000+ m",
            "windSpeed": "12 kts NE",
            "activeRunways": "07R, 25C"
        }
    }

@app.get("/api/awb/{awb_number}/compliance")
def get_awb_compliance(awb_number: str):
    return {
        "awb_number": awb_number,
        "consignment": "High-Density Energy Solutions (Lithium-Ion Component)",
        "alerts": [
            {
                "type": "CRITICAL",
                "title": "UN3480 Requirement",
                "message": "Packaging exceeds the 30% State of Charge (SoC) limit for passenger aircraft. Must be re-routed via Cargo-Only flight (CAO)."
            },
            {
                "type": "INFO",
                "title": "Packing Instruction 965",
                "message": "Section IA compliance detected. Overpack markings required in accordance with IATA DGR Figure 7.1.A."
            }
        ],
        "checks": [
            {
                "description": "Lithium ion batteries (UN 3480, PI 965)",
                "classDiv": "Class 9",
                "packaging": "Fibreboard Box",
                "status": "FAIL"
            },
            {
                "description": "Hazard Labeling (Class 9 & CAO)",
                "classDiv": "-",
                "packaging": "Standard",
                "status": "PASS"
            },
            {
                "description": "Shipper's Declaration (Digital DGD Form)",
                "classDiv": "-",
                "packaging": "NOTOC Required",
                "status": "PASS"
            }
        ],
        "ai_analysis": "Hello Loadmaster Thorne. I've analyzed AWB " + awb_number + ". I found a **Critical Conflict** with IATA Section 5, Sub-section 5.0.2.7."
    }

@app.get("/api/uld/status")
def get_uld_status():
    return [
        {
            "id": "AKE 82910 LH",
            "status": "STAGED",
            "gate": "Gate B14",
            "health": 98,
            "temp": "+4.2°C",
            "milestones": ["RCL", "MAN", "DEP"]
        },
        {
            "id": "PMC 44021 AF",
            "status": "LOADED",
            "gate": "Flight AF006",
            "health": 72,
            "warning": "High G-Force Warning",
            "milestones": ["RCL", "MAN", "DEP"]
        }
    ]

@app.post("/ai")
def ai_endpoint(data: RequestData):
    result = run_ai(data.text)
    return {"result": result}

@app.get("/token")
def get_token():
    return {"token": "123"}

@app.get("/api/onerecord/awb/{awb_id}")
async def get_onerecord_awb(awb_id: str):
    """
    Proxy endpoint: acquires an OAuth token from the ONE Record auth server,
    then fetches AWB data from the external ONE Record API.
    Keeps client credentials on the server side.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Get access token
            token_response = await client.post(
                ONERECORD_AUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": ONERECORD_CLIENT_ID,
                    "client_secret": ONERECORD_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to obtain access token: {token_response.text}",
                )
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=502,
                    detail="Access token not found in auth response",
                )

            # Step 2: Fetch AWB data using the token
            awb_response = await client.get(
                f"{ONERECORD_API_BASE}/awb-{awb_id}",
                params={"embedded": "true"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if awb_response.status_code != 200:
                raise HTTPException(
                    status_code=awb_response.status_code,
                    detail=f"ONE Record API error: {awb_response.text}",
                )
            raw_data = awb_response.json()
            # Parse the JSON-LD into structured dashboard data
            return parse_onerecord_awb(raw_data, awb_id=awb_id)

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Error communicating with ONE Record services: {str(e)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
