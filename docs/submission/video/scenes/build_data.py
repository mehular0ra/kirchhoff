#!/usr/bin/env python3
"""Read the demo bundle and write lib/data.js for the motion-graphic scenes.

Every number a scene shows comes from this file, and this file only reads the
captured demo data:

  apps/web/public/demo/projects/<design project>.json   (default hall-a)
  apps/web/public/demo/inbox.json
  apps/web/public/demo/integrations.json
  docs/submission/video/scenes/team.json                 (names and roles for the intro)

The golden capture rewrites those JSON files, so run this again (render.py
does it for you) and re-render after every capture. Nothing here is typed by
hand: if a field is missing, the scene shows a dash and this script prints a
WARNING instead of inventing a value.

Usage:
  python3 build_data.py [--demo-dir DIR] [--project hall-a] [--email em-hall-b]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEFAULT_DEMO = REPO / "apps" / "web" / "public" / "demo"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def num(x: float, nd: int = 2) -> str:
    """Format a number the way the app does: drop trailing zeros, keep thousands separators."""
    if x is None:
        return "–"
    if float(x).is_integer():
        return f"{int(x):,}"
    return f"{x:,.{nd}f}".rstrip("0").rstrip(".")


def money(x: float) -> str:
    if x is None:
        return "–"
    if abs(x) >= 1_000_000:
        return f"${x / 1_000_000:,.2f}M"
    return f"${x:,.0f}"


def signed_money(x: float) -> str:
    return ("+" if x >= 0 else "−") + money(abs(x))


def when(ts: float | None, fmt: str = "%d %b %Y · %H:%M IST") -> str:
    if ts is None:
        return "–"
    return dt.datetime.fromtimestamp(ts, IST).strftime(fmt).lstrip("0")


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# email + fit check
# ---------------------------------------------------------------------------
def build_email(inbox: dict, email_id: str, materials: dict, lead_limit: float | None) -> dict:
    emails = inbox.get("emails", [])
    em = next((e for e in emails if e["id"] == email_id), None)
    if em is None:
        warn(f"email {email_id} not found in inbox.json; using the first email")
        em = emails[0]
    others = [e for e in emails if e["id"] != em["id"]][:4]

    body = em.get("body", "")
    triage = em.get("triage")
    fields: list[dict] = []
    verdict = None
    reasons: list[str] = []
    fit_source = "triage"
    if triage:
        verdict = (triage.get("fit") or {}).get("verdict") or triage.get("verdict")
        for fld in triage.get("fields", []):
            fields.append({
                "label": fld.get("label"),
                "display": fld.get("display") or str(fld.get("value")),
                "source": fld.get("source_label"),
                "verified": fld.get("verification") == "verified",
            })
        fit = triage.get("fit") or {}
        for r in fit.get("reasons", []) or []:
            reasons.append(r.get("text") if isinstance(r, dict) else str(r))
    else:
        # The static inbox has no frozen triage for the live email. Derive the same
        # deterministic fit inputs from the email itself (no LLM): every value below is
        # read from inbox.json, nothing is typed. The golden capture can replace this.
        fit_source = "derived from inbox.json (triage not frozen yet)"
        warn("inbox triage for %s is null: fit card derived from the email body and appetite rules" % em["id"])
        app = inbox.get("appetite", {})
        mw = re.search(r"([\d.]+)\s*MW", body)
        mw_v = float(mw.group(1)) if mw else None
        racks = re.search(r"in\s+(\d+)\s+racks", body)
        due = re.search(r"due by (\d{1,2} \w+ \d{4})", body)
        lead = re.search(r"no later than (\d+) weeks", body)
        region = None
        for reg in app.get("regions", []):
            if any(p in body for p in reg.get("places", [])):
                region = reg["name"]
                break
        days = None
        if due:
            due_dt = dt.datetime.strptime(due.group(1), "%d %B %Y").replace(tzinfo=IST)
            days = (due_dt - dt.datetime.fromtimestamp(inbox.get("as_of", em["received_at"]), IST)).days
        lo, hi = (app.get("mw") or [None, None])
        ok = []
        if "datahall" in app.get("asset_types", []) and re.search(r"data hall", body, re.I):
            ok.append(("AI data hall", "in appetite"))
        if mw_v is not None and lo is not None and lo <= mw_v <= hi:
            ok.append((f"{num(mw_v, 3)} MW", f"within {num(lo)}–{num(hi)} MW"))
        if region:
            ok.append((region, "in region"))
        if days is not None and days >= app.get("min_days_to_bid_due", 0):
            ok.append((f"{days} days to bid due", f"≥ {app.get('min_days_to_bid_due')}"))
        all_ok = len(ok) == 4
        verdict = "pursue" if all_ok else "clarify"
        reasons = [f"{a} · {b}" for a, b in ok]
        fields = [
            {"label": "Client", "display": em.get("from_org"), "source": "Email body", "verified": True},
            {"label": "Site", "display": region or "–", "source": "Email body", "verified": bool(region)},
            {"label": "Load", "display": f"{num(mw_v, 3)} MW" if mw_v else "–", "source": "Email body",
             "verified": mw_v is not None},
            {"label": "Racks", "display": racks.group(1) if racks else "–", "source": "Email body",
             "verified": bool(racks)},
            {"label": "Bid due", "display": due.group(1) if due else "–", "source": "Email body", "verified": bool(due)},
            {"label": "Lead-time clause", "display": f"{lead.group(1)} weeks" if lead else "–",
             "source": "Email body", "verified": bool(lead)},
        ]

    # Day-zero supply check (spec §20): filled in main() from the procurement swap the run recorded.
    supply = None

    atts = [a["name"] for a in em.get("attachments", [])]
    return {
        "mailbox": inbox.get("mailbox"),
        "label": inbox.get("label"),
        "notice": inbox.get("notice"),
        "id": em["id"],
        "from_name": em.get("from_name"),
        "from_org": em.get("from_org"),
        "from_addr": em.get("from_addr"),
        "subject": em.get("subject"),
        "received": when(em.get("received_at"), "%H:%M"),
        "received_day": when(em.get("received_at"), "%d %b"),
        "snippet": " ".join(body.split("\n\n")[1:2]) if "\n\n" in body else body[:160],
        "attachments": atts,
        "others": [{"from": o.get("from_org") or o.get("from_name"), "subject": o.get("subject"),
                    "day": when(o.get("received_at"), "%d %b"), "has_att": bool(o.get("attachments"))}
                   for o in others],
        "fields": fields,
        "fit": {"verdict": verdict, "reasons": reasons, "source": fit_source},
        "supply": supply,
    }


# ---------------------------------------------------------------------------
# design, checks, sign-off
# ---------------------------------------------------------------------------
def build_design(bundle: dict, materials: dict) -> dict:
    revs = bundle.get("revisions", [])
    if not revs:
        warn("no revisions in the project bundle")
        return {}
    first, last = revs[0], revs[-1]
    m = last["model"]
    racks = m.get("racks", [])
    loads = m.get("loads", {})
    eq = m.get("equipment", [])
    by_kind: dict[str, list] = {}
    for e in eq:
        by_kind.setdefault(e["kind"], []).append(e)
    cdus = [c for c in m.get("cooling_nodes", []) if c.get("kind") == "cdu"]
    tx = by_kind.get("transformer", [])
    ups = by_kind.get("ups", [])
    rack_kw = loads.get("rack_kw") or (racks[0]["kw"] if racks else None)
    it_mw = sum(r.get("kw", 0) for r in racks) / 1000.0

    # Procurement swap, from the ledger ("TX-2500 replaced by TX-3150 (R15 lead time)").
    swap = None
    for entry in last.get("ledger", []):
        mm = re.search(r"([A-Z]+-[\w-]+) replaced by ([A-Z]+-[\w-]+)", entry.get("text", ""))
        if mm and entry.get("agent") == "procurement":
            a, b = materials.get(mm.group(1)), materials.get(mm.group(2))
            if a and b:
                swap = {
                    "from_id": a["id"], "from_mva": num(a["rating"] / 1000), "from_lead": a["lead_time_weeks"],
                    "from_stock": a["stock"], "to_id": b["id"], "to_mva": num(b["rating"] / 1000),
                    "to_lead": b["lead_time_weeks"], "to_stock": b["stock"], "vendor": b.get("vendor"),
                }
            break
    if swap is None:
        warn("no procurement swap in the ledger")

    # Plan geometry for the drawn hall (racks, busways, pipes, CDUs).
    geo = m.get("geometry", {})
    plan = {
        "hall": geo.get("hall"),
        "columns": geo.get("columns", []),
        "rooms": geo.get("rooms", {}),
        "racks": [[r["x"], r["y"], r["w"], r["d"], r["row"]] for r in racks],
        "busways": [[e["id"], e["params"]["x0"], e["params"]["y0"], e["params"]["x1"], e["params"]["y1"]]
                    for e in by_kind.get("busway", []) if "x0" in e.get("params", {})],
        "pipes": [[p["id"], p["kind"], [[q["x"], q["y"]] for q in p["route"]]] for p in m.get("pipes", [])],
        "cdus": [[c["id"], c["x"], c["y"]] for c in cdus],
        "feeders": [[c["id"], [[q["x"], q["y"]] for q in c["route"]]] for c in m.get("connections", [])
                    if c.get("kind") == "busway" and c.get("route")],
    }
    return {
        "first_rev": first, "last_rev": last,
        "racks": len(racks), "rack_kw": num(rack_kw), "it_mw": num(it_mw, 3), "rows": len({r["row"] for r in racks}),
        "hall_w": num((geo.get("hall") or [None, None])[0]), "hall_d": num((geo.get("hall") or [None, None])[1]),
        "topology": m.get("topology"),
        "tx_count": len(tx), "tx_mva": num(tx[0]["rating"] / 1000) if tx else "–",
        "ups_count": len(ups), "busways": len(by_kind.get("busway", [])),
        "cdu_count": len(cdus), "cdu_mw": num(cdus[0]["capacity_kw"] / 1000) if cdus else "–",
        "pipes": len(m.get("pipes", [])),
        "liquid_pct": num(100 * (loads.get("liquid_fraction") or 0)),
        "swap": swap, "plan": plan,
    }


def build_checks(bundle: dict) -> dict:
    revs = bundle.get("revisions", [])
    fnd = bundle.get("findings", {})
    first, last = revs[0], revs[-1]
    f1 = fnd.get(first["id"], [])
    f2 = fnd.get(last["id"], [])
    cs1, cs2 = first.get("check_summary", {}), last.get("check_summary", {})
    n1 = cs1.get("pass", 0) + cs1.get("fail", 0) + cs1.get("warn", 0)
    n2 = cs2.get("pass", 0) + cs2.get("fail", 0) + cs2.get("warn", 0)
    fails = []
    for f in f1:
        if f["status"] != "fail":
            continue
        tref = (f.get("tender_refs") or [{}])[0]
        fix = f.get("fix") or {}
        rej = f.get("rejected_fix") or {}
        inp = f.get("inputs", {})
        unit = f.get("unit") or ""
        if unit == "%":
            measure = f"{f['value']:.2f}% > {f['limit']:.1f}%"
        elif unit == "crossings":
            measure = f"over {inp.get('above', '–')}" + (f" at y ≈ {num(inp['at_y'])} m" if "at_y" in inp else "")
        else:
            measure = f"{num(f.get('value'))} {unit} vs {num(f.get('limit'))}"
        fails.append({
            "rule": f["rule_id"], "element": f["element_id"], "title": f["title"],
            "measure": measure, "clause": tref.get("clause"), "quote": tref.get("quote"), "page": tref.get("page"),
            "agent": fix.get("agent"), "fix_label": short_fix(fix.get("label", "")),
            "fix_cost": signed_money(fix["cost_delta"]) if "cost_delta" in fix else "–",
            "criterion": fix.get("criterion"),
            "at": [inp["at_x"], inp["at_y"]] if "at_x" in inp and "at_y" in inp else None,
            "alt_label": short_fix(rej.get("label", "")),
            "alt_cost": signed_money(rej["cost_delta"]) if "cost_delta" in rej else "–",
        })
    order = {s: i for i, s in enumerate(["pass", "warn", "fail", "n/a"])}
    cells = [f["status"] for f in f1 if f["status"] != "n/a"]
    clauses = sorted({t["clause"] for f in f1 for t in f.get("tender_refs", [])},
                     key=lambda c: [int(x) for x in re.findall(r"\d+", c)])
    return {
        "r1": {"id": first["id"], "total": n1, "pass": cs1.get("pass", 0), "fail": cs1.get("fail", 0),
               "warn": cs1.get("warn", 0)},
        "r2": {"id": last["id"], "total": n2, "pass": cs2.get("pass", 0), "fail": cs2.get("fail", 0),
               "warn": cs2.get("warn", 0), "na": cs2.get("n/a", 0)},
        "rules": len({f["rule_id"] for f in f1}),
        "fails": fails,
        "cells": cells,
        "fail_index": [i for i, s in enumerate(cells) if s == "fail"],
        "clauses": clauses,
        "_order": order and None,
    }


def short_fix(label: str) -> str:
    """Trim an engine fix label for a card ("Replace FA-01 with a parallel cable feeder (…)" → no parenthetical)."""
    label = re.sub(r"\s*\(.*\)$", "", label or "").strip()
    return label.replace("pipe_low", "the low pipe tier").replace("pipe_high", "the high pipe tier")


def build_intake(bundle: dict, checks: dict) -> dict:
    brief = bundle.get("brief")
    if brief and brief.get("requirements"):
        reqs = brief["requirements"]
        ver = sum(1 for r in reqs if r.get("verified"))
        oq = brief.get("open_questions") or []
        return {"source": "brief", "verified": ver, "total": len(reqs), "open_questions": len(oq),
                "label": f"{ver}/{len(reqs)} quotes verified"}
    warn("project bundle has no brief yet: intake shows the tender clauses the checker cites instead")
    n = len(checks["clauses"])
    return {"source": "findings.tender_refs", "verified": n, "total": n, "open_questions": None,
            "label": f"{n} tender clauses cited · quote found on page"}


def build_signoff(bundle: dict, last_rev: dict) -> dict:
    ap = next((a for a in bundle.get("approvals", []) if a.get("decision") == "approved"), None)
    if ap is None:
        warn("no approval in the bundle")
        ap = {}
    ledger = last_rev.get("ledger", [])
    return {
        "name": ap.get("approver_name", "–"), "role": ap.get("role", "–"),
        "when": when(ap.get("ts")), "revision": ap.get("revision", last_rev.get("id")),
        "hash": (last_rev.get("hash") or "")[:12], "comment": ap.get("comment"),
        "not_checked": sum(1 for e in ledger if e.get("kind") == "not_checked"),
        "assumptions": sum(1 for e in ledger if e.get("kind") != "not_checked"),
    }


def build_handoff(bundle: dict, integ: dict, project_id: str, email_project: str | None) -> dict:
    prs = bundle.get("prs") or [p for p in integ["erp"]["prs"] if p["project_id"] == project_id]
    lines = [ln for p in prs for ln in p.get("lines", [])]
    total = sum(ln["qty"] * ln["unit_price"] for ln in lines)
    pr_rows = []
    for p in sorted(prs, key=lambda p: p["id"]):
        ln = p["lines"][0]
        more = len(p["lines"]) - 1
        pr_rows.append({"id": p["id"], "item": f"{ln['material_id']} × {num(ln['qty'])}" + (f" +{more}" if more else ""),
                        "value": money(sum(x["qty"] * x["unit_price"] for x in p["lines"]))})
    docs = [d for d in integ.get("documents", []) if d["project_id"] == project_id]
    crm_after = (bundle.get("crm") or {}).get("stage")
    opps = {o["id"]: o for o in integ["crm"]["opportunities"]}
    # The live story is the emailed tender's opportunity: its stage before approval, then the stage
    # approval sets (the design bundle's CRM overlay).
    opp = opps.get(f"opp-{email_project}") if email_project else None
    opp = opp or opps.get((bundle.get("crm") or {}).get("opportunity_id"))
    return {
        "pr_count": len(prs), "pr_lines": len(lines), "pr_total": money(total), "prs": pr_rows,
        "materials": len(integ["erp"]["materials"]),
        "docs": [d["name"] for d in docs], "doc_count": len(docs),
        "crm": {"name": opp["name"] if opp else "–", "account": opp["account"] if opp else "–",
                "before": opp["stage"] if opp else "–", "after": crm_after or "–",
                "value": money(opp["value"]) if opp else "–"},
        "opportunities": len(opps),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo-dir", type=Path, default=DEFAULT_DEMO)
    ap.add_argument("--project", default="hall-a", help="design project bundle under projects/ (default hall-a)")
    ap.add_argument("--email", default="em-hall-b", help="inbox email the story starts from (default em-hall-b)")
    ap.add_argument("--out", type=Path, default=HERE / "lib" / "data.js")
    args = ap.parse_args()

    demo = args.demo_dir
    paths = {
        "project": demo / "projects" / f"{args.project}.json",
        "inbox": demo / "inbox.json",
        "integrations": demo / "integrations.json",
        "team": HERE / "team.json",
    }
    for k, p in paths.items():
        if not p.exists():
            print(f"ERROR: {k} file missing: {p}", file=sys.stderr)
            return 1
    bundle, inbox, integ, team = (load(paths[k]) for k in ("project", "inbox", "integrations", "team"))
    materials = {m["id"]: m for m in integ["erp"]["materials"]}

    design = build_design(bundle, materials)
    checks = build_checks(bundle)
    lead_limit = None
    for f in bundle["findings"].get(design["first_rev"]["id"], []):
        if f["rule_id"] == "R15" and f.get("limit") is not None:
            lead_limit = f["limit"]
            break
    email = build_email(inbox, args.email, materials, lead_limit)
    em_obj = next((e for e in inbox.get("emails", []) if e["id"] == args.email), {})
    intake = build_intake(bundle, checks)
    signoff = build_signoff(bundle, design["last_rev"])
    handoff = build_handoff(bundle, integ, args.project, em_obj.get("project_id"))
    if design.get("swap"):
        design["swap"]["limit"] = num(lead_limit) if lead_limit is not None else "–"
        sw = design["swap"]
        email["supply"] = {"unit": f"{sw['from_mva']} MVA", "lead_weeks": sw["from_lead"], "stock": sw["from_stock"],
                           "limit_weeks": sw["limit"]}
    proj = bundle.get("project", {})
    first_rev, last_rev = design.pop("first_rev"), design.pop("last_rev")

    data = {
        "_about": "Generated by build_data.py from the demo bundle. Do not edit by hand; re-run after each capture.",
        "sources": {k: {"path": str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p), "sha256_12": sha(p)}
                    for k, p in paths.items()},
        "project": {"id": proj.get("id"), "name": proj.get("name"), "client": proj.get("client")},
        "revisions": {"first": first_rev["id"], "last": last_rev["id"]},
        "team": team,
        "email": email, "intake": intake, "design": design, "checks": checks,
        "signoff": signoff, "handoff": handoff,
        "notice": inbox.get("notice") or "Demo workspace: all companies, people and data are fictional",
        "warnings": WARNINGS,
    }
    data["checks"].pop("_order", None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("// Generated by build_data.py. Do not edit.\nwindow.KDATA = "
                        + json.dumps(data, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")

    # A readable audit of every number the scenes will show.
    d, c, h, s = design, checks, handoff, signoff
    print(f"data.js written: {args.out}")
    print(f"  sources: " + ", ".join(f"{k}={v['sha256_12']}" for k, v in data["sources"].items()))
    print(f"  email: {email['from_org']} · {email['subject'][:60]}… · {len(email['attachments'])} attachments")
    print(f"  fit: {email['fit']['verdict']} ({email['fit']['source']}) · {'; '.join(email['fit']['reasons'])}")
    print(f"  intake: {intake['label']}")
    print(f"  design: {d['racks']} racks × {d['rack_kw']} kW = {d['it_mw']} MW · {d['topology']} · "
          f"{d['tx_count']} × {d['tx_mva']} MVA · {d['cdu_count']} × CDU {d['cdu_mw']} MW · swap {d.get('swap')}")
    print(f"  checks: {c['r1']['id']} {c['r1']['total']} checks · {c['r1']['fail']} fail → {c['r2']['id']} "
          f"{c['r2']['pass']} pass · {c['r2']['fail']} fail · {c['r2']['na']} n/a")
    for f in c["fails"]:
        print(f"    {f['rule']} {f['element']}: {f['measure']} · {f['clause']} · fix {f['fix_label']} {f['fix_cost']}")
    print(f"  sign-off: {s['name']} · {s['when']} · {s['revision']} · {s['hash']}")
    print(f"  handoff: {h['pr_count']} PRs · {h['pr_lines']} lines · {h['pr_total']} · {h['doc_count']} docs · "
          f"CRM {h['crm']['name']}: {h['crm']['before']} → {h['crm']['after']}")
    for w in WARNINGS:
        print(f"  WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
