# VentureMind AI — Current Progress

_Last updated: 2026-09-09_

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
- **Day 9 — Validation + Final Decision:** NEXT
- **Day 10 — Structured Report + Visualization:** PENDING
- **Day 11 — Unified Grounded Chat Q&A:** PENDING
- **Day 12 — Changes + Targeted Re-analysis + Compound Turns:** PENDING
- **Day 13 — E2E Hardening:** PENDING

---

## Day 7 — Business Strategy + Finance

**Status: COMPLETED & VALIDATED**

### Business Strategy
- Research Join / Evidence Gate → Business Strategy scheduling.
- `StrategyStageClaim` and authoritative context loading.
- Business Strategy CrewAI runner and deterministic grounding.
- Strategy claim / complete / fail lifecycle.
- Strategy executor.
- Research → Strategy integration coverage.
- Completed Strategy + persisted `AnalysisResult` required before Finance scheduling.
- Idempotent Business Strategy → Finance scheduling through `BusinessAnalysisFlow.advance_strategy()`.

### Finance
- Structured Finance contracts with explicit provenance.
- Deterministic readiness evaluation.
- Authoritative deterministic financial calculator.
- Monthly / annual normalization.
- BASE / UPSIDE / DOWNSIDE deterministic scenario engine.
- Bounded Finance AI Assumption Builder through `LLMGateway`.
- Deterministic Finance grounding for USER / WEB / AI_ASSUMPTION provenance.
- `FinanceStageClaim` and authoritative context loading from frozen IdeaProfile + accepted Research + completed Strategy.
- Durable `AnalysisRunInput` support for analysis-time questions/answers.
- `PAUSED_FOR_USER` at AnalysisRun and Finance stage level.
- Choice-aware Finance questions with backend-grounded options plus custom / Other.
- Selected option values resolve from the persisted backend request; client values cannot override them.
- Answered Finance input resumes the AnalysisRun and returns Finance to `PENDING` for explicit re-claim.
- Competitor prices remain market modeling choices, never venture WTP truth.
- USER lineage can come from frozen IdeaProfile fields or answered `AnalysisRunInput` IDs.
- Analysis-time answers never mutate the frozen `AnalysisRun.profile_snapshot`.
- Finance executor coordinates claim → assumptions → grounding → answered inputs → readiness → pause when needed → deterministic scenarios → persistence.

### Day 7 validation
- Real PostgreSQL Strategy → Finance integration covers ready completion and pause/answer/re-claim.
- Final Day 7 backend regression previously validated at **370 passed, 0 failed, 0 errors**.

---

## Day 8 — Decision Analytics

**Status: COMPLETED & VALIDATED**

### Contracts and deterministic analytics
- Added `DECISION_ANALYTICS` as an explicit `AnalysisStage`.
- Added `DecisionAnalyticsResult` contracts for:
  - decision KPIs;
  - scenario-relative changes;
  - deterministic sensitivity results;
  - exact Finance stage lineage;
  - explicit limitations.
- Reused authoritative Finance enums and outputs rather than duplicating Finance truth.
- Added deterministic KPI derivation for:
  - operating margin percent;
  - break-even headroom percent.
- Added deterministic BASE / UPSIDE / DOWNSIDE relative comparisons.
- Relative-change math uses absolute BASE magnitude so negative baselines remain directionally meaningful.
- Zero denominators produce unavailable percentages plus explicit limitations rather than fabricated math.
- Added BASE-centered one-at-a-time sensitivity for:
  - selling price per unit;
  - sales volume;
  - variable cost per unit;
  - fixed costs.
- Sensitivity reuses the authoritative Finance calculator after controlled `±shock%` perturbation.
- Sensitivity evaluates available impact on revenue, operating result, break-even units, and contribution margin percent.
- Inputs are ranked deterministically by operating-result sensitivity when defined.
- Added deterministic Analytics result assembly with bounded/de-duplicated limitations.

### Runtime and scheduling
- Added Analytics claim / complete / fail lifecycle.
- Added deterministic Analytics executor.
- Added strict Finance-stage lineage validation before Analytics persistence.
- Added `BusinessAnalysisFlow.advance_finance()`:
  - requires AnalysisRun = RUNNING;
  - requires Finance = COMPLETED;
  - requires a persisted Finance `AnalysisResult`;
  - reuses an existing Decision Analytics stage idempotently;
  - otherwise creates `DECISION_ANALYTICS`, attempt 1, `PENDING`.

---

## Day 8 — Risk

**Status: COMPLETED & VALIDATED**

### Structured Risk contracts
- Added `RISK` as an explicit `AnalysisStage`.
- Added structured Risk contracts covering:
  - category;
  - likelihood;
  - impact;
  - confidence;
  - rationale;
  - mitigation actions;
  - monitoring signals;
  - profile/research/Finance/Analytics lineage;
  - deterministic risk score;
  - deterministic risk level;
  - aggregate overall risk level.
- Risk score and final risk level are authoritative deterministic Python calculations; the LLM does not calculate them.

### Bounded Risk context
`RiskAnalysisContext` is built from:
- frozen IdeaProfile snapshot;
- Research Evidence Gate;
- accepted Market / Competitor / Customer results;
- completed Business Strategy;
- exact completed Finance result;
- exact completed Decision Analytics result.

Risk context validates exact Finance → Decision Analytics lineage consistency.

