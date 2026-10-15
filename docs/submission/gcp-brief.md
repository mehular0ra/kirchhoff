# How Kirchhoff uses Google Cloud

Kirchhoff, by team Ordinal: Gemini agents design power and liquid cooling for an AI data hall, a deterministic checker verifies every number, and an engineer signs. Live at https://kirchhoff.web.app. (spec) marks a design-spec number.

## Gemini on Vertex AI

**In Kirchhoff.** Gemini 3.8 Flash on Vertex AI (global) runs every agent as a Google ADK 2.x agent (LlmAgent with function tools). Intake reads the tender and flags contradictions, Power and Cooling choose between engine-verified fixes with reasons, and Co-pilot answers by text or voice.

**Why.** Native PDF input, structured output and function calling in one GA model; ADK puts LLM nodes and deterministic tools in one auditable graph.

**Detail.** Every agent returns schema-validated structured output, with one repair attempt. A requirement counts only if pdfplumber finds Gemini's verbatim quote on the cited page. We chose this over File Search because we need the exact page and box. A digit-sanitising trust layer filters every LLM sentence in the UI: digits may appear only in engine-filled placeholders or allowlisted ids (FA-01, R11, §4.6), and any other digit swaps the sentence for a template. Voice uses the Gemini Live native-audio model in us-central1 through Firebase AI Logic. Its tools call our API, its on-screen transcript passes the same filter, and the design calls for push-to-talk on `gemini-3.8-flash` as the fallback if a Live session won't open.

## Cloud Run

**In Kirchhoff.** One Cloud Build image runs as two services. `kirchhoff-api` (public, behind Firebase Hosting) runs FastAPI, the agents and the engine; `kirchhoff-enterprise` (private) is the ERP and CRM sandbox.

**Why.** The engine needs native scientific Python (pandapower for IEC 60909 short circuit, shapely, ezdxf), and runs execute as long background phases. A container we control fits both better than a managed agent runtime.

**Detail.** Hosting rewrites time out at 60 s, so each run phase starts with a POST that takes a Firestore lease, starts a worker and returns 202. The worker heartbeats every 15 s (spec). If the lease goes 60 s without a heartbeat (spec), resume takes it with a higher attempt number, skips finished steps and re-runs the rest. Both services run as a dedicated least-privilege service account; the API reaches the private sandbox with a Google ID token.

## Firestore

**In Kirchhoff.** Firestore holds run state, leases, the live event stream, revisions, findings, approvals and the sandbox seed: 60 ERP materials, 9 CRM opportunities and 3 historical PRs, all fictional.

**Why.** Real-time listeners give us a streaming agent UI, an audit trail and per-visitor workspaces with no socket server.

**Detail.** Events are batched about every 250 ms (spec) and tagged `{step, attempt}`. A step commits its outputs and a `done` marker in a transaction that checks `lease.attempt` first, so a stale worker can never commit. Visibility is fenced by attempt, so a resumed run never shows orphaned narration. Clients read only their own `workspaces/{uid}/**` and never write; every mutation goes through the API.

## Firebase

**In Kirchhoff.** Hosting serves the React app and a static demo world. Anonymous Auth gives every judge a private workspace with no login. App Check attests requests, and AI Logic connects the browser to Gemini Live.

**Why.** Static-first browsing survives a backend outage during judging, and anonymous sign-in removes the sign-up step.

**Detail.** The API verifies the Firebase ID token, the App Check token and workspace ownership on every call except `/api/health`. App Check (reCAPTCHA Enterprise) was on from day one: enforcement for Firebase AI Logic becomes mandatory on 2 Nov 2026, mid-judging.

## Also

Cloud Storage holds tenders, drawings and exports, served through signed URLs.
