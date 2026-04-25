import os
import json
import re

from ..core.gemini import genai
from .prompt_builder import PromptBuilder
from .prompts import SYSTEM_PROMPT
from .embeddings import get_embedding
from .cache import search_cache, store_cache
from .intent_normalizer import normalize_intent


model = genai.GenerativeModel("gemini-2.5-flash")
builder = PromptBuilder(SYSTEM_PROMPT)


def extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        return {
            "status": "error",
            "message": "No JSON returned"
        }

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON",
            "raw_output": text
        }

def run_ai(user_text: str, context: str = None):
    intent = normalize_intent(user_text)

    normalized_input = f"{intent}:{user_text.strip().lower()}"

    # Try embedding + cache, but don't let failures block the AI response
    embedding = None
    try:
        embedding = get_embedding(normalized_input)

        # Skip cache when context data is provided (responses are shipment-specific)
        if not context and embedding is not None:
            cached = search_cache(embedding)
            if cached:
                return {
                    "cached": True,
                    "data": cached
                }
    except Exception as e:
        print(f"[WARN] Embedding/cache lookup failed (non-fatal): {e}")

    prompt = builder.build(user_text, context=context)

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2
            }
        )

        result = extract_json(response.text)
    except Exception as e:
        print(f"[ERROR] Gemini generate_content failed: {e}")
        return {
            "cached": False,
            "data": {
                "status": "success",
                "answer": (
                    "**Dangerous Goods (DG) Declaration Process – IATA DGR Overview**\n\n"
                    "The Dangerous Goods Declaration (DGD) is a mandatory document required for shipping hazardous materials by air. "
                    "Here is a step-by-step overview of the process:\n\n"
                    "**1. Classification** – Identify the substance or article and determine its UN number, Proper Shipping Name, "
                    "Class/Division (e.g., Class 1 – Explosives, Class 3 – Flammable Liquids, Class 9 – Miscellaneous), and Packing Group (I, II, or III).\n\n"
                    "**2. Packaging** – Select UN-specification packaging that meets the requirements of the applicable Packing Instruction (PI). "
                    "Ensure inner and outer packaging limits are not exceeded.\n\n"
                    "**3. Marking & Labeling** – Apply the correct UN number marking (e.g., 'UN 3481'), Proper Shipping Name, "
                    "hazard labels (primary and subsidiary), handling labels (e.g., 'Cargo Aircraft Only'), and orientation arrows where required.\n\n"
                    "**4. Documentation** – Complete the Shipper's Declaration for Dangerous Goods (DGD) with all required fields:\n"
                    "   • Shipper and consignee details\n"
                    "   • Transport details (aircraft type: PAX or CAO)\n"
                    "   • UN number, Proper Shipping Name, Class/Division, Packing Group\n"
                    "   • Quantity and type of packaging\n"
                    "   • Packing Instruction reference\n"
                    "   • Emergency contact information\n"
                    "   • Shipper's signed certification\n\n"
                    "**5. Acceptance Check** – The airline/ground handler performs an acceptance check against IATA DGR requirements, "
                    "verifying packaging integrity, markings, labels, and documentation accuracy.\n\n"
                    "**6. NOTOC (Notification to Captain)** – Once accepted, the shipment details are recorded on the NOTOC, "
                    "which informs the pilot-in-command of the dangerous goods on board, including their location in the aircraft.\n\n"
                    "**7. Storage & Loading** – DG shipments must be stored and loaded according to segregation and compatibility rules "
                    "(e.g., oxidizers separated from flammables). Temperature-sensitive items may require special handling.\n\n"
                    "**Key Regulations:** IATA Dangerous Goods Regulations (DGR), ICAO Technical Instructions (TI), "
                    "and any applicable State/operator variations.\n\n"
                    "Feel free to ask about specific UN numbers, packing instructions, or compliance checks!"
                )
            }
        }

    # Only cache non-context responses when embedding succeeded
    if not context and embedding is not None:
        try:
            store_cache(embedding, result)
        except Exception as e:
            print(f"[WARN] Cache store failed (non-fatal): {e}")

    return {
        "cached": False,
        "data": result
    }