/* GENERATED from services/api/kirchhoff/contracts — do not edit */

export interface KirchhoffContracts {
  ProjectBundle?: ProjectBundle;
  RunEvent?: RunEvent;
  TopologyOption?: TopologyOption;
  WhatIfResult?: WhatIfResult;
  PurchaseRequisition?: PurchaseRequisition;
  Material?: Material;
  Opportunity?: Opportunity;
  [k: string]: unknown;
}
export interface ProjectBundle {
  project: Project;
  brief?: DesignBrief | null;
  runs?: RunRecord[];
  steps?: StepRecord[];
  events?: RunEvent[];
  revisions?: Revision[];
  findings?: {
    [k: string]: Finding[];
  };
  approvals?: Approval[];
  prs?: PurchaseRequisition[];
  crm?: CrmOverlay | null;
  what_ifs?: WhatIfResult[];
}
export interface Project {
  id: string;
  name: string;
  client: string;
  asset_pack: "datahall" | "grid" | "solar";
  state: "not_started" | "running" | "in_review" | "checked" | "draft" | "signed" | "archived";
  sample: boolean;
  updated_at: number;
}
export interface DesignBrief {
  project_id: string;
  requirements: Requirement[];
  open_questions?: OpenQuestion[];
  intake_score?: {
    [k: string]: number;
  };
  drawing_check?: {
    [k: string]: unknown;
  };
}
export interface Requirement {
  id: string;
  text: string;
  value?: number | string | null;
  unit?: string | null;
  citation: Citation;
  verified: boolean;
}
export interface Citation {
  doc_id: string;
  page: number;
  quote: string;
  bbox?: [number, number, number, number] | null;
  clause?: string | null;
}
export interface OpenQuestion {
  id: string;
  text: string;
  options: string[];
  citations: Citation[];
  default_resolution: string;
  resolution?: string | null;
}
export interface RunRecord {
  id: string;
  project_id: string;
  status: "running" | "at_gate" | "done" | "expired" | "failed";
  autonomy: "ask" | "auto";
  phase?: ("p1" | "p2" | "p3" | "p4") | null;
  gate?: ("plan" | "option" | "review") | null;
  plan?: PlanStep[];
  open_questions?: OpenQuestion[];
  options?: TopologyOption[];
  selected_option?: ("2N" | "DR" | "BLOCK") | null;
  metrics?: {
    [k: string]: number;
  };
  lease?: {
    [k: string]: unknown;
  } | null;
  started_at: number;
  finished_at?: number | null;
}
export interface PlanStep {
  id: string;
  agent:
    | "intake"
    | "orchestrator"
    | "layout"
    | "power"
    | "cooling"
    | "procurement"
    | "checker"
    | "docs"
    | "copilot"
    | "asset"
    | "system";
  title: string;
  note?: string;
}
export interface TopologyOption {
  id: "2N" | "DR" | "BLOCK";
  installed_mva: number;
  normal_loading_pct: number;
  failover_loading_pct: number;
  cost: number;
  losses_kw: number;
  max_lead_time_weeks: number;
  spof_count: number;
  swaps?: {
    [k: string]: unknown;
  }[];
}
export interface StepRecord {
  id: string;
  phase: "p1" | "p2" | "p3" | "p4";
  status: "running" | "done" | "failed";
  attempt: number;
  outputs_ref?: string | null;
  started_at: number;
  finished_at?: number | null;
}
export interface RunEvent {
  seq: number;
  phase: "p1" | "p2" | "p3" | "p4";
  step: string;
  attempt?: number;
  agent:
    | "intake"
    | "orchestrator"
    | "layout"
    | "power"
    | "cooling"
    | "procurement"
    | "checker"
    | "docs"
    | "copilot"
    | "asset"
    | "system";
  kind: "plan" | "tool_call" | "tool_result" | "message" | "artifact" | "finding" | "gate" | "ledger" | "status";
  title: string;
  detail?: string;
  payload?: {
    [k: string]: unknown;
  };
  ts: number;
}
export interface Revision {
  id: string;
  project_id: string;
  parent?: string | null;
  author: string;
  hash: string;
  model?: DesignModel | null;
  model_url?: string | null;
  summary?: string;
  check_summary?: {
    [k: string]: number;
  };
  status: "draft" | "checked" | "signed";
  ledger?: LedgerEntry[];
  created_at: number;
}
export interface DesignModel {
  topology: "2N" | "DR" | "BLOCK";
  racks: Rack[];
  equipment: Equipment[];
  connections: Connection[];
  cooling_nodes: CoolingNode[];
  pipes: Pipe[];
  geometry: Geometry;
  loads: {
    [k: string]: number;
  };
}
export interface Rack {
  id: string;
  row: string;
  x: number;
  y: number;
  w?: number;
  d?: number;
  kw: number;
  liquid_fraction: number;
  /**
   * @minItems 2
   * @maxItems 2
   */
  feeds: [string, string];
}
export interface Equipment {
  id: string;
  kind: "mv_board" | "transformer" | "lv_board" | "ups" | "critical_board" | "sts" | "busway" | "rack_group";
  rating?: number | null;
  unit?: string | null;
  catalogue_id?: string | null;
  system?: string | null;
  room?: string | null;
  params?: {
    [k: string]: number | string;
  };
}
export interface Connection {
  id: string;
  src: string;
  dst: string;
  kind: "cable" | "busway" | "internal";
  length_m?: number;
  catalogue_id?: string | null;
  route?: Point3[];
}
export interface Point3 {
  x: number;
  y: number;
  z: number;
}
export interface CoolingNode {
  id: string;
  kind: "cdu" | "manifold";
  zone: string;
  capacity_kw?: number | null;
  x: number;
  y: number;
}
export interface Pipe {
  id: string;
  kind: "header" | "branch";
  zone: string;
  dn: number;
  tier: "pipe_low" | "pipe_high";
  route: Point3[];
  flow_lps?: number;
}
export interface Geometry {
  /**
   * @minItems 2
   * @maxItems 2
   */
  hall: [number, number];
  columns: [number, number][];
  keepouts: [number, number, number, number][];
  rooms: {
    /**
     * @minItems 4
     * @maxItems 4
     */
    [k: string]: [number, number, number, number];
  };
  tiers: {
    [k: string]: number;
  };
}
export interface LedgerEntry {
  kind: "did" | "assumed" | "not_checked";
  agent:
    | "intake"
    | "orchestrator"
    | "layout"
    | "power"
    | "cooling"
    | "procurement"
    | "checker"
    | "docs"
    | "copilot"
    | "asset"
    | "system";
  text: string;
}
export interface Finding {
  id: string;
  rule_id: string;
  element_id: string;
  status: "pass" | "fail" | "warn" | "n/a";
  title: string;
  clause_refs?: ClauseRef[];
  tender_refs?: Citation[];
  formula?: string;
  inputs?: {
    [k: string]: number | string;
  };
  value?: number | null;
  limit?: number | null;
  unit?: string | null;
  explanation?: string;
  fix?: {
    [k: string]: unknown;
  } | null;
  rejected_fix?: {
    [k: string]: unknown;
  } | null;
}
export interface ClauseRef {
  standard: string;
  clause?: string | null;
}
export interface Approval {
  id: string;
  revision: string;
  approver_name: string;
  role: string;
  decision: "approved" | "rejected";
  comment?: string;
  ts: number;
}
export interface PurchaseRequisition {
  id: string;
  project_id: string;
  revision: string;
  lines: PRLine[];
  status: "draft" | "submitted" | "blocked";
  created_at: number;
}
export interface PRLine {
  material_id: string;
  description: string;
  qty: number;
  unit_price: number;
  lead_time_weeks: number;
}
export interface CrmOverlay {
  opportunity_id: string;
  stage: string;
  updated_at: number;
}
export interface WhatIfResult {
  revision_ref: string;
  param: "rack_kw" | "liquid_fraction" | "dv_limit_pct" | "tx_loading_cap_pct";
  value: number;
  findings: Finding[];
  impact_chain: string[][];
}
export interface Material {
  id: string;
  category: string;
  description: string;
  rating?: number | null;
  unit?: string | null;
  voltage?: string | null;
  stock: number;
  lead_time_weeks: number;
  unit_price: number;
  vendor: string;
}
export interface Opportunity {
  id: string;
  account: string;
  name: string;
  stage: string;
  value: number;
  next_step?: string;
}
