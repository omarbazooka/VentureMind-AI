# VentureMind AI — Current Progress

_Last updated: 2026-09-10_

This file is the authoritative implementation checkpoint. Older milestone notes must not override this file.

## Build Status

- **Day 1 — Foundation:** DONE
- **Day 2 — Persistence / State:** DONE
- **Day 3 — Chat Runtime Foundation:** DONE
- **Day 4 — Intake:** DONE
- **Day 5 — AnalysisRun + Research Foundation:** DONE
- **Day 6 — Files / RAG:** DEFERRED POST-MVP (ADR-028)
- **Day 7 — Business Strategy + Finance:** COMPLETED & VALIDATED
- **Day 8 — Decision Analytics + Risk:** COMPLETED & VALIDATED
- **Day 9 — Independent Validation + Final Decision:** IMPLEMENTED + QA HARDENED; POST-QA FULL REGRESSION STILL REQUIRED
- **Day 10 — Structured Report + Visualization Data:** IMPLEMENTED + QA HARDENED; FRONTEND BUILD/SMOKE STILL REQUIRED
- **Day 11 — Unified Grounded Chat / Report Actions:** IMPLEMENTED FOUNDATION; SAME CHAT WORKSPACE WIRED
- **Day 12 — Targeted Re-analysis + Compound Turns:** PARTIAL / NOT READY FOR DEMO
- **Day 13 — E2E Hardening:** IN PROGRESS — FRONTEND + DOCKER PRESENT; AUTH UI / FULL E2E / DEPLOY VALIDATION PENDING

---

## Job Fair Fast-Track Status

All urgent implementation work is isolated on `jobfair-demo`. `master` and the educational `learning/day-9` path must remain untouched until QA is complete.

### Implemented backend vertical slice

The current backend path is:

`Idea → Chat/Intake → versioned IdeaProfile → explicit Start Analysis → Market + Competitor + Customer → deterministic Research Join/Evidence Gate → Business Strategy → Finance → optional PAUSED_FOR_USER → Decision Analytics → Risk → Independent Validation → Investment Committee / Final Decision → Structured Report → grounded report actions / Chat follow-up`

Important runtime properties:
- Analysis starts only from an explicitly ready profile and explicit Start Analysis action.
- Research Evidence Gate remains a deterministic checkpoint, not a fake persisted stage.
- Finance authoritative arithmetic is deterministic Python.
- Decision Analytics authoritative KPI/scenario/sensitivity math is deterministic Python.
- Risk score/level is deterministic Python; LLM output is grounded before persistence.
- Independent Validation cannot authoritatively schedule retries through LLM output.
- Final Decision uses exact grounded upstream stage-run lineage.
- Structured Report is persisted authoritative structured data and reuses the exact Final Decision lineage.
- Report generation does not fabricate unsupported monthly projections, TAM/SAM/SOM, WTP, or other missing metrics.
- Report actions use persisted report facts and explicit unavailable states rather than helpful-sounding fallback claims.

### Pipeline execution / progress

Implemented:
- in-process FastAPI background execution for the Job Fair MVP;
- real `AnalysisStageRun` progress polling;
- real Finance `PAUSED_FOR_USER` input request / answer / resume;
- server-side resolution of predefined Finance option values;
- explicit failure propagation to `AnalysisRun`;
- report-ready state exposed from backend progress.

The initial three research stages are currently executed sequentially by the MVP `PipelineRunner`, even though the intended architecture permits parallel research execution. This is an optimization/runtime improvement, not a reason to add unsafe concurrency during the demo sprint.

### Authentication and ownership

Backend foundation implemented:
- Supabase JWT verification supports asymmetric JWKS verification and explicit HS256 fallback when configured;
- `pyjwt[crypto]` is an explicit backend dependency;
- client-supplied user IDs are never trusted as identity;
- dev auth bypass is disabled by default and restricted to development/test configuration;
- `ideas.owner_user_id` added through Alembic migration;
- ownership checks now cover Ideas, Chat, Profile, Analysis, progress, Finance input answers, Reports, report actions, re-analysis, and report comparison;
- legacy ownerless ideas remain accessible only as an intentional compatibility/demo path.

