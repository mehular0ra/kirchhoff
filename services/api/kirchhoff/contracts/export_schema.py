import json
import sys
from pathlib import Path

from pydantic.json_schema import models_json_schema

from . import (Material, Opportunity, ProjectBundle, PurchaseRequisition, RunEvent, TopologyOption,
               WhatIfResult)

TOP_LEVEL = [ProjectBundle, RunEvent, TopologyOption, WhatIfResult, PurchaseRequisition, Material, Opportunity]


def _remove_property_titles(obj):
    """Recursively remove 'title' keys from property schemas (keep titles on $defs models)."""
    if isinstance(obj, dict):
        # If this is a properties dict, remove titles from each property schema
        if "properties" in obj:
            for prop_schema in obj["properties"].values():
                if isinstance(prop_schema, dict) and "title" in prop_schema:
                    del prop_schema["title"]
        # Recursively process all values
        for value in obj.values():
            _remove_property_titles(value)
    elif isinstance(obj, list):
        for item in obj:
            _remove_property_titles(item)


def _convert_prefix_items_to_array(obj):
    """Convert prefixItems tuples to proper array schemas with minItems/maxItems."""
    if isinstance(obj, dict):
        # If this has prefixItems, convert to array schema
        if "prefixItems" in obj:
            prefix_items = obj.pop("prefixItems")
            # Create a union of all item types
            item_types = set()
            for item_schema in prefix_items:
                if isinstance(item_schema, dict):
                    if "type" in item_schema:
                        item_types.add(item_schema["type"])
                    elif "enum" in item_schema:
                        item_types.add("string")  # enum values are strings

            # Set proper array schema
            obj["type"] = "array"
            if item_types:
                if len(item_types) == 1:
                    obj["items"] = {"type": list(item_types)[0]}
                else:
                    # Multiple types - use anyOf
                    obj["items"] = {"anyOf": [{"type": t} for t in sorted(item_types)]}
            obj["minItems"] = len(prefix_items)
            obj["maxItems"] = len(prefix_items)

        # Recursively process all values
        for value in obj.values():
            _convert_prefix_items_to_array(value)
    elif isinstance(obj, list):
        for item in obj:
            _convert_prefix_items_to_array(item)


def build_schema(out: Path) -> None:
    _, schema = models_json_schema([(m, "serialization") for m in TOP_LEVEL], title="KirchhoffContracts")

    # Post-process schema to fix json2ts issues
    _remove_property_titles(schema)
    _convert_prefix_items_to_array(schema)

    # Add properties to root schema so json2ts exports all models as top-level interfaces
    schema["properties"] = {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in TOP_LEVEL}

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    build_schema(Path(sys.argv[1] if len(sys.argv) > 1 else "build/schema.json"))
