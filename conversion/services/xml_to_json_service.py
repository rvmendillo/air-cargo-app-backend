import xmltodict

def convert_xml_string_to_json(xml_data):
    """
    Core logic: Strips namespaces, removes newlines, renames #text to 'value',
    removes schemaLocation, and forces all nodes into arrays.
    """

    def clean_namespaces(path, key, value):
        # 1. Strip newlines and normalize whitespace
        if isinstance(value, str):
            value = " ".join(value.split())

        # 2. Remove prefixes (ram:, rsm:, xsi:)
        if ':' in key:
            key = key.split(':')[-1]
        
        # 3. Strip @ from attributes
        if key.startswith('@'):
            key = key[1:]
            
        # 4. Strict filter for boilerplate/metadata
        key_lower = key.lower()
        garbage_keys = ['xmlns', 'schemalocation', 'rsm', 'ccts', 'udt', 'ram', 'xsd', 'xsi']
        
        # This catches "schemaLocation", "xsi:schemaLocation", and any "xmlns" tags
        if key_lower in garbage_keys or 'xmlns' in key_lower or 'schemalocation' in key_lower:
            return None
            
        return key, value

    def force_deep_array(data):
        """
        Recursively wraps every dictionary key's value in a list [].
        """
        if isinstance(data, dict):
            return {
                k: force_deep_array(v) if isinstance(v, list) else [force_deep_array(v)]
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [force_deep_array(i) for i in data]
        return data

    try:
        # Step 1: Parse the XML string
        raw_dict = xmltodict.parse(
            xml_data, 
            process_namespaces=False, 
            postprocessor=clean_namespaces,
            cdata_key='value' 
        )
        
        if not raw_dict:
            return {"error": "XML resulted in an empty object"}

        # Step 2: Extract the root key (e.g., ShippersDeclarationForDangerousGoods)
        root_key = list(raw_dict.keys())[0]
        root_content = raw_dict[root_key]

        # Step 3: Transform content into deep arrays
        processed_content = force_deep_array(root_content)

        # Step 4: Return as { "Root": [ { ... } ] }
        return {
            root_key: [processed_content]
        }

    except Exception as e:
        return {"error": f"Internal Conversion Error: {str(e)}"}