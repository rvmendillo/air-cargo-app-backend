from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
from ai.models.request import RequestData
from ai.services.ai_service import run_ai

app = FastAPI(title="Air Cargo Dashboard API")

# Setup CORS for the Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class XMLPayload(BaseModel):
    xml_data: str

class JSONPayload(BaseModel):
    json_data: str

@app.post("/api/convert")
def convert_xml_endpoint(payload: XMLPayload):
    try:
        from converter import convert_xml_to_onerecord_jsonld
        result = convert_xml_to_onerecord_jsonld(payload.xml_data)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["details"])
            
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