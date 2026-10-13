/* GENERATED from services/api/kirchhoff/contracts — do not edit */

export type Id = string;
export type Name = string;
export type Client = string;
export type AssetPack = "datahall" | "grid" | "solar";
export type State = "not_started" | "running" | "in_review" | "checked" | "draft" | "signed" | "archived";
export type Sample = boolean;
export type UpdatedAt = number;
export type ProjectId = string;
export type Id1 = string;
export type Text = string;
export type Value = number | string | null;
export type Unit = string | null;
export type DocId = string;
export type Page = number;
export type Quote = string;
export type Bbox = [unknown, unknown, unknown, unknown] | null;
export type Clause = string | null;
export type Verified = boolean;
export type Requirements = Requirement[];
export type Id2 = string;
export type Text1 = string;
export type Options = string[];
export type Citations = Citation[];
export type DefaultResolution = string;
export type Resolution = string | null;
export type OpenQuestions = OpenQuestion[];
export type Id3 = string;
export type ProjectId1 = string;
export type Status = "running" | "at_gate" | "done" | "expired" | "failed";
export type Autonomy = "ask" | "auto";
export type Phase = ("p1" | "p2" | "p3" | "p4") | null;
export type Gate = ("plan" | "option" | "review") | null;
export type Id4 = string;
export type Agent =
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
export type Title = string;
export type Note = string;
export type Plan = PlanStep[];
export type OpenQuestions1 = OpenQuestion[];
export type Id5 = "2N" | "DR" | "BLOCK";
export type InstalledMva = number;
export type NormalLoadingPct = number;
export type FailoverLoadingPct = number;
export type Cost = number;
export type LossesKw = number;
export type MaxLeadTimeWeeks = number;
export type SpofCount = number;
export type Swaps = {
  [k: string]: unknown;
}[];
export type Options1 = TopologyOption[];
export type SelectedOption = ("2N" | "DR" | "BLOCK") | null;
export type Lease = {
  [k: string]: unknown;
} | null;
export type StartedAt = number;
export type FinishedAt = number | null;
export type Runs = RunRecord[];
export type Id6 = string;
export type Phase1 = "p1" | "p2" | "p3" | "p4";
export type Status1 = "running" | "done" | "failed";
export type Attempt = number;
export type OutputsRef = string | null;
export type StartedAt1 = number;
export type FinishedAt1 = number | null;
export type Steps = StepRecord[];
export type Seq = number;
export type Phase2 = "p1" | "p2" | "p3" | "p4";
export type Step = string;
export type Attempt1 = number;
export type Agent1 =
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
export type Kind =
  "plan" | "tool_call" | "tool_result" | "message" | "artifact" | "finding" | "gate" | "ledger" | "status";
export type Title1 = string;
export type Detail = string;
export type Ts = number;
export type Events = RunEvent[];
export type Id7 = string;
export type ProjectId2 = string;
export type Parent = string | null;
export type Author = string;
export type Hash = string;
export type Topology = "2N" | "DR" | "BLOCK";
export type Id8 = string;
export type Row = string;
export type X = number;
export type Y = number;
export type W = number;
export type D = number;
export type Kw = number;
export type LiquidFraction = number;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Feeds = [unknown, unknown];
export type Racks = Rack[];
export type Id9 = string;
export type Kind1 =
  "mv_board" | "transformer" | "lv_board" | "ups" | "critical_board" | "sts" | "busway" | "rack_group";
export type Rating = number | null;
export type Unit1 = string | null;
export type CatalogueId = string | null;
export type System = string | null;
export type Room = string | null;
export type Equipment = Equipment1[];
export type Id10 = string;
export type Src = string;
export type Dst = string;
export type Kind2 = "cable" | "busway" | "internal";
export type LengthM = number;
export type CatalogueId1 = string | null;
export type X1 = number;
export type Y1 = number;
export type Z = number;
export type Route = Point3[];
export type Connections = Connection[];
export type Id11 = string;
export type Kind3 = "cdu" | "manifold";
export type Zone = string;
export type CapacityKw = number | null;
export type X2 = number;
export type Y2 = number;
export type CoolingNodes = CoolingNode[];
export type Id12 = string;
export type Kind4 = "header" | "branch";
export type Zone1 = string;
export type Dn = number;
export type Tier = "pipe_low" | "pipe_high";
export type Route1 = Point3[];
export type FlowLps = number;
export type Pipes = Pipe[];
/**
 * @minItems 2
 * @maxItems 2
 */
