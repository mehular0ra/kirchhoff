"""The bids inbox of the demo world (spec §20): the bids@ mailbox (sandbox, simulated), its rendered attachments and
the Firestore seed. Deterministic for a given world.yaml: reportlab invariant, seeded scan noise, no wall clock.
The precomputed triage comes from scenarios/demo_world/captures/inbox-triage.json, which WS2's
`python -m kirchhoff.inbox.precompute` writes at golden-capture time (addendum ruling B5)."""
import hashlib
import io
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict

from kirchhoff.store import Store
from kirchhoff.store.validate import firestore_safe_problems

from ..model import FICTIONAL_NOTICE, ILLUSTRATIVE, SANDBOX_LABEL
from ..paths import scenarios_dir
from .config import Appetite, InboxAttachmentCfg, WorldConfig, rng_for

__all__ = ["Appetite", "InboxAttachment", "InboxEmail", "InboxSeed", "InboxBuild", "build_inbox", "write_inbox",
           "inbox_diff_on_disk", "load_inbox", "load_inbox_seed", "inbox_seed_path", "load_triage_capture",
           "letter_pdf", "scan_pdf"]

DEMO = "apps/web/public/demo"
INBOX_JSON = f"{DEMO}/inbox.json"
INBOX_DIR = f"{DEMO}/inbox"
INBOX_SEED = "scenarios/demo_world/out/inbox_seed.json"
INBOX_OUT_DIR = "scenarios/demo_world/out/inbox"
TRIAGE_CAPTURE = "scenarios/demo_world/captures/inbox-triage.json"
MANAGED_DIRS = (INBOX_DIR, INBOX_OUT_DIR)
SEED_DOC = "seed/inbox"
SEED_EMAILS = "seed/inbox/emails"
CAPTURE_VERSION = 1


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InboxAttachment(_M):
    id: str
    name: str
    url: str  # browser URL: /demo/docs/{reuse} (WS3 sync script) or /demo/inbox/{file}
    source: str  # path under the scenarios dir: hall_a/out/{reuse} or demo_world/out/inbox/{file}
    content_type: str = "application/pdf"


class InboxEmail(_M):
    id: str
    from_name: str
    from_addr: str
    from_org: str
    to: str
    subject: str
    received_at: float
    body: str
    attachments: list[InboxAttachment] = []
    project_id: str | None = None
    live_triage: bool = False
    triage: dict[str, Any] | None = None  # WS2 TriageResult JSON (precomputed); null until captured


class InboxSeed(_M):
    mailbox: str
    label: str = SANDBOX_LABEL
    notice: str = FICTIONAL_NOTICE
    as_of: float  # the world anchor: days to a bid deadline are counted from here, never from the wall clock
    appetite: Appetite
    emails: list[InboxEmail]  # newest first


@dataclass
class InboxBuild:
    seed: InboxSeed
    files: dict[str, bytes] = field(default_factory=dict)  # repo-relative path -> bytes

    def digest(self) -> str:
        manifest = {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(self.files.items())}
        return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()


_SUBST = {"—": "-", "–": "-", "·": "-", "≤": "<=", "≥": ">=", "→": "->"}


def _latin1(s: str) -> str:
    text = "".join(_SUBST.get(ch, ch) for ch in s)
    return text.encode("latin-1", "replace").decode("latin-1")


def letter_pdf(title: str, lines: list[str]) -> bytes:
    """A one-page text PDF (pdfplumber can verify quotes on it), with the illustrative and fictional labels."""
    from reportlab import rl_config

    rl_config.invariant = 1
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=13, leading=17, spaceAfter=8)
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=6)
    note = ParagraphStyle("n", fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=colors.grey)
    story = [Paragraph(escape(_latin1(title)), h1)]
    story += [Paragraph(escape(_latin1(line)), body) for line in lines]
    story += [Spacer(1, 8 * mm), Paragraph(escape(_latin1(ILLUSTRATIVE)), note),
              Paragraph(escape(_latin1(FICTIONAL_NOTICE)), note)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, title=_latin1(title), author="Kirchhoff demo world", leftMargin=20 * mm,
                      rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm).build(story)
    return buf.getvalue()


