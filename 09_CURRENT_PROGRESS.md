# VentureMind AI — Current Progress

_Last updated: 2026-09-09_

This file is the current implementation checkpoint. Older milestone notes should not override this section.

## Build Status

- **Day 1 — Foundation:** DONE
- **Day 2 — Persistence / State:** DONE
- **Day 3 — Chat Runtime Foundation:** DONE
- **Day 4 — Intake:** DONE
- **Day 5 — AnalysisRun + Research Foundation:** DONE
- **Day 6 — Files / RAG:** DEFERRED POST-MVP (ADR-028)
- **Day 7 — Business Strategy + Finance:** COMPLETED & VALIDATED
- **Day 8 — Decision Analytics + Risk:** IMPLEMENTATION COMPLETE; FINAL VALIDATION PENDING
- **Day 9 — Validation + Final Decision:** PENDING
- **Day 10 — Structured Report + Visualization:** PENDING
- **Day 11 — Unified Grounded Chat Q&A:** PENDING
- **Day 12 — Changes + Targeted Re-analysis + Compound Turns:** PENDING
- **Day 13 — E2E Hardening:** PENDING

## Day 7 — Business Strategy

**Status: COMPLETED & VALIDATED**

Completed:
- Research Join / Evidence Gate → Business Strategy scheduling.
- `StrategyStageClaim` and authoritative context loading.
- Business Strategy runner and deterministic grounding.
- Strategy claim / complete / fail lifecycle.
- Strategy executor.
- Research → Strategy integration coverage.
- Completed Strategy + persisted `AnalysisResult` verification before Finance scheduling.
- Idempotent Business Strategy → Finance scheduling through `BusinessAnalysisFlow.advance_strategy()`.

## Day 7 — Finance

**Status: COMPLETED & VALIDATED**

### Completed Finance primitives
- Structured Finance contracts and explicit provenance.
- Deterministic readiness evaluation.
- Deterministic authoritative financial calculator.
- Monthly / annual period normalization.
- BASE / UPSIDE / DOWNSIDE deterministic scenario engine.
- Bounded Finance AI Assumption Builder through `LLMGateway`; no CrewAI workflow was added because the task is a single bounded structured generation.
- Deterministic Finance grounding for USER / WEB / AI_ASSUMPTION source boundaries.

### Completed Finance stage/runtime lifecycle
- `FinanceStageClaim` and authoritative context loading from frozen IdeaProfile snapshot, accepted Research Join state, and completed Business Strategy.
- Durable `AnalysisRunInput` persistence for analysis-time user questions and answers.
- `PAUSED_FOR_USER` support at both AnalysisRun and AnalysisStage level.
- Finance pause lifecycle with one active pending question at a time.
- Typed `FinanceInputRequest` and `FinanceUserInputAnswer` contracts.
- Choice-aware questions with backend-grounded options plus an always-available custom / Other path.
- Selected option answers resolve their numeric value from the persisted backend request; clients cannot override the selected option value.
- Custom answers are validated against requested currency / unit / period when those are already fixed.
- Answered Finance input resumes the parent AnalysisRun and returns the Finance stage to `PENDING`, so a worker must explicitly re-claim it before execution continues.
- Finance complete / fail lifecycle and persisted `AnalysisResult` support.

### Market-backed Finance options
Initial deterministic option generation is intentionally conservative:
- currently supports `SELLING_PRICE_PER_UNIT` only;
- uses accepted Competitor Intelligence only;
- ignores competitor evidence if that stage is marked insufficient;
- uses WEB evidence only;
- requires observed numerical pricing evidence;
- requires the evidence statement to match the Finance currency and unit basis;
- can expose lower observed benchmark, deterministic midpoint, and upper observed benchmark;
- competitor prices remain modeling choices, not venture selling-price facts;
- the user always retains a custom / Other option.

Other missing Finance inputs currently fall back to a direct user question unless a future deterministic evidence rule is explicitly implemented for them.

