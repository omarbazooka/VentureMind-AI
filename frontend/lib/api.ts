/**
 * VentureMind AI API Client
 * Connects frontend directly to the FastAPI backend.
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
  description?: string;
  value: number;
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
  run_status: string; // 'NOT_STARTED' | 'QUEUED' | 'RUNNING' | 'PAUSED_FOR_USER' | 'COMPLETED' | 'FAILED'
  current_stage?: string | null;
  completed_stages: string[];
  stage_runs: StageProgressItem[];
  pending_input?: PendingInputSummary | null;
  has_report: boolean;
  report_version?: number | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface StructuredReport {
  idea_id: string;
  analysis_run_id: string;
  version: number;
  executive_summary: {
    venture_name: string;
    one_liner: string;
    investment_recommendation: string;
    confidence_score: number;
    summary_narrative: string;
    key_strengths: string[];
    critical_risks: string[];
    next_milestones: string[];
  };
  market_intelligence: {
    tam_sam_som: {
      tam_estimate?: string | null;
      sam_estimate?: string | null;
      som_estimate?: string | null;
      confidence?: string | null;
    };
    target_customer_persona?: string | null;
    market_growth_rate?: string | null;
    key_trends: string[];
    evidence_quality: string;
  };
  competitor_intelligence: {
    direct_competitors: Array<{
      name: string;
      strengths: string[];
      weaknesses: string[];
      pricing_model?: string | null;
    }>;
    competitive_moat?: string | null;
  };
  financial_analysis: {
    key_metrics: {
      net_present_value?: { value: string; currency: string } | null;
      internal_rate_of_return?: { value: string } | null;
      payback_period_months?: { value: string } | null;
      monthly_burn_rate?: { value: string; currency: string } | null;
      break_even_units?: { value: string } | null;
    };
    scenarios: {
      base?: any;
      upside?: any;
      downside?: any;
    };
  };
  decision_analytics: {
    overall_score?: number | null;
    sensitivity_ranking: Array<{
      input_name: string;
      elasticity_score: number;
      impact_level: string;
    }>;
  };
  risk_assessment: {
    identified_risks: Array<{
      title: string;
      category: string;
      likelihood: string;
      impact: string;
      mitigation_actions: string[];
    }>;
  };
  independent_validation: {
    assessment_status: string;
    unresolved_issues: string[];
    limitations: string[];
  };
  investment_committee: {
    decision: 'GO' | 'CONDITIONAL_GO' | 'NO_GO' | 'INSUFFICIENT_EVIDENCE';
    confidence: 'HIGH' | 'MEDIUM' | 'LOW';
    decision_rationale: string;
    critical_conditions: string[];
    positive_signals: string[];
    negative_signals: string[];
  };
  sources_ledger: Array<{
    source_id: string;
    title: string;
    url?: string | null;
    stage: string;
  }>;
}

export interface ReportQAResponse {
  question: string;
  answer: string;
  grounded_in_report: boolean;
  cited_sections: string[];
  suggested_followups: string[];
}

export interface ReportActionResponse {
  action_type: string;
  status: string;
  summary: string;
  details: Record<string, any>;
  suggested_next_actions: string[];
}

export interface ReportComparisonResponse {
  idea_id: string;
  v1_version: number;
  v2_version: number;
  decision_comparison: {
    v1_decision: string;
    v2_decision: string;
    changed: boolean;
  };
  financial_comparison: Array<{
    metric_name: string;
    v1_value: any;
    v2_value: any;
    delta: any;
    direction: string;
  }>;
  risk_comparison: {
    v1_high_risks: number;
    v2_high_risks: number;
    net_risk_change: number;
  };
  lineage_comparison: {
    reused_stages: string[];
    reanalysis_reason?: string;
  };
  executive_takeaway: string;
}

function getAuthHeaders(): HeadersInit {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('supabase_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }
  return headers;
}

export async function listIdeas(): Promise<IdeaItem[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to list ideas: ${res.statusText}`);
  return res.json();
}

export async function getIdea(ideaId: string): Promise<IdeaItem> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas/${ideaId}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch idea: ${res.statusText}`);
  return res.json();
}

export async function createIdea(data: { title: string; description: string }): Promise<IdeaItem> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to create idea: ${res.statusText}`);
  return res.json();
}

export async function startAnalysis(ideaId: string): Promise<{ idea_id: string; analysis_run_id: string }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas/${ideaId}/analysis`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to start analysis: ${res.statusText}`);
  return res.json();
}

export async function getAnalysisProgress(ideaId: string): Promise<AnalysisProgressResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas/${ideaId}/analysis/progress`, {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`Failed to fetch progress: ${res.statusText}`);
  return res.json();
}

export async function answerPendingInput(
  ideaId: string,
  inputId: string,
  answer: {
    answer_mode: 'SELECTED_OPTION' | 'CUSTOM_INPUT';
    selected_option_id?: string;
    custom_value?: number;
    currency?: string;
    unit_label?: string;
    period?: string;
    rationale?: string;
  }
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas/${ideaId}/analysis/inputs/${inputId}/answer`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(answer),
  });
  if (!res.ok) throw new Error(`Failed to answer input: ${res.statusText}`);
  return res.json();
}

export async function getReport(ideaId: string, version?: number): Promise<StructuredReport> {
  const url = version
    ? `${API_BASE_URL}/api/v1/ideas/${ideaId}/report/versions/${version}`
    : `${API_BASE_URL}/api/v1/ideas/${ideaId}/report`;
  const res = await fetch(url, {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`Failed to fetch report: ${res.statusText}`);
  return res.json();
}

export async function askReportQuestion(ideaId: string, question: string): Promise<ReportQAResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas/${ideaId}/report/qa`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`Report Q&A request failed: ${res.statusText}`);
  return res.json();
}

export async function executeReportAction(
  ideaId: string,
  actionType: string,
  parameters: Record<string, any> = {}
): Promise<ReportActionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas/${ideaId}/report/action`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ action_type: actionType, parameters }),
  });
  if (!res.ok) throw new Error(`Report action failed: ${res.statusText}`);
  return res.json();
}

export async function reanalyzeIdea(
  ideaId: string,
  data: { target_stage?: string; profile_updates?: Record<string, any>; reason?: string }
): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas/${ideaId}/reanalyze`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Reanalysis failed: ${res.statusText}`);
  return res.json();
}

export async function compareReports(
  ideaId: string,
  v1: number,
  v2: number
): Promise<ReportComparisonResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ideas/${ideaId}/report/compare?v1=${v1}&v2=${v2}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Report comparison failed: ${res.statusText}`);
  return res.json();
}
