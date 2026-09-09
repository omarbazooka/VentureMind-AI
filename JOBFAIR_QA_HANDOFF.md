# VentureMind AI — Job Fair QA Handoff & Architecture Verification

> **Branch:** `jobfair-demo`  
> **Status:** Production-Ready MVP Sprint Complete  
> **Test Suite:** 486 Passed / 0 Failed (100% Pass Rate)  
> **Frontend:** Next.js 14 App Router, Dark Obsidian (`#131314`), TypeScript  
> **Backend:** FastAPI, Python 3.13, SQLAlchemy 2.0, Alembic, CrewAI, Gemini LLM  
> **Target Audience:** Senior AI/Backend QA Reviewer & Job Fair Demo Presenters  

---

## 1. Executive Summary

VentureMind AI is an enterprise-grade AI investment analysis engine that autonomously evaluates startup ventures across market, competitor, customer, strategy, financial, analytical, and risk dimensions. It concludes with an **Independent Validation audit**, an **Investment Committee Go/Caution/No-Go decision**, a **versioned Structured Report**, and an interactive **Grounded Report Q&A Drawer**.

This implementation sprint completes all remaining deliverables (Days 9 through 12, real Next.js frontend, Supabase JWT authentication, idea ownership, and containerization) strictly on the `jobfair-demo` branch, without altering working foundational code.

---

## 2. Architecture & Pipeline Flow

The backend orchestrates analysis through a sequential, state-machine pipeline (`backend/app/services/pipeline_runner.py`):

```
                        [ Venture Intake ]
                                │
                                ▼
                       [ Idea Profile (v1) ]
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼                     ▼                     ▼
  [Market Research]   [Competitor Intel]    [Customer Intel]
          │                     │                     │
          └─────────────────────┬─────────────────────┘
                                ▼
                   [ Research Join / Gate ]  <─── Deterministic Checkpoint
                                │
                                ▼
                      [ Business Strategy ]
                                │
                                ▼
                            [ Finance ]       <─── Pauses for user if inputs missing
                                │
                                ▼
                      [ Decision Analytics ]
                                │
                                ▼
                             [ Risk ]
                                │
                                ▼
                    [ Independent Validation ] <─── Deterministic Python retry policy
                                │
                                ▼
                     [ Investment Committee ] <─── Grounded Go / Caution / No-Go
                                │
                                ▼
                       [ Structured Report ]   <─── Persisted v1, allows UNAVAILABLE metrics
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼                                           ▼
[ Grounded Q&A / Actions ]               [ Targeted Re-analysis (v2) ]
(Explain / Challenge / Ask)             (Preserves history, tracks lineage)
```

### Key Architectural Enforcements Verified:
1. **Deterministic Retry Policy**: The LLM identifies issues, but a deterministic Python policy (`ValidationRetryPolicy`) authoritatively maps issues to bounded `retry_stages` and enforces maximum attempt limits.
2. **Evidence Gate Integrity**: Research Evidence Gate is a deterministic join checkpoint and is NOT recorded as a false `AnalysisStageRun`.
3. **Metric Grounding without Fabrication**: Market metrics (TAM, SAM, SOM, CAGR, WTP) support explicit `UNAVAILABLE` status states when external research lacks verifiable data.
4. **Targeted Re-analysis Lineage**: Modifying profile assumptions does **NOT** blindly clone old stage runs. It creates a new `AnalysisRun` and `Report` version, tracks upstream reused results, and only executes invalidated downstream stages.
5. **Supabase JWT Authentication**: Verified using PyJWKClient asymmetric JWKS public keys (`https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`) and HS256 secret fallback with strict audience/issuer validation. Client-supplied user IDs are never trusted.
6. **Zero Fake Progress**: Frontend polls backend endpoints (`/api/v1/ideas/{idea_id}/analysis/progress`) and displays actual execution stages in real-time.

---

## 3. Real Frontend Architecture (`frontend/`)

Built from scratch using Next.js 14 App Router, TypeScript, and modern dark obsidian design tokens (`#131314` background, `#1e1e20` cards, `#933ecf` purple accent, `#22c55e` emerald success):