### Risk AI reasoning
- Added single-agent Risk CrewAI runner over the existing `LLMGateway` adapter.
- Risk Crew uses no tools and performs no new web research.
- Risk Crew returns structured `RiskDraftAnalysis` only.
- The LLM handles qualitative risk reasoning; Python owns authoritative scoring, validation, lifecycle, and persistence rules.

### Deterministic Risk grounding
- Validates exact IdeaProfile fields.
- Validates research evidence IDs against the declared research stage.
- Validates Finance metrics against the actual Finance context.
- Validates Decision Analytics KPIs and sensitivity inputs against actual Analytics output.
- Rejects hallucinated lineage instead of persisting it.
- Preserves Research Evidence Gate `INSUFFICIENT_EVIDENCE` states in Risk limitations.
- Ordinary risks cannot use stage names alone as grounding; they require at least one concrete reference.
- Stage-only grounding is reserved for `EVIDENCE_QUALITY`, and only when the referenced research stage is actually marked insufficient by the Research Evidence Gate.
- No arbitrary evidence-quality → numeric-confidence cap was invented because the project does not define an authoritative mapping yet.

### Runtime and scheduling
- Added Risk claim / complete / fail lifecycle.
- Added guarded Risk executor:
  - builds bounded context before execution;
  - runs the Risk AI draft;
  - performs deterministic grounding/scoring;
  - revalidates grounding at the persistence boundary;
  - fails safely if upstream state becomes inconsistent.
- Added `BusinessAnalysisFlow.advance_analytics()`:
  - requires AnalysisRun = RUNNING;
  - requires Decision Analytics = COMPLETED;
  - requires a persisted Decision Analytics `AnalysisResult`;
  - reuses an existing Risk stage idempotently;
  - otherwise creates `RISK`, attempt 1, `PENDING`.

---

## Day 8 — Grounded Chat AI read access

**Status: IMPLEMENTED; FULL ANALYSIS/REPORT Q&A REMAINS DAY 11**

Added `app/chat/analysis_context.py`:
- provides explicit read-only access to persisted `DECISION_ANALYTICS` and `RISK` results;
- requires both `idea_id` and `analysis_run_id`;
- rejects cross-idea AnalysisRun access;
- loads only explicitly requested stages;
- validates persisted JSON through authoritative Pydantic contracts before returning it;
- returns unavailable stages as `None` instead of fabricating data;
- is not injected into unrelated general chat turns.

Day 11 will wire this selective capability into report/analysis Q&A intents.

---

## Day 8 — Integration and validation

### Real PostgreSQL integration
`tests/integration/analysis/test_finance_to_analytics_to_risk.py` covers:
1. completed Finance → Decision Analytics scheduling → deterministic Analytics execution → persisted Analytics result → Risk scheduling → bounded Risk context → deterministic grounding/scoring → persisted Risk result → RISK COMPLETED;
2. hallucinated Risk profile lineage → `INVALID_RISK_GROUNDING` → RISK FAILED → no Risk `AnalysisResult` persisted.

### Test hardening completed during validation
- Replaced invalid `FinancialScenarioBundle` test placeholders with scenario-shaped dummy results.
- Replaced incomplete Research Evidence Gate fixtures with valid gate objects where runtime validation is under test.
- Replaced incomplete sensitivity fixtures with valid decrease/increase `SensitivityPoint` objects.
- Kept Crew wiring tests isolated from unrelated context validation when appropriate.
- Renamed colliding Pytest module basenames on Windows, including the Analytics calculator test and duplicate Risk test names.
- No production behavior was weakened to make tests pass.

### Recorded validation evidence
The following results were explicitly observed during Day 8 validation:
- Analytics focused batch: **19 passed, 0 failed, 0 errors**.
- Selective Chat analysis-context tests: **6 passed, 0 failed, 0 errors**.
- Finance → Decision Analytics → Risk integration: **2 passed, 0 failed, 0 errors**.
- Full `tests/integration/analysis` suite: **5 passed, 0 failed, 0 errors**.
- Final Risk focused batch, full unit suite, and full backend regression were re-run after fixture/module-name fixes and confirmed by the user as passing with **0 failed / 0 errors**.
- Exact aggregate pass counts for the final unit/full-suite runs were not captured in the chat, so they are intentionally not invented here.

**Day 8 exit criteria are satisfied.**

---

## Next milestone

### Day 9 — Validation + Final Decision

**Status: NEXT**

Planned scope:
- Independent Validation;
- bounded targeted correction/retry where justified;
- Investment Committee;
- final decision guardrail;
- grounded explanation of decision, rationale, confidence, limitations, and what could change the conclusion.

---

## Important active rules
- Frozen `AnalysisRun.profile_snapshot` is never silently mutated by analysis-time answers.
- Messages remain conversation history, not authoritative structured state.
- User pause is for decision-critical BASE inputs that cannot safely be resolved from authoritative state/research; it is not a fallback for arbitrary model uncertainty.
- Competitor pricing is not venture pricing or willingness-to-pay proof.
- Selected option values are resolved from persisted backend requests, not trusted client values.
- LLMs never own authoritative Finance or Decision Analytics arithmetic.
- Risk AI never owns authoritative risk score or final risk level.
- Risk stage names alone are not sufficient grounding for ordinary risk claims.
- `INSUFFICIENT_EVIDENCE` remains a valid downstream state and must not trigger fabricated numbers.
- Chat analysis context is loaded selectively; unrelated general chat does not automatically receive Analytics/Risk outputs.
- Deterministic state/dependency/application code owns Analysis DAG progression; CrewAI does not own normal chat turns or stage scheduling.