export type Hall = [unknown, unknown];
export type Columns = [unknown, unknown][];
export type Keepouts = [unknown, unknown, unknown, unknown][];
export type ModelUrl = string | null;
export type Summary = string;
export type Status2 = "draft" | "checked" | "signed";
export type Kind5 = "did" | "assumed" | "not_checked";
export type Agent2 =
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
export type Text2 = string;
export type Ledger = LedgerEntry[];
export type CreatedAt = number;
export type Revisions = Revision[];
export type Id13 = string;
export type RuleId = string;
export type ElementId = string;
export type Status3 = "pass" | "fail" | "warn" | "n/a";
export type Title2 = string;
export type Standard = string;
export type Clause1 = string | null;
export type ClauseRefs = ClauseRef[];
export type TenderRefs = Citation[];
export type Formula = string;
export type Value1 = number | null;
export type Limit = number | null;
export type Unit2 = string | null;
export type Explanation = string;
export type Fix = {
  [k: string]: unknown;
} | null;
export type RejectedFix = {
  [k: string]: unknown;
} | null;
export type Id14 = string;
export type Revision1 = string;
export type ApproverName = string;
export type Role = string;
export type Decision = "approved" | "rejected";
export type Comment = string;
export type Ts1 = number;
export type Approvals = Approval[];
export type Id15 = string;
export type ProjectId3 = string;
export type Revision2 = string;
export type MaterialId = string;
export type Description = string;
export type Qty = number;
export type UnitPrice = number;
export type LeadTimeWeeks = number;
export type Lines = PRLine[];
export type Status4 = "draft" | "submitted" | "blocked";
export type CreatedAt1 = number;
export type Prs = PurchaseRequisition[];
export type OpportunityId = string;
export type Stage = string;
export type UpdatedAt1 = number;
export type RevisionRef = string;
export type Param = "rack_kw" | "liquid_fraction" | "dv_limit_pct" | "tx_loading_cap_pct";
export type Value2 = number;
export type Findings1 = Finding[];
export type ImpactChain = string[][];
export type WhatIfs = WhatIfResult[];
export type Id16 = string;
export type Category = string;
export type Description1 = string;
export type Rating1 = number | null;
export type Unit3 = string | null;
export type Voltage = string | null;
export type Stock = number;
export type LeadTimeWeeks1 = number;
export type UnitPrice1 = number;
export type Vendor = string;
export type Id17 = string;
export type Account = string;
export type Name1 = string;
export type Stage1 = string;
export type Value3 = number;
export type NextStep = string;

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
  runs?: Runs;
  steps?: Steps;
  events?: Events;
  revisions?: Revisions;
  findings?: Findings;
  approvals?: Approvals;
  prs?: Prs;
  crm?: CrmOverlay | null;
  what_ifs?: WhatIfs;
}
export interface Project {
  id: Id;
  name: Name;
  client: Client;
  asset_pack: AssetPack;
  state: State;
  sample: Sample;
  updated_at: UpdatedAt;
}
export interface DesignBrief {
  project_id: ProjectId;
  requirements: Requirements;
  open_questions?: OpenQuestions;
  intake_score?: IntakeScore;
  drawing_check?: DrawingCheck;
}
export interface Requirement {
  id: Id1;
  text: Text;
  value?: Value;
  unit?: Unit;
  citation: Citation;
  verified: Verified;
}
export interface Citation {
  doc_id: DocId;
  page: Page;
  quote: Quote;
  bbox?: Bbox;
  clause?: Clause;
}
export interface OpenQuestion {
  id: Id2;
  text: Text1;
  options: Options;
  citations: Citations;
  default_resolution: DefaultResolution;
  resolution?: Resolution;
}
export interface IntakeScore {
  [k: string]: number;
}
export interface DrawingCheck {
  [k: string]: unknown;
}
export interface RunRecord {
  id: Id3;
  project_id: ProjectId1;
  status: Status;
  autonomy: Autonomy;
  phase?: Phase;
  gate?: Gate;
  plan?: Plan;
  open_questions?: OpenQuestions1;
  options?: Options1;
  selected_option?: SelectedOption;
  metrics?: Metrics;
  lease?: Lease;
  started_at: StartedAt;
  finished_at?: FinishedAt;
}
export interface PlanStep {
  id: Id4;
  agent: Agent;
  title: Title;
  note?: Note;
}
export interface TopologyOption {
  id: Id5;
  installed_mva: InstalledMva;
  normal_loading_pct: NormalLoadingPct;
  failover_loading_pct: FailoverLoadingPct;
  cost: Cost;
  losses_kw: LossesKw;
  max_lead_time_weeks: MaxLeadTimeWeeks;
  spof_count: SpofCount;
  swaps?: Swaps;
}
export interface Metrics {
  [k: string]: number;
}
export interface StepRecord {
  id: Id6;
  phase: Phase1;
  status: Status1;
  attempt: Attempt;
  outputs_ref?: OutputsRef;
  started_at: StartedAt1;
  finished_at?: FinishedAt1;
}
export interface RunEvent {
  seq: Seq;
  phase: Phase2;
  step: Step;
  attempt?: Attempt1;
  agent: Agent1;
  kind: Kind;
  title: Title1;
  detail?: Detail;
  payload?: Payload;
  ts: Ts;
}
export interface Payload {
  [k: string]: unknown;
}
export interface Revision {
  id: Id7;
  project_id: ProjectId2;
  parent?: Parent;
  author: Author;
  hash: Hash;
  model?: DesignModel | null;
  model_url?: ModelUrl;
  summary?: Summary;
  check_summary?: CheckSummary;
  status: Status2;
  ledger?: Ledger;
  created_at: CreatedAt;
}
export interface DesignModel {
  topology: Topology;
  racks: Racks;
  equipment: Equipment;
  connections: Connections;
  cooling_nodes: CoolingNodes;
  pipes: Pipes;
  geometry: Geometry;
  loads: Loads;
}
export interface Rack {
  id: Id8;
  row: Row;
  x: X;
  y: Y;
  w?: W;
  d?: D;
  kw: Kw;
  liquid_fraction: LiquidFraction;
  feeds: Feeds;
}
export interface Equipment1 {
  id: Id9;
  kind: Kind1;
  rating?: Rating;
  unit?: Unit1;
  catalogue_id?: CatalogueId;
  system?: System;
  room?: Room;
  params?: Params;
}
export interface Params {
  [k: string]: number | string;
}
export interface Connection {
  id: Id10;
  src: Src;
  dst: Dst;
  kind: Kind2;
  length_m?: LengthM;
  catalogue_id?: CatalogueId1;
  route?: Route;
}
export interface Point3 {
  x: X1;
  y: Y1;
  z: Z;
}
export interface CoolingNode {
  id: Id11;
  kind: Kind3;
  zone: Zone;
  capacity_kw?: CapacityKw;
  x: X2;
  y: Y2;
}
export interface Pipe {
  id: Id12;
  kind: Kind4;
  zone: Zone1;
  dn: Dn;
  tier: Tier;
  route: Route1;
  flow_lps?: FlowLps;
}
export interface Geometry {
  hall: Hall;
  columns: Columns;
  keepouts: Keepouts;
  rooms: Rooms;
  tiers: Tiers;
}
export interface Rooms {
  /**
   * @minItems 4
   * @maxItems 4
   */
  [k: string]: [unknown, unknown, unknown, unknown];
}
export interface Tiers {
  [k: string]: number;
}
export interface Loads {
  [k: string]: number;
}
export interface CheckSummary {
  [k: string]: number;
}
export interface LedgerEntry {
  kind: Kind5;
  agent: Agent2;
  text: Text2;
}
export interface Findings {
  [k: string]: Finding[];
}
export interface Finding {
  id: Id13;
  rule_id: RuleId;
  element_id: ElementId;
  status: Status3;
  title: Title2;
  clause_refs?: ClauseRefs;
  tender_refs?: TenderRefs;
  formula?: Formula;
  inputs?: Inputs;
  value?: Value1;
  limit?: Limit;
  unit?: Unit2;
  explanation?: Explanation;
  fix?: Fix;
  rejected_fix?: RejectedFix;
}
export interface ClauseRef {
  standard: Standard;
  clause?: Clause1;
}
export interface Inputs {
  [k: string]: number | string;
}
export interface Approval {
  id: Id14;
  revision: Revision1;
  approver_name: ApproverName;
  role: Role;
  decision: Decision;
  comment?: Comment;
  ts: Ts1;
}
export interface PurchaseRequisition {
  id: Id15;
  project_id: ProjectId3;
  revision: Revision2;
  lines: Lines;
  status: Status4;
  created_at: CreatedAt1;
}
export interface PRLine {
  material_id: MaterialId;
  description: Description;
  qty: Qty;
  unit_price: UnitPrice;
  lead_time_weeks: LeadTimeWeeks;
}
export interface CrmOverlay {
  opportunity_id: OpportunityId;
  stage: Stage;
  updated_at: UpdatedAt1;
}
export interface WhatIfResult {
  revision_ref: RevisionRef;
  param: Param;
  value: Value2;
  findings: Findings1;
  impact_chain: ImpactChain;
}
export interface Material {
  id: Id16;
  category: Category;
  description: Description1;
  rating?: Rating1;
  unit?: Unit3;
  voltage?: Voltage;
  stock: Stock;
  lead_time_weeks: LeadTimeWeeks1;
  unit_price: UnitPrice1;
  vendor: Vendor;
}
export interface Opportunity {
  id: Id17;
  account: Account;
  name: Name1;
  stage: Stage1;
  value: Value3;
  next_step?: NextStep;
}
