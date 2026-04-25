JOKE_KEYWORDS = ["joke", "funny", "humor", "laugh"]
DGR_KEYWORDS = ["dangerous goods", "iata", "lithium", "UN", "battery"]
SHIPMENT_KEYWORDS = ["shipment", "consignment", "air waybill", "cargo"]


def normalize_intent(text: str) -> str:
    text = text.lower().strip()

    if any(k in text for k in JOKE_KEYWORDS):
        return "intent:joke"

    if any(k in text for k in DGR_KEYWORDS):
        return "intent:dgr"

    if any(k in text for k in SHIPMENT_KEYWORDS):
        return "intent:shipment_analysis"

    return "intent:general"