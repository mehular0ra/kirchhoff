import json
import sys
from pathlib import Path

from pydantic.json_schema import models_json_schema

from . import (Material, Opportunity, ProjectBundle, PurchaseRequisition, RunEvent, TopologyOption,
               WhatIfResult)

TOP_LEVEL = [ProjectBundle, RunEvent, TopologyOption, WhatIfResult, PurchaseRequisition, Material, Opportunity]


def build_schema(out: Path) -> None:
    _, schema = models_json_schema([(m, "serialization") for m in TOP_LEVEL], title="KirchhoffContracts")
    # Add properties to root schema so json2ts exports all models as top-level interfaces
    schema["properties"] = {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in TOP_LEVEL}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    build_schema(Path(sys.argv[1] if len(sys.argv) > 1 else "build/schema.json"))