**Still pending:** the real frontend Supabase login/signup/session UI and token lifecycle. Backend auth support must not be described as complete end-user authentication until this frontend path exists and is tested.

### Frontend

A Next.js 14 + TypeScript frontend exists on `jobfair-demo` with:
- grounded landing page;
- dashboard / idea creation routes;
- Idea Workspace;
- same Chat AI before and after analysis;
- authoritative Idea Profile panel before analysis;
- Start Analysis enabled only when backend profile readiness is `READY_FOR_ANALYSIS`;
- backend-driven progress state with no timer-simulated stage completion;
- Finance pause/resume card using the real backend request contract;
- Structured Report tabs using the actual backend schema;
- deterministic Finance scenario metrics actually produced by the backend;
- persisted sensitivity/risk/validation/decision/source data;
- supported explicit report actions only.

QA removed frontend claims and fallbacks for unsupported NPV, IRR, five-year DCF, monthly burn, fake sensitivity rankings, fake competitor defaults, and unsupported report actions.

New-idea creation now routes the initial description through the normal Chat/Intake path so the user does not need to repeat the concept before IdeaProfile extraction begins.

### Docker / browser integration

Implemented:
- backend Dockerfile;
- frontend Dockerfile;
- PostgreSQL/backend/frontend `docker-compose.yml`;
- backend Alembic upgrade before serving for the single-instance Job Fair compose workflow;
- explicit environment-driven CORS configuration;
- browser origin `http://localhost:3000` supported by default for local compose;
- `NEXT_PUBLIC_*` variables passed at Next.js **build time**, not only container runtime.

**Still pending:** a fresh `docker compose up --build` smoke after the latest QA fixes.

---

## Day 9 — Independent Validation + Final Decision

**Status: IMPLEMENTED + QA HARDENED; FULL POST-QA REGRESSION PENDING**

Implemented:
- bounded Independent Validation context from the exact accepted analysis packet;
- structured validation findings/issues and limitations;
- deterministic grounding against profile fields, evidence IDs, Finance metrics, Analytics outputs, Risk references, and stage lineage;
- persistence-boundary revalidation to reject stale upstream state;
- exact upstream stage-run lineage in persisted Validation output;
- Investment Committee context with no new web research;
- structured Final Decision contract: GO / CONDITIONAL_GO / NO_GO / INSUFFICIENT_EVIDENCE;
- deterministic confidence/decision guardrails;
- concrete grounded Final Decision lineage references;
- persistence-boundary revalidation before Final Decision persistence;
- DAG progression from Risk → Independent Validation → Investment Committee.

Direct Day 9 Validation retry execution is intentionally not used as a shortcut. `affected_stages` can describe impact, while authoritative dependency invalidation belongs to the Day 12 deterministic resolver.

---

## Day 10 — Structured Report

**Status: IMPLEMENTED + QA HARDENED; FRONTEND/CONTAINER SMOKE PENDING**

Implemented:
- persisted versioned `Report` model and migration;
- authoritative `StructuredReport` Pydantic contract;
- sections for profile, market, competitors, customers, strategy, Finance, Analytics, Risk, Independent Validation, Final Decision, sources, and chart-ready data;
- explicit unavailable / insufficient-evidence market metric states;
- exact Final Decision stage-run lineage used to select every upstream report result;
- Finance/Analytics/Validation lineage consistency checks at report generation;
- idempotent report generation per AnalysisRun;
- chart-ready break-even, sensitivity, and risk data sourced from validated persisted results;
- no invented month-by-month ramp when Finance has no authoritative time series.

---

## Day 11 — Unified Grounded Chat / Report Actions

**Status: IMPLEMENTED FOUNDATION**

Implemented:
- same `/ideas/{idea_id}/messages` Chat AI remains visible before and after report generation;
- selective analysis context remains idea/run scoped;
- explicit report actions for Explain, Explain Simply, Show Evidence, Show Sources, Explain Calculation, Explain Chart, Challenge Conclusion, What Could Change, and Ask VentureMind;
- ordinary report actions do not silently launch unrestricted web research;
- report actions use persisted facts and explicitly say unavailable when required information is missing;
- frontend is wired to supported report actions through the actual backend request/response contract.

