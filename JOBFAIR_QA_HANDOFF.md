# VentureMind AI — Job Fair QA Handoff

_Last updated: 2026-09-10_

> **Branch:** `jobfair-demo`  
> **QA status:** IN PROGRESS — core vertical slice implemented, final local/E2E verification still required  
> **Reviewed implementation through:** `b75291aa23cbe7289b4e36a70881a9bfe720cb90`  
> **Stable branches:** do not merge to `master` until final QA is complete

## 1. What is actually implemented

The current Job Fair branch contains a production-minded vertical slice for:

`Create Idea → Chat/Intake → IdeaProfile → explicit Start Analysis → Research → Research Join/Evidence Gate → Strategy → Finance → optional user pause → Decision Analytics → Risk → Independent Validation → Investment Committee / Final Decision → versioned Structured Report → grounded report actions / Chat follow-up`

Backend stack: FastAPI, Python 3.13, SQLAlchemy, Alembic, CrewAI/LLM Gateway where appropriate, deterministic Python for authoritative calculations/state rules.

Frontend stack: Next.js 14 App Router + TypeScript.

Files/RAG and payments remain intentionally outside the Job Fair MVP scope.

## 2. QA hardening already applied

The QA pass corrected issues that would otherwise make the demo misleading or unsafe:

- Independent Validation and Final Decision now revalidate exact upstream stage-run lineage at the persistence boundary.
- Final Decision lineage uses grounded typed references rather than arbitrary model strings.
- Report generation selects the exact upstream results referenced by the Final Decision instead of an arbitrary/latest result.
- Report generation no longer invents a monthly financial ramp.
- Report actions no longer invent useful-sounding fallback business claims.
- Finance pause answers reject ambiguous/invalid input and predefined option values remain server-authoritative.
- Progress reports a genuinely active PAUSED/RUNNING stage before queued PENDING work.
- Workspace ownership is enforced across Ideas, Chat, Profile, Analysis, Finance inputs, Reports, report actions, re-analysis, and report comparison.
- Supabase JWT verification validates signature, issuer, audience, expiry, and subject for verified tokens; JWT errors do not leak internal details.
- FastAPI CORS is explicit/environment-driven for the browser frontend.
- Next.js public environment variables are passed at build time in Docker.
- Frontend API routes and request/response shapes were realigned with the actual FastAPI contracts.
- Frontend report fields were realigned with the actual `StructuredReport` contract.
- Unsupported frontend claims for NPV, IRR, five-year DCF, monthly burn, fake sensitivity values, fake competitor defaults, and unsupported report actions were removed.
- New idea text is sent through the normal Chat/Intake path so IdeaProfile extraction starts from the user's initial description.
- Targeted re-analysis controls were removed from the current Job Fair frontend because its executable result-reuse path is not complete yet.

## 3. Current frontend journey

Current implemented routes include:

- `/` — grounded landing page
- `/dashboard` — ideas dashboard
- `/ideas/new` — create idea and begin the first Chat/Intake turn
- `/ideas/[ideaId]` — Idea Workspace

The Idea Workspace currently provides:

- the same Chat AI throughout the idea lifecycle;
- Idea Profile before analysis;
- explicit Start Analysis only when backend readiness is `READY_FOR_ANALYSIS`;
- real backend progress polling;
- Finance `PAUSED_FOR_USER` card and resume interaction;
- authoritative Structured Report sections;
- Base/Upside/Downside Finance values that actually exist in the backend Finance result;
- Analytics sensitivity data from persisted Decision Analytics;
- grounded risks and validation findings;
- final decision and confidence;
- persisted evidence sources;
- supported report actions: Challenge Conclusion, What Could Change, Explain Break-Even, and Show Sources.

## 4. Authentication status

### Backend — implemented