def scan_pdf(title: str, lines: list[str], rng: random.Random) -> bytes:
    """A one-page image-only PDF that looks like a scan: no text layer, so pdfplumber finds nothing and the trust
    rules mark anything read from it "unverified (scan)" (spec §20); Gemini can still read the image."""
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    w, h = 1240, 1754  # A4 at 150 dpi
    img = Image.new("L", (w, h), 244)
    draw = ImageDraw.Draw(img)
    draw.text((110, 130), _latin1(title), fill=20, font=ImageFont.load_default(size=36))
    y = 230
    for line in lines:
        draw.text((110, y), _latin1(line), fill=35, font=ImageFont.load_default(size=28))
        y += 56
    small = ImageFont.load_default(size=20)
    draw.text((110, h - 150), _latin1(ILLUSTRATIVE), fill=90, font=small)
    draw.text((110, h - 118), _latin1(FICTIONAL_NOTICE), fill=90, font=small)
    for _ in range(2500):  # scanner speckle, seeded
        img.putpixel((rng.randrange(w), rng.randrange(h)), rng.randrange(150, 235))
    img = img.rotate(0.6, resample=Image.Resampling.BILINEAR, fillcolor=244)
    png = io.BytesIO()
    img.save(png, format="PNG")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    c.setTitle(_latin1(title))
    c.setAuthor("Kirchhoff demo world")
    c.drawImage(ImageReader(io.BytesIO(png.getvalue())), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    return buf.getvalue()


def _attachment(cfg: WorldConfig, email_id: str, a: InboxAttachmentCfg, scenarios_root: Path,
                files: dict[str, bytes]) -> InboxAttachment:
    if (a.reuse is None) == (a.file is None):
        raise ValueError(f"{email_id}/{a.id}: set exactly one of reuse and file")
    if a.reuse is not None:
        if not (scenarios_root / "hall_a" / "out" / a.reuse).is_file():
            raise FileNotFoundError(f"{email_id}/{a.id}: scenarios/hall_a/out/{a.reuse} is missing (WS2 renders it)")
        return InboxAttachment(id=a.id, name=a.name, url=f"/demo/docs/{a.reuse}", source=f"hall_a/out/{a.reuse}")
    if a.render == "letter":
        data = letter_pdf(a.title, a.lines)
    elif a.render == "scan":
        data = scan_pdf(a.title, a.lines, rng_for(cfg, f"inbox:{a.id}"))
    else:
        raise ValueError(f"{email_id}/{a.id}: render must be letter or scan")
    files[f"{INBOX_DIR}/{a.file}"] = data
    files[f"{INBOX_OUT_DIR}/{a.file}"] = data
    return InboxAttachment(id=a.id, name=a.name, url=f"/demo/inbox/{a.file}",
                           source=f"demo_world/out/inbox/{a.file}")


def build_inbox(cfg: WorldConfig, scenarios_root: Path, triage: dict[str, dict] | None = None) -> InboxBuild:
    if cfg.inbox is None:
        raise ValueError("world.yaml has no inbox section")
    scenarios_root = Path(scenarios_root)
    triage = dict(triage or {})
    ids = [e.id for e in cfg.inbox.emails]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate email ids: {sorted({i for i in ids if ids.count(i) > 1})}")
    unknown = sorted(set(triage) - set(ids))
    if unknown:
        raise ValueError(f"triage for unknown emails: {unknown}")
    files: dict[str, bytes] = {}
    emails = []
    for e in cfg.inbox.emails:
        result = triage.get(e.id)
        if result is not None and result.get("email_id") != e.id:
            raise ValueError(f"triage for {e.id} carries email_id {result.get('email_id')!r}")
        emails.append(InboxEmail(
            id=e.id, from_name=e.from_name, from_addr=e.from_addr, from_org=e.from_org, to=cfg.inbox.mailbox,
            subject=e.subject, received_at=cfg.ts(e.days_ago), body=e.body.rstrip("\n"),
            attachments=[_attachment(cfg, e.id, a, scenarios_root, files) for a in e.attachments],
            project_id=e.project_id, live_triage=e.live_triage, triage=result))
    emails.sort(key=lambda m: (-m.received_at, m.id))
    seed = InboxSeed(mailbox=cfg.inbox.mailbox, as_of=cfg.now, appetite=cfg.inbox.appetite, emails=emails)
    data = (seed.model_dump_json(indent=2) + "\n").encode("utf-8")
    files[INBOX_JSON] = data  # static bundle (Hosting)
    files[INBOX_SEED] = data  # API image fallback + Firestore seed source
    return InboxBuild(seed=seed, files=files)


def load_triage_capture(path: Path) -> dict[str, dict]:
    """{email_id: TriageResult JSON} from WS2's precompute capture, or {} if it has not been captured yet."""
    path = Path(path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != CAPTURE_VERSION:
        raise ValueError(f"{path}: expected version {CAPTURE_VERSION}, got {data.get('version')!r}")
    return dict(data["results"])


def write_inbox(build: InboxBuild, root: Path) -> list[str]:
    root = Path(root)
    for d in MANAGED_DIRS:
        folder = root / d
        if folder.is_dir():
            for f in sorted(folder.iterdir()):
                if f.is_file() and f.relative_to(root).as_posix() not in build.files:
                    f.unlink()
    for rel, data in sorted(build.files.items()):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return sorted(build.files)


def inbox_diff_on_disk(build: InboxBuild, root: Path) -> list[str]:
    root = Path(root)
    stale = [rel for rel, data in sorted(build.files.items())
             if not (root / rel).exists() or (root / rel).read_bytes() != data]
    extra = [f.relative_to(root).as_posix() for d in MANAGED_DIRS if (root / d).is_dir()
             for f in sorted((root / d).iterdir()) if f.is_file() and f.relative_to(root).as_posix() not in build.files]
    return stale + extra


def inbox_seed_path() -> Path:
    return scenarios_dir() / "demo_world" / "out" / "inbox_seed.json"


def load_inbox_seed(path: Path | str) -> InboxSeed:
    return InboxSeed.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_inbox(store: Store, seed: InboxSeed) -> int:
    """Seed loader: seed/inbox (meta) and seed/inbox/emails/{id}, replacing whatever was there. API read-only."""
    meta = seed.model_dump(mode="json", exclude={"emails"})
    items = [(f"{SEED_EMAILS}/{e.id}", e.model_dump(mode="json")) for e in seed.emails]
    problems = [f"{path}: {p}" for path, doc in [(SEED_DOC, meta), *items] for p in firestore_safe_problems(doc)]
    if problems:
        raise ValueError("inbox seed is not Firestore-safe: " + "; ".join(problems[:5]))
    store.delete_tree(SEED_DOC)
    store.set_doc(SEED_DOC, meta)
    store.batch_set(items)
    return len(items)
