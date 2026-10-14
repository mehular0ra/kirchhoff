"""Pydantic mirror of P3's `World` / `IntegrationsSnapshot` TypeScript types
(apps/web/src/lib/types.ts on ws3-web, read verbatim 2026-10-14). `extra="forbid"` on every mirror model makes any
field drift between the TS source of truth and WS4's generator fail loudly here, instead of silently in the browser.

Mirrored shapes (ws3-web apps/web/src/lib/types.ts):
    export interface WorldPerson { id: string; name: string; role: string; initials?: string }
    export interface WorldActivity { id: string; ts: number; actor: string; project_id?: string | null; text: string }
    export interface World { org: { name: string; tagline?: string }; people: WorldPerson[]; projects: Project[];
                              activity: WorldActivity[] }
    export interface DocumentRecord { id: string; project_id: string; name: string; kind: string; url: string;
                                       updated_at: number }
    export interface NotificationRecord { id: string; ts: number; kind: string; title: string; body?: string;
                                           project_id?: string | null }
    export interface IntegrationsSnapshot { synced_at?: number; erp: { materials: Material[]; prs: PurchaseRequisition[] };
                                             crm: { opportunities: Opportunity[] }; documents: DocumentRecord[];
                                             notifications: NotificationRecord[] }

No field was adapted: WS4's `build_world` output validates against this mirror unchanged.
"""
from pydantic import BaseModel, ConfigDict

from kirchhoff.contracts import Material, Opportunity, Project, PurchaseRequisition
from kirchhoff.enterprise.world.build import DEMO, build_world


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorldPersonTS(_M):
    id: str
    name: str
    role: str
    initials: str | None = None


class WorldActivityTS(_M):
    id: str
    ts: float
    actor: str
    project_id: str | None = None
    text: str


class WorldOrgTS(_M):
    name: str
    tagline: str | None = None


class WorldTS(_M):
    org: WorldOrgTS
    people: list[WorldPersonTS]
    projects: list[Project]
    activity: list[WorldActivityTS]


class DocumentRecordTS(_M):
    id: str
    project_id: str
    name: str
    kind: str
    url: str
    updated_at: float


class NotificationRecordTS(_M):
    id: str
    ts: float
    kind: str
    title: str
    body: str | None = None
    project_id: str | None = None


class ErpSnapshotTS(_M):
    materials: list[Material]
    prs: list[PurchaseRequisition]


class CrmSnapshotTS(_M):
    opportunities: list[Opportunity]


class IntegrationsSnapshotTS(_M):
    synced_at: float | None = None
    erp: ErpSnapshotTS
    crm: CrmSnapshotTS
    documents: list[DocumentRecordTS]
    notifications: list[NotificationRecordTS]


def test_world_json_validates_against_the_p3_world_mirror(world_cfg, scenarios_root):
    build = build_world(world_cfg, scenarios_root=scenarios_root)
    WorldTS.model_validate_json(build.files[f"{DEMO}/world.json"])


def test_integrations_json_validates_against_the_p3_integrations_mirror(world_cfg, scenarios_root):
    build = build_world(world_cfg, scenarios_root=scenarios_root)
    IntegrationsSnapshotTS.model_validate_json(build.files[f"{DEMO}/integrations.json"])