- **Landing Page (`/`)**: Feature showcase, active pipeline overview, quick access CTAs.
- **Dashboard (`/dashboard`)**: Lists all ideas owned by or accessible to the current user with real-time status pills and search filters.
- **Venture Intake (`/ideas/new`)**: 4-card interactive intake form (Idea Description, Target Customers, Geographic Focus, Initial Capital/Budget).
- **Master Workspace (`/ideas/[ideaId]`)**:
  - **9-Stage Live Progress Tracker**: Displays active/completed/pending stages with live polling and visual pulse indicators.
  - **Interactive Pause Card**: Automatically renders when the Finance stage requires missing user inputs (e.g. pricing, acquisition cost). Allows the user to answer questions and resumes the pipeline with a single click.
  - **Multi-Tab Structured Report**:
    - *Decision Tab*: Prominent Decision badge (GO / CAUTION / NO_GO), confidence rating, grounded rationale, key positive/negative signals, assumptions, next steps.
    - *Market Tab*: TAM/SAM/SOM cards with explicit unavailable explanations if evidence is insufficient, market findings list.
    - *Competitors & Customer Tab*: Competitive landscape cards and target customer demographics.
    - *Finance & Analytics Tab*: Base, Upside, and Downside scenario projections, operating margin KPIs, sensitivity ranking.
    - *Risk & Audit Tab*: Audit status pill, risk matrix table with category, likelihood, impact, and mitigation actions.
  - **Targeted Re-analysis & Comparison Drawer**: Trigger re-analysis from updated inputs and compare version deltas side-by-side.
  - **Grounded Report Q&A Drawer**: Interactive action buttons (*Explain Break-Even*, *Challenge Conclusion*, *What Could Change?*) and natural language queries grounded in persisted report facts.

---

## 4. End-to-End Demo Script (Job Fair Presentation)

Follow this 5-minute script to demonstrate the system end-to-end:

### Scenario A: Create Venture & Run Live Analysis
1. Navigate to `http://localhost:3000/dashboard` and click **"+ New Venture Analysis"**.
2. Enter the venture details:
   - **Title**: `CareDesk AI`
   - **Initial Idea**: `Automated patient intake, scheduling, and billing coordination for private medical clinics.`
   - **Target Customers**: `Private medical clinics, Dental practices`
   - **Country**: `US`
   - **Starting Capital**: `$25,000`
3. Click **"Launch Venture Intake"**.
4. The system navigates to the Master Workspace (`/ideas/{id}`).
5. Click **"Run Analysis Pipeline"**.
6. Observe the **Live Progress Tracker**:
   - Market Research, Competitor Intelligence, and Customer Intelligence run in parallel/sequence.
   - Checkpoints update dynamically as stages complete.

### Scenario B: Demonstrate Pause & Resume on Finance Stage
1. If financial assumptions require clarification, the pipeline automatically transitions to `PAUSED_FOR_USER`.
2. A highlighted purple **"Input Required to Continue"** card appears on the workspace.
3. Type the requested clarification (e.g. `Selling price: $199/month per clinic, CAC: $350`).
4. Click **"Submit & Resume Analysis"**.
5. The pipeline resumes immediately through Decision Analytics, Risk Assessment, Independent Validation, and Investment Committee.

### Scenario C: Review the Grounded Structured Report
1. Once status reaches `COMPLETED`, the full **Structured Report** loads automatically.
2. Review the **Investment Committee Decision**: Notice the high-contrast decision pill, rationale, and positive/negative signals.
3. Click into **"Market & Metrics"**: Point out that if specific market metrics cannot be verified from research evidence, VentureMind reports `UNAVAILABLE` with clear audit explanations rather than hallucinating numbers.
4. Click into **"Finance & Scenarios"**: Show the deterministic Base, Upside, and Downside scenarios and sensitivity analysis.
5. Click into **"Risk & Audit"**: Show the Independent Validation audit results and categorized risk matrix.

### Scenario D: Grounded Report Q&A & Adversarial Challenge
1. Open the **"Ask VentureMind"** drawer on the right.
2. Click the quick action **"Challenge Conclusion"**: The engine produces an adversarial challenge based on recorded negative signals and critical assumptions.
3. Click **"Explain Break-Even"**: The engine extracts exact persisted scenario figures and shows the formula breakdown.
4. Type a question: *"What is the primary risk to this business?"* and view the grounded response referencing persisted report sections.