A richer bounded LLM phrasing layer for arbitrary report questions may be improved later, but it must remain grounded in the same persisted report/evidence packet.

---

## Day 12 — Targeted Re-analysis

**Status: PARTIAL / NOT READY FOR DEMO**

Implemented foundation:
- deterministic field/stage impact resolver draft;
- new AnalysisRun/profile version creation;
- old execution history is preserved;
- reuse/invalidated-stage lineage metadata is recorded;
- report comparison endpoint exists.

Known blocker:
- reused upstream result IDs are currently metadata only; the new AnalysisRun / existing `BusinessAnalysisFlow` and `PipelineRunner` do not yet consume those reused results as an authoritative executable dependency chain;
- therefore the implementation must **not** claim that only invalidated stages execute end-to-end yet;
- current Job Fair frontend intentionally does not expose targeted re-analysis as a working feature;
- profile-field impact mappings also need alignment with the authoritative `ProfileField` vocabulary before completion.

Compound-turn sophistication is not complete and is lower priority than a reliable Job Fair vertical slice.

---

## Day 13 — Job Fair E2E Hardening

**Status: IN PROGRESS**

Implemented:
- real backend-connected Next.js workspace;
- central typed frontend API client aligned with FastAPI contracts;
- browser CORS wiring;
- Dockerfiles and compose orchestration;
- real progress/pause/report interaction surfaces.

Remaining exit criteria:
1. implement real Supabase login/signup/logout/session flow in frontend;
2. run frontend `npm run build` after the latest QA fixes;
3. run the full backend pytest regression after the latest QA fixes;
4. run `docker compose up --build` and verify migrations/backend/frontend health;
5. execute one real HTTP E2E smoke: create idea → Chat/Intake → ready profile → Start Analysis → progress → optional Finance pause → Final Decision → report → report action;
6. deploy or document the exact deployment path if credentials are unavailable;
7. do not expose targeted re-analysis in the demo until its result-reuse execution path is complete.

Antigravity previously reported `486 passed / 0 failed` and a successful Next.js build before the latest QA fixes. GitHub currently has no CI status checks proving the post-QA state, so those numbers are historical external claims, not current verified regression evidence.

---

## Previously validated baseline

### Day 7
- Strategy → Finance lifecycle, Finance assumptions/grounding, deterministic scenarios, and pause/resume were validated.
- Recorded full Day 7 regression: **370 passed, 0 failed, 0 errors**.

### Day 8
Recorded validation evidence:
- Analytics focused batch: **19 passed, 0 failed, 0 errors**.
- Selective Chat analysis-context tests: **6 passed, 0 failed, 0 errors**.
- Finance → Decision Analytics → Risk integration: **2 passed, 0 failed, 0 errors**.
- Full `tests/integration/analysis` suite: **5 passed, 0 failed, 0 errors**.
- Final Risk focused/unit/full backend reruns were reported with **0 failed / 0 errors**, but the final aggregate count was not captured and is intentionally not invented.

---

## Important active rules

- Frozen `AnalysisRun.profile_snapshot` is never silently mutated by analysis-time answers.
- Messages are conversation history; `IdeaProfile` is authoritative structured idea state.
- User pause is for decision-critical BASE inputs, not arbitrary model uncertainty.
- Competitor pricing is not venture pricing or WTP proof.
- Selected Finance option values are resolved from persisted backend requests, not trusted client values.
- LLMs do not own authoritative Finance/Analytics arithmetic, risk scoring, permissions, or DAG scheduling.
- `INSUFFICIENT_EVIDENCE` is a valid result and must not be replaced with fabricated completeness.
- Report output is structured authoritative data, not merely presentation text.
- Missing report data must render as unavailable, not a plausible-looking fallback.
- Authenticated ownership is enforced server-side; frontend identity is never authoritative.
- Deterministic state/dependency/application code owns Analysis DAG progression.
- Files/RAG remain deferred post-MVP.