### Run-scoped USER provenance
`FinancialAssumption` supports USER lineage from either:
- frozen `IdeaProfile` fields; or
- answered `AnalysisRunInput` IDs.

Analysis-time answers do not mutate or masquerade as fields from the frozen IdeaProfile snapshot.

Answered run inputs are overlaid deterministically after AI draft grounding. A user-confirmed critical input is applied consistently to BASE, UPSIDE, and DOWNSIDE instead of allowing the model to invent scenario variations around that confirmed fact.

### Finance Executor
`execute_finance_stage()` coordinates:
1. claim Finance stage;
2. run bounded Finance assumption generation;
3. deterministic grounding;
4. load and ground answered analysis-time user inputs;
5. deterministic readiness evaluation;
6. if BASE has a decision-critical missing input, build a direct or market-option request and pause for the user;
7. if only secondary scenarios are incomplete, fail the modeling output rather than asking the user to fix an AI scenario-construction problem;
8. calculate BASE / UPSIDE / DOWNSIDE deterministically when ready;
9. persist the validated Finance `AnalysisResult` and complete the stage.

## Day 7 — Validated integration coverage

### Strategy → Finance scheduling
`BusinessAnalysisFlow.advance_strategy()`:
- requires AnalysisRun = RUNNING;
- requires a completed Business Strategy stage;
- requires its persisted Business Strategy `AnalysisResult`;
- reuses an existing initial Finance stage if present;
- otherwise creates `FINANCE`, attempt 1, `PENDING`.

A helper-scope/indentation bug found by the focused unit tests was fixed by moving `_require_completed_strategy_result()` and `_ensure_finance_stage_run()` inside `BusinessAnalysisFlow`.

### Real-DB Strategy → Finance integration
`tests/integration/analysis/test_strategy_to_finance.py` provides real PostgreSQL transaction-backed lifecycle coverage while faking only the LLM-facing Finance assumption runner.

It validates:
1. completed Strategy → Finance scheduling → claim → grounded assumptions → deterministic calculation → persisted Finance result → FINANCE COMPLETED;
2. missing selling price → Finance/AnalysisRun `PAUSED_FOR_USER` → `AnalysisRunInput(PENDING)` → custom user answer → `ANSWERED` → Finance `PENDING` + AnalysisRun `RUNNING` → re-claim → run-input USER overlay → deterministic calculation → FINANCE COMPLETED.

## Day 7 final validation

**Final backend regression: 370 passed, 0 failed, 0 errors.**

The full regression includes the focused Strategy → Finance scheduling coverage, real-DB Strategy → Finance integration, Finance pause/answer/re-claim behavior, and the existing backend unit/integration suite.

Day 7 exit criteria are satisfied.

---

## Day 8 — Decision Analytics

**Status: IMPLEMENTATION COMPLETE; FINAL VALIDATION PENDING**

Completed implementation:
- Added `DECISION_ANALYTICS` as an explicit `AnalysisStage`.
- Added strict `DecisionAnalyticsResult` contracts for:
  - decision KPIs;
  - scenario-relative changes;
  - deterministic sensitivity results;
  - Finance stage lineage;
  - explicit limitations.
- Reused Finance enums and authoritative calculated outputs instead of duplicating Finance truth.
- Added deterministic KPI derivation for:
  - operating margin percent;
  - break-even headroom percent.
- Added deterministic BASE / UPSIDE / DOWNSIDE relative comparisons.
- Relative-change math uses absolute BASE magnitude so movement around negative baselines remains directionally meaningful.
- Zero BASE denominators produce an unavailable relative percentage plus an explicit limitation rather than fabricated math.
- Added BASE-centered one-at-a-time sensitivity analysis for:
  - selling price per unit;
  - sales volume;
  - variable cost per unit;
  - fixed costs.
- Sensitivity reuses the authoritative Finance calculator after controlled `±shock%` input perturbation.
- Sensitivity currently evaluates impacts on available:
  - revenue;
  - operating result;
  - break-even units;
  - contribution margin percent.
