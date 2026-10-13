import json
from pathlib import Path

from kirchhoff.contracts import (
    Citation, ClauseRef, DesignModel, Equipment, Connection, Rack, Point3, Geometry,
    CoolingNode, Pipe, RunEvent, Finding, Revision, LedgerEntry, ProjectBundle, Project,
    TopologyOption, RunRecord, WhatIfResult, PurchaseRequisition, PRLine, Material,
)
from kirchhoff.contracts.export_schema import build_schema


def _model() -> DesignModel:
    return DesignModel(
        topology="2N",
        racks=[Rack(id="R1-01", row="R1", x=6.0, y=15.9, kw=132.0, liquid_fraction=0.8, feeds=("A-01", "B-01"))],
        equipment=[Equipment(id="A1", kind="lv_board", rating=3150.0, unit="kVA", system="A", room="A")],
        connections=[Connection(id="FA-01", src="A1", dst="A-01", kind="busway", length_m=82.0,
                                route=[Point3(x=66, y=4, z=3.2), Point3(x=6, y=2, z=3.2)])],
        cooling_nodes=[CoolingNode(id="CDU-1", kind="cdu", zone="Z1", capacity_kw=1200.0, x=8.0, y=30.0)],
        pipes=[Pipe(id="H-Z1", kind="header", zone="Z1", dn=200, tier="pipe_high",
                    route=[Point3(x=8, y=30, z=3.8), Point3(x=8, y=22, z=3.8)])],
        geometry=Geometry(hall=(60.0, 36.0), columns=[(0.0, 0.0)], keepouts=[(10.0, 10.0, 18.0, 26.0)],
                          rooms={"A": (60.0, 0.0, 72.0, 10.0)}, tiers={"pipe_low": 2.6, "busway": 3.2, "pipe_high": 3.8}),
        loads={"rack_kw": 132.0, "liquid_fraction": 0.8, "aux_mw": 0.30, "pumps_kw": 135.0},
    )


def test_design_model_round_trip():
    m = _model()
    again = DesignModel.model_validate_json(m.model_dump_json())
    assert again == m


def test_finding_requires_rule_and_status():
    f = Finding(id="R05:FA-01", rule_id="R05", element_id="FA-01", status="fail", title="Voltage drop",
                clause_refs=[ClauseRef(standard="IEC 60364-5-52", clause="§525")],
                tender_refs=[Citation(doc_id="tender-hall-a", page=4, quote="shall not exceed 2.0%", clause="§4.6")],
                formula="ΔU% = 100·√3·I·L·(R cosφ + X sinφ)/U", inputs={"I_A": 1546.0, "L_m": 82.0},
                value=2.16, limit=2.0, unit="%", explanation="{value} exceeds {limit}")
    assert f.status == "fail"


def test_bundle_round_trip_and_defaults():
    b = ProjectBundle(project=Project(id="hall-a", name="Deccan AI Campus · Hall A", client="Deccan Compute",
                                      asset_pack="datahall", state="signed", sample=True, updated_at=0.0))
    again = ProjectBundle.model_validate_json(b.model_dump_json())
    assert again.events == [] and again.revisions == [] and again.what_ifs == []


def test_schema_export_contains_all_top_level_models(tmp_path: Path):
    out = tmp_path / "schema.json"
    build_schema(out)
    schema = json.loads(out.read_text())
    for name in ["ProjectBundle", "DesignModel", "RunEvent", "Finding", "Revision", "RunRecord",
                 "TopologyOption", "WhatIfResult", "PurchaseRequisition", "Material"]:
        assert name in schema["$defs"], name


def test_schema_no_property_titles(tmp_path: Path):
    """Verify schema has no 'title' keys in property schemas (prevents json2ts name collisions)."""
    out = tmp_path / "schema.json"
    build_schema(out)
    schema = json.loads(out.read_text())

    def has_property_title(obj, path=""):
        """Recursively check for titles in property schemas."""
        if isinstance(obj, dict):
            # Check if this is a properties dict and has titles in its values
            if "properties" in obj:
                for prop_name, prop_schema in obj["properties"].items():
                    if isinstance(prop_schema, dict) and "title" in prop_schema:
                        return True, f"{path}.properties.{prop_name}"
            # Recursively check all values
            for key, value in obj.items():
                result, found_path = has_property_title(value, f"{path}.{key}")
                if result:
                    return True, found_path
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                result, found_path = has_property_title(item, f"{path}[{i}]")
                if result:
                    return True, found_path
        return False, ""

    has_title, location = has_property_title(schema)
    assert not has_title, f"Found property title at {location}"


def test_schema_no_prefix_items(tmp_path: Path):
    """Verify schema has no prefixItems (converted to proper array schema)."""
    out = tmp_path / "schema.json"
    build_schema(out)
    schema_text = out.read_text()
    assert "prefixItems" not in schema_text, "Schema contains prefixItems (should be converted to minItems/maxItems)"
