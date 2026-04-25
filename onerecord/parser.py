"""
ONE Record JSON-LD Parser

Transforms raw ONE Record JSON-LD responses into structured dashboard data.
Hierarchy: MASTER Waybill > HOUSE Waybills > Shipment > Pieces > ProductDg
                                                      > DgDeclaration
           MASTER Waybill > Checks > Sub-checks
"""

# ── Namespace prefixes ──────────────────────────────────────────────────────
CARGO = "https://onerecord.iata.org/ns/cargo#"
API = "https://onerecord.iata.org/ns/api#"
DG = "https://onerecord.champ.aero/ns/dangerous-goods#"


def _get(obj, key, default=None):
    """Safely get a value from a dict by full-URI key."""
    if not isinstance(obj, dict):
        return default
    return obj.get(key, default)


def _get_id(obj):
    """Extract @id from an object."""
    if isinstance(obj, dict):
        return obj.get("@id")
    return None


def _last_segment(uri):
    """Extract the last path segment from a URI, also handling # fragments."""
    if not uri:
        return None
    # First split by '/' to get the last path segment
    parts = str(uri).rstrip("/").split("/")
    segment = parts[-1] if parts else str(uri)
    # If the segment contains a '#', return only the part after '#'
    # e.g. "iata-three-letter-codes#AMS" → "AMS"
    if "#" in segment:
        return segment.split("#")[-1]
    return segment


def _extract_location_code(location_obj):
    """Extract a location code (e.g. 'AMS', 'GVA') from a Location object."""
    if not isinstance(location_obj, dict):
        return None
    codes = _get(location_obj, f"{CARGO}locationCodes", [])
    if isinstance(codes, dict):
        codes = [codes]
    for code in codes:
        code_id = _get_id(code)
        if code_id:
            return _last_segment(code_id)
    # Fallback to locationName
    return _get(location_obj, f"{CARGO}locationName")