- `ideas.owner_user_id` migration exists.
- Supabase bearer JWT verification exists.
- Modern asymmetric JWKS verification is supported.
- Legacy HS256 fallback is available only when explicitly configured.
- Expected issuer is `${SUPABASE_URL}/auth/v1`.
- Audience is configurable and defaults to `authenticated`.
- Required identity claims include `exp`, `iss`, `sub`, and `aud`.
- User identity comes from the verified JWT subject, never request payload data.
- Dev bypass is disabled by default and restricted to development/test environments.
- Owned workspace resources are protected server-side.

### Frontend — NOT COMPLETE YET

The current frontend does **not yet** contain the real Supabase login/signup/logout/session UI or Supabase JS client lifecycle. The API client can attach a stored bearer token, but that is not a complete authentication UX.

Do not present end-user authentication as complete until this frontend path is implemented and tested.

## 5. Targeted re-analysis status

**Status: PARTIAL / NOT DEMO-READY.**

The branch contains a deterministic impact-resolver foundation that can:
- create a new profile/run version;
- classify reused vs invalidated stages;
- preserve previous execution history;
- record reuse lineage metadata;
- compare report versions.

However, reused upstream results are currently recorded as metadata only. The existing `BusinessAnalysisFlow` / `PipelineRunner` still expects prerequisite results to belong to the new `analysis_run_id`, so the executable pipeline does not yet consume reuse lineage as a complete authoritative dependency chain.

Therefore:
- do not claim that only invalidated stages re-execute end-to-end yet;
- do not expose Apply Change / Re-analysis in the Job Fair frontend yet;
- keep this as follow-up engineering work after the core demo path is stable.

## 6. Docker status

Present configuration:
- PostgreSQL 16 container;
- FastAPI backend container;
- Next.js frontend container;
- backend waits for Postgres health;
- frontend waits for backend health;
- Alembic migration runs before the backend server in the single-instance Job Fair compose flow;
- CORS origin is configurable through `CORS_ORIGINS`;
- `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` are available as frontend build args.

**Still required:** run a fresh `docker compose up --build` smoke after the latest QA changes.

## 7. Test/build evidence

Antigravity previously reported:
- backend: `486 passed / 0 failed`;
- frontend: successful `npm run build`.

Those results were produced **before several later QA code changes**. GitHub currently has no CI status checks attached that independently prove the current post-QA HEAD.

Treat those numbers as historical reported evidence, not final current validation.

Required final verification:

```bash
cd backend
uv run pytest -v

cd ../frontend
npm ci
npm run build

cd ..
docker compose up --build
```

For the Job Fair exit gate, also run one real HTTP/UI smoke through the core journey.

## 8. Recommended final Job Fair demo path

Use only the currently grounded core flow:

1. Open the landing page.
2. Create an idea.
3. Show that the initial description becomes the first Chat/Intake turn.
4. Continue clarification until Idea Profile reaches `READY_FOR_ANALYSIS`.
5. Click Start Analysis explicitly.
6. Show real backend-driven progress.
7. If Finance pauses, choose a backend-provided option or enter a custom value and resume.
8. Continue through Analytics, Risk, Independent Validation, and Final Decision.
9. Open the versioned Structured Report.
10. Show Market/Competitor/Customer evidence and limitations.
11. Show deterministic Base/Upside/Downside Finance results and sensitivity.
12. Show Risk and Validation.
13. Show the Final Decision and confidence.
14. Use grounded actions such as Challenge Conclusion, What Could Change, Explain Break-Even, and Show Sources.
15. Ask a follow-up through the same Chat AI.

Do **not** demo targeted re-analysis until its dependency-reuse execution path is completed and verified.

## 9. Remaining blockers before calling the Job Fair build fully validated

1. Real frontend Supabase authentication UI/session flow.
2. Full backend regression after latest QA fixes.
3. Fresh frontend TypeScript/Next.js production build after latest QA fixes.
4. Docker Compose smoke after latest QA fixes.
5. End-to-end core journey smoke.
6. Deployment or documented deployment instructions if deployment credentials are unavailable.
7. Targeted re-analysis remains outside the approved core demo until its actual result-reuse runtime is fixed.

## 10. Review rule

Do not merge this branch into `master` based only on this document. Final approval requires current test/build/container/E2E evidence against the final branch HEAD.
