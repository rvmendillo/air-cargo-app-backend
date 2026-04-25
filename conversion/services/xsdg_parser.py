import xmltodict
import re
from typing import Optional


def _strip_ns(key: str) -> str:
    """Remove XML namespace prefix from a key."""
    return key.split(":")[-1].lstrip("@")


def _clean(d):
    """Recursively strip namespaces and @ prefixes from dict keys."""
    if isinstance(d, dict):
        return {_strip_ns(k): _clean(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_clean(i) for i in d]
    return d


def _get(d: dict, *keys, default=None):
    """Safely navigate nested dicts."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    return d if d != {} else default


def parse_xsdg(xml_string: str) -> dict:
    """
    Parse an XSDG (XML Shipper's Declaration for Dangerous Goods) and return
    a structured dict with all DGD fields for display and ONE Record mapping.
    """
    try:
        raw = xmltodict.parse(xml_string, process_namespaces=False)
    except Exception as e:
        return {"error": f"XML parse error: {e}"}

    raw = _clean(raw)

    # Find the root — could be ShippersDeclarationForDangerousGoods, or any root
    root_key = list(raw.keys())[0]
    doc = raw[root_key]

    # ── Header / AWB ──────────────────────────────────────────────────────────
    header = doc.get("HeaderExchangedDocument", {}) or doc.get("ExchangedDocument", {})
    message_id = _get(header, "ID") or _get(header, "MessageID") or "UNKNOWN"

    consignment = (
        doc.get("SpecifiedSupplyChainConsignment")
        or doc.get("Consignment")
        or doc.get("SupplyChainConsignment")
        or {}
    )

    # AWB number
    awb_id_node = (
        _get(consignment, "AssociatedTransportDocument")
        or _get(consignment, "MasterAirWaybill")
        or {}
    )
    if isinstance(awb_id_node, list):
        awb_id_node = awb_id_node[0]
    awb_raw = _get(awb_id_node, "ID") or _get(awb_id_node, "AWBNumber") or message_id
    awb_number = _format_awb(str(awb_raw))

    # Shipper
    shipper_node = (
        _get(consignment, "ConsignorTradeParty")
        or _get(consignment, "Shipper")
        or {}
    )
    if isinstance(shipper_node, list):
        shipper_node = shipper_node[0]
    shipper_name = _get(shipper_node, "Name") or "N/A"
    shipper_addr = _build_address(shipper_node)

    # Consignee
    consignee_node = (
        _get(consignment, "ConsigneeTradeParty")
        or _get(consignment, "Consignee")
        or {}
    )
    if isinstance(consignee_node, list):
        consignee_node = consignee_node[0]
    consignee_name = _get(consignee_node, "Name") or "N/A"
    consignee_addr = _build_address(consignee_node)

    # Route
    origin = _extract_location(consignment, "DepartureTransportEvent", "LoadingBaseportLocation") or "N/A"
    destination = _extract_location(consignment, "ArrivalTransportEvent", "UnloadingBaseportLocation") or "N/A"

    # Pieces / Weight
    logistics_pkg = consignment.get("UtilizedLogisticsTransportEquipment") or {}
    if isinstance(logistics_pkg, list):
        logistics_pkg = logistics_pkg[0]

    gross_weight_node = (
        _get(consignment, "GrossWeightMeasure")
        or _get(consignment, "TotalGrossWeightMeasure")
        or {}
    )
    gross_weight = _get(gross_weight_node, "#text") if isinstance(gross_weight_node, dict) else str(gross_weight_node or "")
    weight_unit = _get(gross_weight_node, "unitCode") if isinstance(gross_weight_node, dict) else "K"

    piece_qty_node = (
        _get(consignment, "PackageQuantity")
        or _get(consignment, "TotalPieceQuantity")
        or {}
    )
    piece_quantity = str(piece_qty_node.get("#text", piece_qty_node) if isinstance(piece_qty_node, dict) else piece_qty_node or "1")

    # ── DG Line Items ─────────────────────────────────────────────────────────
    dg_items = []
    transport_items = consignment.get("IncludedSupplyChainConsignmentItem") or []
    if isinstance(transport_items, dict):
        transport_items = [transport_items]

    for item in transport_items:
        dg_goods = item.get("TransportDangerousGoods") or item.get("DangerousGoods") or {}
        if isinstance(dg_goods, list):
            for dg in dg_goods:
                dg_items.append(_parse_dg_item(dg, item))
        elif isinstance(dg_goods, dict) and dg_goods:
            dg_items.append(_parse_dg_item(dg_goods, item))

    # Fallback: try top-level dangerous goods
    if not dg_items:
        top_dg = consignment.get("TransportDangerousGoods") or consignment.get("DangerousGoods") or []
        if isinstance(top_dg, dict):
            top_dg = [top_dg]
        for dg in top_dg:
            dg_items.append(_parse_dg_item(dg, {}))

    # Emergency contact
    emergency_node = doc.get("EmergencyContactInformation") or {}
    emergency_phone = _get(emergency_node, "TelephoneCommunication", "CompleteNumber") or "SEE SDS"
    emergency_name = _get(emergency_node, "ResponsiblePartyName") or ""

    # Signatory
    signatory_node = doc.get("SignatoryContact") or {}
    signatory_name = _get(signatory_node, "PersonName") or ""
    signatory_date = _get(header, "IssueDateTime", "DateTimeString") or _get(header, "IssuedDateTime") or ""

    return {
        "awb_number": awb_number,
        "message_id": message_id,
        "shipper": {"name": shipper_name, "address": shipper_addr},
        "consignee": {"name": consignee_name, "address": consignee_addr},
        "origin": origin,
        "destination": destination,
        "piece_quantity": piece_quantity,
        "gross_weight": gross_weight,
        "weight_unit": weight_unit or "K",
        "dg_items": dg_items,
        "emergency_phone": emergency_phone,
        "emergency_name": emergency_name,
        "signatory_name": signatory_name,
        "signatory_date": str(signatory_date)[:10] if signatory_date else "",
        "source_format": root_key,
    }


def _format_awb(raw: str) -> str:
    """Format an AWB string as XXX-XXXXXXXX."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 11:
        return f"{digits[:3]}-{digits[3:11]}"
    return raw


def _build_address(party: dict) -> str:
    addr = party.get("PostalTradeAddress") or party.get("Address") or {}
    parts = [
        addr.get("LineOne") or addr.get("StreetName", ""),
        addr.get("CityName", ""),
        addr.get("CountryID", "") or addr.get("CountryCode", ""),
    ]
    return ", ".join(p for p in parts if p)


def _extract_location(consignment: dict, event_key: str, location_key: str) -> Optional[str]:
    event = consignment.get(event_key) or {}
    if isinstance(event, list):
        event = event[0]
    loc = event.get(location_key) or {}
    return _get(loc, "ID") or _get(loc, "Name") or None


def _parse_dg_item(dg: dict, parent_item: dict) -> dict:
    """Extract a DG line item from the XML node."""
    un_node = dg.get("UNDGIdentification") or dg.get("UNNumber") or dg.get("UNDGID") or {}
    un_number = (
        _get(un_node, "ID")
        or (un_node if isinstance(un_node, str) else "")
        or dg.get("UNCode", "")
    )
    if un_number and not str(un_number).upper().startswith("UN"):
        un_number = f"UN {un_number}"

    proper_name = (
        dg.get("ProperShippingName")
        or dg.get("TechnicalName")
        or dg.get("ShippingName")
        or "N/A"
    )
    hazard_class = (
        _get(dg, "HazardClassification", "ClassCode")
        or _get(dg, "HazardClass", "Code")
        or dg.get("HazardClass")
        or dg.get("Class")
        or ""
    )
    subsidiary_risk = dg.get("SubsidiaryRisk") or ""
    packing_group = dg.get("PackingGroup") or dg.get("PackingGroupCode") or ""
    packing_inst = dg.get("PackingInstruction") or dg.get("PackingInstructionCode") or ""

    qty_node = (
        dg.get("MeasuredDGProductQuantity")
        or dg.get("Quantity")
        or parent_item.get("GrossWeightMeasure")
        or {}
    )
    quantity = (
        _get(qty_node, "#text")
        or (str(qty_node) if isinstance(qty_node, str) else "")
    )
    qty_unit = _get(qty_node, "unitCode") or "kg"

    net_qty_node = dg.get("NetWeightMeasure") or {}
    net_qty = _get(net_qty_node, "#text") or ""

    authorizations = dg.get("AuthorizationInformation") or ""
    special_provisions = dg.get("SpecialProvision") or ""
    if isinstance(special_provisions, list):
        special_provisions = ", ".join(str(s) for s in special_provisions)

    return {
        "un_number": str(un_number),
        "proper_shipping_name": str(proper_name),
        "hazard_class": str(hazard_class),
        "subsidiary_risk": str(subsidiary_risk),
        "packing_group": str(packing_group),
        "packing_instruction": str(packing_inst),
        "quantity": str(quantity),
        "quantity_unit": str(qty_unit),
        "net_quantity": str(net_qty),
        "authorizations": str(authorizations),
        "special_provisions": str(special_provisions),
    }
