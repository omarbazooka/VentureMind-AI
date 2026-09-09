/**
 * VentureMind AI typed browser API client.
 * Keep this file aligned with the FastAPI contracts; do not invent frontend-only
 * analysis fields or endpoint shapes.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

export interface IdeaItem {
  id: string;
  title: string;
  description: string;
  owner_user_id?: string | null;
  state: string;
  created_at?: string;
}

export interface ChatMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface ChatTurnResponse {
  status: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  clarification?: unknown | null;
  profile_version?: number | null;
  profile_readiness?: string | null;
  conflicts: unknown[];
  unknown_conflicts: unknown[];
}

export interface IdeaProfile {
  idea_id: string;
  version: number;
  readiness: string;
  profile_data: Record<string, unknown>;
  profile_metadata: Record<string, unknown>;
  unknown_fields: string[];
}

export interface StageProgressItem {
  stage: string;
  attempt: number;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface PendingInputOption {
  option_id: string;
  label: string;
  value: number | string;
  currency?: string | null;
  unit_label?: string | null;
  period?: string | null;
  rationale?: string | null;
}

export interface PendingInputSummary {
  input_id: string;
  stage_run_id: string;
  input_name: string;
  question: string;
  options: PendingInputOption[];
  allow_custom: boolean;
  currency?: string | null;
  unit_label?: string | null;
  period?: string | null;
}

export interface AnalysisProgressResponse {
  idea_id: string;
  analysis_run_id?: string | null;
  run_status: string;
  current_stage?: string | null;
  completed_stages: string[];
  stage_runs: StageProgressItem[];
  pending_input?: PendingInputSummary | null;
  has_report: boolean;
  report_version?: number | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface AnalysisRunCreateResponse {
  run_id: string;
  idea_id: string;
  profile_id: string;
  profile_version: number;
  status: string;
  created_at: string;
}

export interface FinancialMetric {
  metric_name: string;
  value: string | number;
  currency?: string | null;
  unit: string;
  formula?: string;
  input_names?: string[];
  provenance?: string;
  period?: string | null;
}

export interface FinancialScenario {
  scenario: string;
  assumptions: Record<string, any>;
  metrics: FinancialMetric[];
  missing_critical_inputs: string[];
  limitations: string[];
}

export interface ReportMetricValue {
  status: 'AVAILABLE' | 'UNAVAILABLE' | 'INSUFFICIENT_EVIDENCE';
  value?: string | null;
  unit?: string | null;
  explanation?: string | null;
}

export interface DecisionLineageReference {
  kind: string;
  value: string;
  stage?: string | null;
}

export interface FinalDecision {
  decision: 'GO' | 'CONDITIONAL_GO' | 'NO_GO' | 'INSUFFICIENT_EVIDENCE';
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  rationale: string;
  supporting_evidence_lineage: DecisionLineageReference[];
  strongest_positive_signals: string[];
  strongest_negative_signals: string[];
  critical_assumptions: string[];
  limitations: string[];
  what_could_change: string[];
  recommended_next_steps: string[];
  upstream_stage_run_ids: Record<string, string>;
}

export interface StructuredReport {
  id: string;
  idea_id: string;
  analysis_run_id: string;
  version: number;
  title: string;
  executive_summary: string;
  decision: FinalDecision;
  profile_summary: Record<string, unknown>;
  market: {
    summary: string;
    evidence_quality: string;
    findings: Array<Record<string, any>>;
    market_metrics: {
      tam: ReportMetricValue;
      sam: ReportMetricValue;
      som: ReportMetricValue;
      cagr: ReportMetricValue;
      willingness_to_pay: ReportMetricValue;
    };
    limitations: string[];
  };
  competitors: {
    summary: string;
    evidence_quality: string;
    competitors: Array<Record<string, any>>;
    findings: Array<Record<string, any>>;
    limitations: string[];
  };
  customer: {
    summary: string;
    evidence_quality: string;
    findings: Array<Record<string, any>>;
    limitations: string[];
  };
  strategy: {
    executive_summary: string;
    positioning: Array<Record<string, any>>;
    value_proposition: Array<Record<string, any>>;
    business_model_implications: Array<Record<string, any>>;
    go_to_market: Array<Record<string, any>>;
    strategic_strengths: Array<Record<string, any>>;
    strategic_weaknesses: Array<Record<string, any>>;
    critical_assumptions: Array<Record<string, any>>;
    limitations: string[];
  };
  finance: {
    executive_summary: string;
    base_scenario: FinancialScenario;
    upside_scenario: FinancialScenario;
    downside_scenario: FinancialScenario;
    comparisons: Array<Record<string, any>>;
    limitations: string[];
  };
  analytics: {
    kpis: Array<Record<string, any>>;
    scenario_relative_changes: Array<Record<string, any>>;
    sensitivity?: Record<string, any> | null;
    limitations: string[];
  };
  risk: {
    executive_summary: string;
    overall_level?: string | null;
    risks: Array<Record<string, any>>;
    limitations: string[];
  };
  validation: {
    status: string;
    executive_assessment: string;
    issues: Array<Record<string, any>>;
    limitations: string[];
  };
  chart_data: {
    break_even_comparison: Array<Record<string, any>>;
    monthly_projections: Array<Record<string, any>>;
    sensitivity_ranking: Array<Record<string, any>>;
    risk_matrix: Array<Record<string, any>>;
  };
  sources: Array<{
    source_id: string;
    title: string;
    url?: string | null;
    provenance: string;
    stage: string;
  }>;
  created_at: string;
}

export interface ReportActionRequest {
  action:
    | 'EXPLAIN'
    | 'EXPLAIN_SIMPLY'
    | 'SHOW_EVIDENCE'
    | 'SHOW_SOURCES'
    | 'EXPLAIN_CALCULATION'
    | 'EXPLAIN_CHART'
    | 'CHALLENGE_CONCLUSION'
    | 'WHAT_COULD_CHANGE'
    | 'ASK_VENTUREMIND';
  target_section?: string;
  target_metric?: string;
  question?: string;
}

export interface ReportActionResponse {
  action: string;
  title: string;
  content: string;
  grounding_references: string[];
  suggested_followups: string[];
  metadata: Record<string, any>;
}

export interface ReportQAResponse {
  answer: string;
  grounding_references: string[];
  suggested_followups: string[];
}

export interface ReportComparisonResponse {
  idea_id: string;
  v1_report_id: string;
  v1_version: number;
  v2_report_id: string;
  v2_version: number;
  v1_analysis_run_id: string;
  v2_analysis_run_id: string;
  decision_comparison: Record<string, any>;
  financial_comparison: Array<Record<string, any>>;
  risk_comparison: Record<string, any>;
  lineage_comparison: Record<string, any>;
  executive_takeaway: string;
}

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (typeof window !== 'undefined') {
    const token =
      localStorage.getItem('venturemind_access_token') ||
      localStorage.getItem('supabase_token');
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') detail = body.detail;
      else if (body?.detail) detail = JSON.stringify(body.detail);
    } catch {
      // Keep the HTTP status when the error response is not JSON.
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export function setAccessToken(token: string | null): void {
  if (typeof window === 'undefined') return;
  if (token) localStorage.setItem('venturemind_access_token', token);
  else localStorage.removeItem('venturemind_access_token');
}

export function listIdeas(): Promise<IdeaItem[]> {
  return apiFetch('/api/v1/ideas');
}

export function getIdea(ideaId: string): Promise<IdeaItem> {
  return apiFetch(`/api/v1/ideas/${ideaId}`);
}

export function createIdea(data: {
  title: string;
  description: string;
}): Promise<IdeaItem> {
  return apiFetch('/api/v1/ideas', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function getProfile(ideaId: string): Promise<IdeaProfile> {
  return apiFetch(`/api/v1/ideas/${ideaId}/profile`, { cache: 'no-store' });
}

export function getMessages(ideaId: string): Promise<ChatMessage[]> {
  return apiFetch(`/api/v1/ideas/${ideaId}/messages`, { cache: 'no-store' });
}

export function sendMessage(ideaId: string, content: string): Promise<ChatTurnResponse> {
  return apiFetch(`/api/v1/ideas/${ideaId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export function startAnalysis(ideaId: string): Promise<AnalysisRunCreateResponse> {
  return apiFetch(`/api/v1/ideas/${ideaId}/analysis`, { method: 'POST' });
}

export function getAnalysisProgress(
  ideaId: string,
): Promise<AnalysisProgressResponse> {
  return apiFetch(`/api/v1/ideas/${ideaId}/analysis/progress`, {
    cache: 'no-store',
  });
}

export function answerPendingInput(
  ideaId: string,
  inputId: string,
  answer: {
    choice?: string;
    value?: number;
    currency?: string;
    unit_label?: string;
    period?: string;
  },
): Promise<{
  input_id: string;
  status: string;
  analysis_run_status: string;
  message: string;
}> {
  return apiFetch(`/api/v1/ideas/${ideaId}/analysis/inputs/${inputId}/answer`, {
    method: 'POST',
    body: JSON.stringify(answer),
  });
}

export function getReport(
  ideaId: string,
  version?: number,
): Promise<StructuredReport> {
  const path = version
    ? `/api/v1/ideas/${ideaId}/reports/${version}`
    : `/api/v1/ideas/${ideaId}/report/latest`;
  return apiFetch(path, { cache: 'no-store' });
}

export function executeReportAction(
  ideaId: string,
  request: ReportActionRequest,
): Promise<ReportActionResponse> {
  return apiFetch(`/api/v1/ideas/${ideaId}/report/action`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function askReportQuestion(
  ideaId: string,
  question: string,
): Promise<ReportQAResponse> {
  const response = await executeReportAction(ideaId, {
    action: 'ASK_VENTUREMIND',
    question,
  });
  return {
    answer: response.content,
    grounding_references: response.grounding_references,
    suggested_followups: response.suggested_followups,
  };
}

export function compareReports(
  ideaId: string,
  v1: number,
  v2: number,
): Promise<ReportComparisonResponse> {
  return apiFetch(`/api/v1/ideas/${ideaId}/report/compare?v1=${v1}&v2=${v2}`, {
    cache: 'no-store',
  });
}
