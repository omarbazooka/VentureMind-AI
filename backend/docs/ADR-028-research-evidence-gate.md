# ADR-028 — Research Evidence Gate outcome semantics and bounded targeted retry

**Status:** Accepted for MVP

## Context
Market, Competitor, and Customer research now produce independently validated structured outputs. The system needs a deterministic join/gate policy that improves recoverable weak work without turning missing primary evidence into an endless research loop or discarding successful partial results.

## Decision
The Research Join/Evidence Gate is application-owned deterministic orchestration, not a fourth research agent or Crew.

Gate outcomes:
- `ACCEPT`: all latest research stages are completed with `STRONG` or `MODERATE` evidence. Downstream analysis may proceed.
- `RETRY`: at least one latest stage is `FAILED` or `WEAK` and still has retry budget. Downstream progression pauses and only those retryable stages receive a new attempt.
- `INSUFFICIENT`: one or more stages have a non-retryable evidence gap (`INSUFFICIENT` output or exhausted retry budget), but no retryable work remains. Downstream analysis may proceed with the gaps explicitly preserved.

If retryable and non-retryable gaps exist together, `RETRY` takes precedence. After recoverable work is exhausted/resolved, the gate may return `INSUFFICIENT` with `can_proceed=True`.

Default research-stage attempt budget is 2 total attempts (initial attempt + one targeted retry). This remains an application policy constant and can be revisited with measured evidence.

The Join keeps the latest stage attempt for gate state, while also preserving the latest successful persisted result from an earlier attempt when a later retry fails. Successful unrelated stages are never rerun or overwritten.

## Why
- prevents uncontrolled retry loops;
- avoids treating missing primary evidence as a system error;
- preserves useful partial research;
- keeps known DAG dependencies under deterministic Python control;
- avoids an unnecessary LLM judge for stage-state/evidence-quality routing.

## Tradeoffs
- evidence-quality categories remain coarse;
- semantic cross-stage contradiction analysis remains a later validation responsibility unless a deterministic structured check exists;
- reason-specific retry prompts are not persisted yet; the current MVP targets the smallest affected stage.

## Revisit when
Measured runs show that one retry is insufficient, evidence-quality routing needs finer-grained policy, or repeated retry-reason plumbing justifies a persisted retry-context contract.

## Canonical project-doc note
The complete architecture decision history is maintained in the project's `08_DECISIONS_LOG.md`. This repository previously did not track that file, so ADR-028 is mirrored here as the repository-local record of this decision.