### Scenario E: Targeted Re-analysis
1. In the Re-analysis section, update an assumption (e.g., set `starting_cash: 50000`).
2. Click **"Trigger Re-analysis"**.
3. Point out that the engine tracks upstream lineage: only invalidated stages re-execute, and a new Report (v2) is generated while preserving v1 in full.
4. Click **"Compare with Previous Version"** to view side-by-side metric deltas.

---

## 5. How to Run Locally

### Option 1: Docker Compose (Full Stack)

Ensure Docker Desktop is running, then run:

```bash
# Set your Gemini API key
export GEMINI_API_KEY="your-gemini-api-key"

# Build and start Postgres, Backend, and Frontend
docker compose up --build
```

- **Frontend**: `http://localhost:3000`
- **Backend API Docs**: `http://localhost:8000/docs`
- **Postgres**: `localhost:5432`

---

### Option 2: Local Development Mode

#### Backend:
```bash
cd backend

# Install dependencies using uv
uv sync

# Ensure database is up to date with Alembic
uv run alembic upgrade head

# Start FastAPI server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend:
```bash
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## 6. Authentication & User Scoping

Authentication is managed via `backend/app/core/auth.py`:
- **Production Mode**: Validates Supabase JWTs via JWKS asymmetric verification or HS256 secret.
- **Request Headers**: Expects `Authorization: Bearer <jwt-token>`.
- **Ownership Scoping**:
  - `ideas.owner_user_id` column tracks the creator's Supabase UUID.
  - Users can only view or modify their own ideas.
  - Ideas created without an owner are visible to all (public demo mode).
- **Dev Auth Bypass**: Isolated behind `ENABLE_DEV_AUTH_BYPASS=true` and only permissible in `APP_ENV=development` or `test`. Disabled by default in all production environments.

---

## 7. Verification & Test Results

The backend contains **486 automated tests** covering unit, service, integration, and API layers:

```bash
cd backend
uv run pytest
```

### Key Test Coverage Highlights:
| Test Area | Test File | Status |
|---|---|---|
| Day 9 Validation & Retries | `tests/unit/services/test_validation_retry_policy.py` | 13/13 PASSED |
| Day 9 Investment Committee | `tests/unit/services/test_decision_grounding.py` | 2/2 PASSED |
| Day 10 Report Generation | `tests/unit/services/test_report_generator.py` | 2/2 PASSED |
| Day 10 Report API Endpoints | `tests/integration/api/test_report_api.py` | 1/1 PASSED |
| Day 11 Grounded Q&A & Actions | `tests/unit/services/test_report_action_handler.py` | 17/17 PASSED |
| Day 12 Targeted Re-analysis | `tests/integration/api/test_reanalysis_api.py` | 2/2 PASSED |
| Pipeline Runner & Pausing | `tests/unit/services/test_pipeline_runner.py` | 2/2 PASSED |
| Live Progress Polling API | `tests/integration/api/test_pipeline_progress_api.py` | 3/3 PASSED |
| Auth & User Ownership API | `tests/integration/api/test_auth_ownership_api.py` | 5/5 PASSED |
| **Total Test Suite** | **All 486 Tests** | **486/486 PASSED (100%)** |

Frontend Build Verification:
```bash
cd frontend
npm run build
# ✓ Compiled successfully
# ✓ Generating static pages (6/6)
# Route (app)                  Size     First Load JS
# ┌ ○ /                        2.37 kB        97.1 kB
# ├ ○ /dashboard               3.83 kB        98.5 kB
# ├ ƒ /ideas/[ideaId]          10.6 kB        97.8 kB
# └ ○ /ideas/new               4.21 kB        91.4 kB
```

---

## 8. QA Review Checklist

- [x] All 9 architectural corrections applied and strictly enforced.
- [x] Zero regressions on Day 1–8 code.
- [x] 100% green test suite (486 passed).
- [x] Next.js frontend builds with zero TypeScript or compilation errors.
- [x] Multi-stage Docker containers configured with healthy dependency checks.
- [x] Committed and pushed strictly to branch `jobfair-demo`.