- Inputs are ranked by deterministic operating-result sensitivity when the ranking percentage is defined.
- Added deterministic Analytics result assembly with bounded/de-duplicated limitations.
- Added Analytics stage claim / complete / fail lifecycle.
- Added deterministic Analytics executor.
- Added strict Finance-stage lineage validation before Analytics persistence.
- Added `BusinessAnalysisFlow.advance_finance()`:
  - requires AnalysisRun = RUNNING;
  - requires Finance = COMPLETED;
  - requires a persisted Finance `AnalysisResult`;
  - reuses an existing initial Decision Analytics stage idempotently;
  - otherwise creates `DECISION_ANALYTICS`, attempt 1, `PENDING`.

## Day 8 — Risk

**Status: IMPLEMENTATION COMPLETE; FINAL VALIDATION PENDING**

Completed implementation:
- Added `RISK` as an explicit `AnalysisStage`.
- Added structured Risk contracts covering:
  - risk category;
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
- Risk score and final level are authoritative deterministic Python calculations; the LLM does not calculate them.
- Added bounded `RiskAnalysisContext` from:
  - frozen IdeaProfile snapshot;
  - Research Evidence Gate;
  - accepted Market / Competitor / Customer results;
  - completed Business Strategy;
  - exact completed Finance result;
  - exact completed Decision Analytics result.
- Risk context validates Finance → Decision Analytics lineage consistency.
- Added a single-agent Risk CrewAI runner over the existing `LLMGateway` adapter.
- Risk Crew uses no tools and performs no new web research.
- Risk Crew returns structured `RiskDraftAnalysis` only.
- Added deterministic Risk grounding for:
  - exact IdeaProfile fields;
  - research evidence source IDs from declared research stages;
  - available Finance metrics;
  - available Decision Analytics KPIs;
  - available sensitivity inputs.
- Risk grounding rejects hallucinated lineage instead of persisting it.
- Research Evidence Gate `INSUFFICIENT_EVIDENCE` states are preserved in final Risk limitations.
- Hardened Risk grounding after audit:
  - ordinary risks cannot use stage names alone as grounding;
  - ordinary risks require at least one concrete reference;
  - stage-only grounding is reserved for `EVIDENCE_QUALITY`;
  - stage-only `EVIDENCE_QUALITY` claims are accepted only when the referenced research stage is actually marked insufficient by the Research Evidence Gate.
- No arbitrary numeric confidence cap was added because the project does not currently define an authoritative categorical-evidence-quality → numeric-confidence mapping.
- Added Risk stage claim / complete / fail lifecycle.
- Added guarded Risk executor:
  - builds bounded context before execution;
  - runs the AI draft;
  - performs deterministic grounding/scoring;
  - revalidates grounding at the persistence boundary;
  - fails safely if upstream state becomes inconsistent.
- Added `BusinessAnalysisFlow.advance_analytics()`:
  - requires AnalysisRun = RUNNING;
  - requires Decision Analytics = COMPLETED;
  - requires a persisted Decision Analytics `AnalysisResult`;
  - reuses an existing initial Risk stage idempotently;
  - otherwise creates `RISK`, attempt 1, `PENDING`.

## Day 8 — Grounded Chat AI read access

**Status: IMPLEMENTED AS A SELECTIVE READ CAPABILITY; FULL Q&A REMAINS DAY 11**

Added `app/chat/analysis_context.py`:
- provides explicit read-only access to persisted `DECISION_ANALYTICS` and `RISK` results;
- requires both `idea_id` and `analysis_run_id`;
- rejects cross-idea AnalysisRun access;
- loads only explicitly requested analysis stages;
- validates persisted result JSON through the authoritative Pydantic contracts before returning it;
- returns unavailable stages as `None` instead of fabricating data;
- is not injected into every normal chat turn.

This intentionally does **not** implement the Day 11 report/analysis Q&A intents yet. Day 11 will call this capability from the relevant handlers so unrelated general chat does not load unnecessary analysis context.

## Day 8 — Integration coverage

