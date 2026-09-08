# VentureMind AI — Current Progress

_Last updated: 2026-09-08_

This file is the current implementation checkpoint. Older milestone notes should not override this section.

## Build Status

- **Day 1 — Foundation:** DONE
- **Day 2 — Persistence / State:** DONE
- **Day 3 — Chat Runtime Foundation:** DONE
- **Day 4 — Intake:** DONE
- **Day 5 — AnalysisRun + Research Foundation:** DONE
- **Day 6 — Files / RAG:** DEFERRED POST-MVP (ADR-028)
- **Day 7 — Business Strategy + Finance:** IMPLEMENTATION COMPLETE; FINAL E2E/FULL REGRESSION VALIDATION PENDING
- **Day 8 — Decision Analytics + Risk:** PENDING
- **Day 9 — Validation + Final Decision:** PENDING
- **Day 10 — Structured Report + Visualization:** PENDING
- **Day 11 — Unified Grounded Chat Q&A:** PENDING
- **Day 12 — Changes + Targeted Re-analysis + Compound Turns:** PENDING
- **Day 13 — E2E Hardening:** PENDING

## Day 7 — Business Strategy

**Status: IMPLEMENTATION COMPLETE**

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

**Status: IMPLEMENTATION COMPLETE; FINAL NEW INTEGRATION/FULL REGRESSION RESULTS NOT YET RECORDED**

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

## Day 7 — Integration coverage now added

### Strategy → Finance scheduling
`BusinessAnalysisFlow.advance_strategy()` now:
- requires AnalysisRun = RUNNING;
- requires a completed Business Strategy stage;
- requires its persisted Business Strategy `AnalysisResult`;
- reuses an existing initial Finance stage if present;
- otherwise creates `FINANCE`, attempt 1, `PENDING`.

A helper-scope/indentation bug found by the focused unit tests was fixed by moving `_require_completed_strategy_result()` and `_ensure_finance_stage_run()` inside `BusinessAnalysisFlow`.

### Real-DB Strategy → Finance integration
Added `tests/integration/analysis/test_strategy_to_finance.py` with real PostgreSQL transaction-backed lifecycle coverage while faking only the LLM-facing Finance assumption runner.

It covers:
1. completed Strategy → Finance scheduling → claim → grounded assumptions → deterministic calculation → persisted Finance result → FINANCE COMPLETED;
2. missing selling price → Finance/AnalysisRun `PAUSED_FOR_USER` → `AnalysisRunInput(PENDING)` → custom user answer → `ANSWERED` → Finance `PENDING` + AnalysisRun `RUNNING` → re-claim → run-input USER overlay → deterministic calculation → FINANCE COMPLETED.

## Validation status

The user reported the earlier focused Finance/unit regressions passing before the final Strategy → Finance integration addition.

The following final checkpoint still needs to be recorded as passed before marking Day 7 `COMPLETED & VALIDATED`:

```powershell
uv run pytest tests/unit/flows/test_business_analysis_strategy_advance.py -v
uv run pytest tests/integration/analysis/test_strategy_to_finance.py -v
uv run pytest tests/integration/analysis -v
uv run pytest tests/unit -v
uv run pytest -v
```

Acceptance: 0 failed / 0 errors.

## Day 7 exit criteria
When the final commands above pass:
- mark Day 7 `COMPLETED & VALIDATED`;
- update this file with the actual pass counts;
- proceed to Day 8 — Decision Analytics + Risk.

## Important active rules
- Frozen `AnalysisRun.profile_snapshot` is never silently mutated by analysis-time Finance answers.
- Messages remain conversation history, not authoritative structured Finance state.
- User pause is for decision-critical BASE inputs that cannot safely be resolved from authoritative state/research; it is not a fallback for arbitrary model uncertainty.
- Competitor pricing is not venture pricing or willingness-to-pay proof.
- Selected option values are resolved from persisted backend requests, not trusted client values.
- LLMs never own authoritative Finance arithmetic.
- `INSUFFICIENT_EVIDENCE` remains a valid downstream state and must not trigger fabricated numbers.