def _ensure_list(val):
    """Wrap a single item in a list, or return [] for None."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


# ── ProductDg parser ────────────────────────────────────────────────────────
def _parse_product_dg(product):
    """Parse a ProductDg object into a DangerousGood dict."""
    if not isinstance(product, dict):
        return None

    # Extract net weight
    net_weight_obj = _get(product, f"{DG}productNetWeight") or _get(product, f"{CARGO}netWeight")
    quantity = None
    unit = None
    if isinstance(net_weight_obj, dict):
        quantity = _get(net_weight_obj, f"{CARGO}numericalValue")
        unit_obj = _get(net_weight_obj, f"{CARGO}unit")
        if isinstance(unit_obj, dict):
            unit = _last_segment(_get_id(unit_obj))
        elif isinstance(unit_obj, str):
            unit = unit_obj
        if not unit:
            unit = "kg"  # default

    return {
        "unNumber": _get(product, f"{CARGO}unNumber"),
        "properShippingName": _get(product, f"{CARGO}properShippingName"),
        "hazardClass": _get(product, f"{CARGO}hazardClassificationId"),
        "packingGroup": _get(product, f"{CARGO}packagingDangerLevelCode"),
        "quantity": quantity,
        "unit": unit,
        "packingInstruction": _get(product, f"{CARGO}packingInstructionNumber"),
        "radioactive": None,
        "qValue": _get(product, f"{DG}hazardCategoryCode"),
    }


# ── Piece parser ────────────────────────────────────────────────────────────
def _parse_piece(piece):
    """Parse a PieceDg object into a Piece dict."""
    if not isinstance(piece, dict):
        return None

    # Parse dangerous goods (contentProducts)
    products = _ensure_list(_get(piece, f"{CARGO}contentProducts", []))
    dangerous_goods = []
    for p in products:
        dg = _parse_product_dg(p)
        if dg:
            dangerous_goods.append(dg)

    # Parse packaging type description
    pkg_type = _get(piece, f"{CARGO}packagingType")
    piece_description = None
    if isinstance(pkg_type, dict):
        piece_description = _get(pkg_type, f"{CARGO}description")

    return {
        "pieceId": _last_segment(_get_id(piece)),
        "pieceDescription": piece_description,
        "weight": None,
        "weightUnit": None,
        "dangerousGoods": dangerous_goods,
        "dgDeclaration": {
            "declarationType": None,
            "declarationDate": None,
            "shipperSignature": None,
            "complianceMethod": None,
        },
    }


# ── Shipment parser ─────────────────────────────────────────────────────────
def _parse_shipment(shipment, dg_declaration_obj=None):
    """Parse a Shipment object."""
    if not isinstance(shipment, dict):
        return None

    pieces_raw = _ensure_list(_get(shipment, f"{CARGO}pieces", []))
    pieces = []
    for p in pieces_raw:
        piece = _parse_piece(p)
        if piece:
            pieces.append(piece)

    # Parse involved parties for description (shipper name)
    parties = _ensure_list(_get(shipment, f"{CARGO}involvedParties", []))
    shipper_name = None
    for party in parties:
        role = _get(party, f"{CARGO}partyRole")
        role_id = _get_id(role) if isinstance(role, dict) else None
        if role_id and "SHP" in role_id:
            details = _get(party, f"{CARGO}partyDetails")
            if isinstance(details, dict):
                shipper_name = _get(details, f"{CARGO}name")

    # Parse DG declaration if available
    dg_decl = dg_declaration_obj or _get(shipment, f"{DG}dgDeclaration")
    if isinstance(dg_decl, dict):
        departure_loc = _get(dg_decl, f"{CARGO}departureLocation")
        arrival_loc = _get(dg_decl, f"{CARGO}arrivalLocation")
        origin_code = _extract_location_code(departure_loc)
        dest_code = _extract_location_code(arrival_loc)

        decl_data = {
            "declarationType": _get(dg_decl, f"{CARGO}handlingInformation"),
            "declarationDate": _get(dg_decl, f"{CARGO}declarationDate"),
            "shipperSignature": _get(dg_decl, f"{DG}shipperSignatory"),
            "complianceMethod": (
                f"Exclusive use: {_get(dg_decl, f'{CARGO}exclusiveUseIndicator', 'N/A')}"
            ),
        }

        # Apply declaration data to all pieces
        for piece in pieces:
            piece["dgDeclaration"] = decl_data

        # Use origin/dest from declaration for shipment-level data
        return {
            "shipmentId": _last_segment(_get_id(shipment)),
            "description": shipper_name,
            "totalWeight": None,
            "weightUnit": None,
            "pieceCount": str(len(pieces)),
            "commodity": f"{origin_code or '?'} → {dest_code or '?'}",
            "pieces": pieces,
        }

    return {
        "shipmentId": _last_segment(_get_id(shipment)),
        "description": shipper_name,
        "totalWeight": None,
        "weightUnit": None,
        "pieceCount": str(len(pieces)),
        "commodity": None,
        "pieces": pieces,
    }


# ── Check parser ────────────────────────────────────────────────────────────
def _parse_check(check):
    """Parse a Check object."""
    if not isinstance(check, dict):
        return None

    check_name = _get(check, f"{DG}checkname") or _get(check, f"{CARGO}checkName")

    # Parse total result
    total_result = _get(check, f"{CARGO}checkTotalResult")
    result_str = None
    checked_by = None
    check_date = None
    if isinstance(total_result, dict):
        result_str = _get(total_result, f"{DG}checkResult")
        certified_on = _get(total_result, f"{DG}certifiedOn")
        check_date = certified_on

        # Get the certifier
        certifier = _get(total_result, f"{CARGO}certifiedByActor")
        if isinstance(certifier, dict):
            first_name = _get(certifier, f"{CARGO}firstName", "")
            employee_id = _get(certifier, f"{CARGO}employeeId", "")
            checked_by = f"{first_name} ({employee_id})".strip() if first_name else employee_id

    # If no total result, check for sub-check status info
    if not check_date:
        check_date = (
            _get(check, f"{CARGO}actionEndTime")
            or _get(check, f"{DG}createdOn")
        )

    # Get checker for sub-checks
    if not checked_by:
        checker = _get(check, f"{CARGO}checker")
        if isinstance(checker, dict):
            first_name = _get(checker, f"{CARGO}firstName", "")
            employee_id = _get(checker, f"{CARGO}employeeId", "")
            checked_by = f"{first_name} ({employee_id})".strip() if first_name else employee_id

    # Parse sub-checks as remarks
    sub_checks = _ensure_list(_get(check, f"{CARGO}checks", []))
    sub_check_names = [_get(sc, f"{DG}checkname", "Unknown") for sc in sub_checks if isinstance(sc, dict)]
    remarks = f"Sub-checks: {', '.join(sub_check_names)}" if sub_check_names else _get(check, f"{DG}checkStatus")

    return {
        "checkType": check_name,
        "checkResult": result_str,
        "checkDate": check_date,
        "checkedBy": checked_by,
        "remarks": remarks,
    }


def _parse_sub_checks(check):
    """Parse sub-checks from a parent Check object into individual CheckResult dicts."""
    sub_checks_raw = _ensure_list(_get(check, f"{CARGO}checks", []))
    results = []
    for sc in sub_checks_raw:
        if not isinstance(sc, dict):
            continue
        check_name = _get(sc, f"{DG}checkname")
        start_time = _get(sc, f"{CARGO}actionStartTime")
        end_time = _get(sc, f"{CARGO}actionEndTime")

        checker = _get(sc, f"{CARGO}checker")
        checked_by = None
        if isinstance(checker, dict):
            first_name = _get(checker, f"{CARGO}firstName", "")
            employee_id = _get(checker, f"{CARGO}employeeId", "")
            checked_by = f"{first_name} ({employee_id})".strip() if first_name else employee_id

        results.append({
            "checkType": check_name,
            "checkResult": "OK" if end_time else "PENDING",
            "checkDate": end_time or start_time,
            "checkedBy": checked_by,
            "remarks": None,
        })
    return results


# ── Waybill parser ──────────────────────────────────────────────────────────
def _parse_waybill_info(waybill, awb_input=None):
    """Parse a Waybill object into a WaybillInfo dict."""
    if not isinstance(waybill, dict):
        return None

    waybill_type = _get(waybill, f"{CARGO}waybillType")
    type_id = _get_id(waybill_type) if isinstance(waybill_type, dict) else None
    type_label = _last_segment(type_id) if type_id else None

    waybill_number = _get(waybill, f"{CARGO}waybillNumber")

    # Try to extract origin/destination from the shipment's DG declaration
    origin = None
    destination = None

    # Look into the shipment for DG declaration locations
    shipment = _get(waybill, f"{CARGO}shipment")
    if isinstance(shipment, dict):
        dg_decl = _get(shipment, f"{DG}dgDeclaration")
        if isinstance(dg_decl, dict):
            dep_loc = _get(dg_decl, f"{CARGO}departureLocation")
            arr_loc = _get(dg_decl, f"{CARGO}arrivalLocation")
            origin = _extract_location_code(dep_loc)
            destination = _extract_location_code(arr_loc)

    return {
        "id": _get_id(waybill),
        "awbNumber": waybill_number or awb_input,
        "prefix": None,
        "origin": origin,
        "destination": destination,
        "carrier": None,
        "type": type_label,
    }


# ── Main parser ─────────────────────────────────────────────────────────────
def parse_onerecord_awb(raw_json, awb_id=None):
    """
    Parse a ONE Record JSON-LD AWB response into an AwbDashboardData structure.

    Args:
        raw_json: The raw JSON-LD dict from the ONE Record API
        awb_id: The AWB ID that was queried (for display fallback)

    Returns:
        dict matching the AwbDashboardData interface
    """
    if not isinstance(raw_json, dict):
        return {
            "masterWaybill": None,
            "houseWaybills": [],
            "shipments": [],
            "checks": [],
            "rawData": raw_json,
        }

    # ── Master Waybill ──────────────────────────────────────────────────────
    master_waybill = _parse_waybill_info(raw_json, awb_input=awb_id)

    # ── House Waybills ──────────────────────────────────────────────────────
    house_waybills_raw = _ensure_list(_get(raw_json, f"{CARGO}houseWaybills", []))
    house_waybills = []
    shipments = []

    for hwb in house_waybills_raw:
        if not isinstance(hwb, dict):
            continue
        hwb_info = _parse_waybill_info(hwb)
        if hwb_info:
            house_waybills.append(hwb_info)

        # Extract shipment from house waybill
        shipment_obj = _get(hwb, f"{CARGO}shipment")
        if isinstance(shipment_obj, dict):
            dg_decl = _get(shipment_obj, f"{DG}dgDeclaration")
            shipment = _parse_shipment(shipment_obj, dg_decl)
            if shipment:
                shipments.append(shipment)

    # ── Enrich master waybill with data from house waybills ─────────────────
    if master_waybill:
        # Inherit origin/destination from the first house waybill that has them
        if not master_waybill.get("origin") or not master_waybill.get("destination"):
            for hwb_info in house_waybills:
                if hwb_info.get("origin") and not master_waybill.get("origin"):
                    master_waybill["origin"] = hwb_info["origin"]
                if hwb_info.get("destination") and not master_waybill.get("destination"):
                    master_waybill["destination"] = hwb_info["destination"]
                if master_waybill.get("origin") and master_waybill.get("destination"):
                    break

    # ── Checks ──────────────────────────────────────────────────────────────
    # Look for checks at master waybill level
    checks_raw = _ensure_list(_get(raw_json, f"{CARGO}checks", []))
    checks = []
    for c in checks_raw:
        parent_check = _parse_check(c)
        if parent_check:
            checks.append(parent_check)
        sub_checks = _parse_sub_checks(c)
        checks.extend(sub_checks)

    # Also look for checks inside house waybills and their shipments
    if not checks:
        for hwb in house_waybills_raw:
            if not isinstance(hwb, dict):
                continue
            hwb_checks = _ensure_list(_get(hwb, f"{CARGO}checks", []))
            for c in hwb_checks:
                parent_check = _parse_check(c)
                if parent_check:
                    checks.append(parent_check)
                sub_checks = _parse_sub_checks(c)
                checks.extend(sub_checks)
            shipment_obj = _get(hwb, f"{CARGO}shipment")
            if isinstance(shipment_obj, dict):
                ship_checks = _ensure_list(_get(shipment_obj, f"{CARGO}checks", []))
                for c in ship_checks:
                    parent_check = _parse_check(c)
                    if parent_check:
                        checks.append(parent_check)
                    sub_checks = _parse_sub_checks(c)
                    checks.extend(sub_checks)

    return {
        "masterWaybill": master_waybill,
        "houseWaybills": house_waybills,
        "shipments": shipments,
        "checks": checks,
        "rawData": raw_json,
    }