### Finance → Decision Analytics → Risk
`tests/integration/analysis/test_finance_to_analytics_to_risk.py` provides real PostgreSQL transaction-backed lifecycle coverage while faking only the Risk AI draft boundary.

It covers:
1. completed Finance → Decision Analytics scheduling → deterministic Analytics execution → persisted Analytics result → Risk scheduling → bounded Risk context → deterministic grounding/scoring → persisted Risk result → RISK COMPLETED;
2. a Risk draft with hallucinated profile lineage → `INVALID_RISK_GROUNDING` → RISK FAILED → no Risk `AnalysisResult` persisted.

Focused unit coverage also exists for:
- Analytics contracts;
- KPI derivation;
- scenario-relative comparisons;
- sensitivity;
- Analytics assembly;
- Analytics claim/executor;
- Finance → Analytics scheduling;
- Risk contracts;
- Risk context;
- Risk Crew/runtime;
- Risk grounding;
- Risk claim/executor;
- Analytics → Risk scheduling;
- selective Chat Analytics/Risk read access.

## Day 8 — Final validation checkpoint

**Final regression result has not yet been recorded.**

The code is pushed, but this environment cannot run the repository's local Python/PostgreSQL test runtime and the repository currently has no GitHub Actions status checks. Do not mark Day 8 `COMPLETED & VALIDATED` until the following commands pass locally with **0 failed / 0 errors**.

Run from `backend/`:

```powershell
uv run pytest tests/unit/analytics -v
uv run pytest tests/unit/schemas/test_analytics_schemas.py tests/unit/schemas/test_analytics_runtime.py -v
uv run pytest tests/unit/services/test_analytics_stage_claim.py tests/unit/services/test_analytics_executor.py -v
uv run pytest tests/unit/flows/test_business_analysis_finance_advance.py tests/unit/flows/test_business_analysis_analytics_advance.py -v

uv run pytest tests/unit/schemas/test_risk_schemas.py tests/unit/schemas/test_risk_runtime.py tests/unit/schemas/test_risk_stage_claim.py -v
uv run pytest tests/unit/services/test_risk_context.py tests/unit/services/test_risk_grounding.py tests/unit/services/test_risk_stage_claim.py tests/unit/services/test_risk_executor.py -v
uv run pytest tests/unit/crews/risk -v

uv run pytest tests/unit/chat/test_analysis_context.py -v
uv run pytest tests/integration/analysis/test_finance_to_analytics_to_risk.py -v

uv run pytest tests/integration/analysis -v
uv run pytest tests/unit -v
uv run pytest -v
```

Acceptance:
- 0 failed;
- 0 errors;
- no Day 7 regression;
- Finance → Decision Analytics → Risk integration passes;
- Risk hallucinated-lineage failure path passes;
- selective Chat analysis-context tests pass.

After the actual passing counts are available, update this file with the counts and mark Day 8 `COMPLETED & VALIDATED`.

## Next milestone

### Day 9 — Validation + Final Decision
After Day 8 final regression passes:
- Independent Validation;
- targeted correction/retry;
- Investment Committee;
- final decision guardrail;
- Chat AI explanation of decision/rationale/limitations.

## Important active rules
- Frozen `AnalysisRun.profile_snapshot` is never silently mutated by analysis-time Finance answers.
- Messages remain conversation history, not authoritative structured Finance state.
- User pause is for decision-critical BASE inputs that cannot safely be resolved from authoritative state/research; it is not a fallback for arbitrary model uncertainty.
- Competitor pricing is not venture pricing or willingness-to-pay proof.
- Selected option values are resolved from persisted backend requests, not trusted client values.
- LLMs never own authoritative Finance or Decision Analytics arithmetic.
- Risk AI never owns authoritative risk score or final risk level.
- Risk stage names alone are not sufficient grounding for ordinary risk claims.
- `INSUFFICIENT_EVIDENCE` remains a valid downstream state and must not trigger fabricated numbers.
- Chat analysis context is loaded selectively for relevant capabilities; unrelated general chat does not automatically receive Analytics/Risk outputs.
