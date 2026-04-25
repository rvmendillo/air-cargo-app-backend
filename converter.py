import xmltodict
import json
from typing import Dict, Any, List, Union


def strip_namespace(key: str) -> str:
    """Remove namespace prefix (e.g. 'rsm:', 'ram:') from a key."""
    if ':' in key and not key.startswith('@') and not key.startswith('#'):
        return key.split(':', 1)[1]
    return key


def transform_value(value: Any) -> List:
    """
    Recursively transforms an xmltodict value into the required array-wrapped format.
    Rules:
      - Every value is wrapped in a list: ["value"] or [{...}]
      - XML attributes (@key) become sibling keys with their value also wrapped in a list
      - Text content (#text) is extracted and merged with attributes
      - Nested dicts are recursively transformed
      - Lists (repeated elements) are kept as list items, each transformed
    """
    if isinstance(value, list):
        return [transform_node(item) for item in value]
    elif isinstance(value, dict):
        return [transform_node(value)]
    elif value is None:
        return [""]
    else:
        return [str(value)]


def transform_node(node: Any) -> Any:
    """
    Transform a single node (dict) or scalar into the output format.
    """
    if not isinstance(node, dict):
        return str(node) if node is not None else ""

    result = {}
    text_value = None
    attrs = {}

    for raw_key, val in node.items():
        if raw_key == '#text':
            text_value = val
        elif raw_key.startswith('@'):
            # Attribute — strip the @ prefix and namespace
            attr_name = strip_namespace(raw_key[1:])
            attrs[attr_name] = val
        else:
            clean_key = strip_namespace(raw_key)
            result[clean_key] = transform_value(val)

    # If node has both attributes and text, merge them
    if text_value is not None:
        for attr_name, attr_val in attrs.items():
            result[attr_name] = [str(attr_val)]
        result['value'] = [str(text_value)]
    elif attrs:
        # Attributes-only node with no children — rare, but handle it
        for attr_name, attr_val in attrs.items():
            result[attr_name] = [str(attr_val)]

    return result


def convert_xml_to_onerecord_jsonld(xml_string: str) -> Dict[str, Any]:
    """
    Parses an IATA ShippersDeclarationForDangerousGoods (or similar) XML and converts it
    into a structured JSON format where every value is array-wrapped.
    """
    try:
        # Parse XML — force_list not needed; we handle lists via transform
        parsed_dict = xmltodict.parse(xml_string, attr_prefix='@', cdata_key='#text')

        if not parsed_dict:
            raise ValueError("Empty XML Document")

        # Get the root element key (e.g. "rsm:ShippersDeclarationForDangerousGoods")
        root_raw_key = list(parsed_dict.keys())[0]
        root_clean_key = strip_namespace(root_raw_key)
        root_data = parsed_dict[root_raw_key]

        # Build the output — root is also array-wrapped per the spec
        output = {
            root_clean_key: transform_value(root_data)
        }

        return output

    except Exception as e:
        return {
            "error": "Failed to parse XML",
            "details": str(e),
            "raw_input_preview": xml_string[:200] + "..." if len(xml_string) > 200 else xml_string
        }
