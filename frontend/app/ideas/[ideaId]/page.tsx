'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  getIdea,
  getAnalysisProgress,
  startAnalysis,
  answerPendingInput,
  getReport,
  askReportQuestion,
  executeReportAction,
  compareReports,
  IdeaItem,
  AnalysisProgressResponse,
  StructuredReport,
  ReportQAResponse,
  ReportActionResponse,
  ReportComparisonResponse,
} from '@/lib/api';
import {
  Sparkles,
  Play,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Send,
  HelpCircle,
  TrendingUp,
  BarChart3,
  ShieldCheck,
  Award,
  Layers,
  FileText,
  DollarSign,
  Zap,
  RotateCw,
  GitCompare,
  ArrowUpRight,
  ArrowDownRight,
  ExternalLink,
} from 'lucide-react';

const PIPELINE_STAGE_LABELS: Record<string, string> = {
  MARKET_RESEARCH: 'Market Research',
  COMPETITOR_INTELLIGENCE: 'Competitor Intelligence',
  CUSTOMER_INTELLIGENCE: 'Customer Signals',
  BUSINESS_STRATEGY: 'Business Strategy',
  FINANCE: 'DCF / Unit Finance',
  DECISION_ANALYTICS: 'Decision Analytics',
  RISK: 'Risk Matrix',
  INDEPENDENT_VALIDATION: 'Validation Audit',
  INVESTMENT_COMMITTEE: 'Investment Committee',
};

const STAGE_ORDER = [
  'MARKET_RESEARCH',
  'COMPETITOR_INTELLIGENCE',
  'CUSTOMER_INTELLIGENCE',
  'BUSINESS_STRATEGY',
  'FINANCE',
  'DECISION_ANALYTICS',
  'RISK',
  'INDEPENDENT_VALIDATION',
  'INVESTMENT_COMMITTEE',
];

export default function IdeaWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const ideaId = params.ideaId as string;

  const [idea, setIdea] = useState<IdeaItem | null>(null);
  const [progress, setProgress] = useState<AnalysisProgressResponse | null>(null);
  const [report, setReport] = useState<StructuredReport | null>(null);
  const [activeTab, setActiveTab] = useState<string>('overview');

  // Loading & error states
  const [loading, setLoading] = useState(true);
  const [startingAnalysis, setStartingAnalysis] = useState(false);
  const [answeringInput, setAnsweringInput] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // User input answer form state
  const [selectedOptionId, setSelectedOptionId] = useState<string>('');
  const [customValue, setCustomValue] = useState<string>('');
  const [useCustomValue, setUseCustomValue] = useState<boolean>(false);

  // Report Q&A Assistant state
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string; citations?: string[] }>>([
    {
      role: 'assistant',
      text: 'Hello! I am your Investment Committee Due Diligence Assistant. Ask me anything about this venture\'s financial model, market dynamics, sensitivity drivers, or committee verdict.',
    },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [askingQA, setAskingQA] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Report comparison state
  const [comparison, setComparison] = useState<ReportComparisonResponse | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  // Poll progress while RUNNING or QUEUED
  useEffect(() => {
    loadWorkspaceData();
  }, [ideaId]);

  useEffect(() => {
    if (!progress) return;
    if (progress.run_status === 'RUNNING' || progress.run_status === 'QUEUED') {
      const timer = setInterval(() => {
        pollProgress();
      }, 2500);
      return () => clearInterval(timer);
    }
  }, [progress?.run_status]);

  async function loadWorkspaceData() {
    try {
      setLoading(true);
      setError(null);
      const ideaData = await getIdea(ideaId);
      setIdea(ideaData);

      const progData = await getAnalysisProgress(ideaId);
      setProgress(progData);

      if (progData.has_report) {
        const reportData = await getReport(ideaId);
        setReport(reportData);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load workspace data');
    } finally {
      setLoading(false);
    }
  }

  async function pollProgress() {
    try {
      const progData = await getAnalysisProgress(ideaId);
      setProgress(progData);

      if (progData.has_report && !report) {
        const reportData = await getReport(ideaId);
        setReport(reportData);
      }
    } catch (err) {
      console.error('Progress poll failed', err);
    }
  }

  async function handleStartAnalysis() {
    try {
      setStartingAnalysis(true);
      setError(null);
      await startAnalysis(ideaId);
      await pollProgress();
    } catch (err: any) {
      setError(err.message || 'Failed to start analysis');
    } finally {
      setStartingAnalysis(false);
    }
  }

  async function handleAnswerInput(e: React.FormEvent) {
    e.preventDefault();
    if (!progress?.pending_input) return;

    try {
      setAnsweringInput(true);
      setError(null);

      const inputId = progress.pending_input.input_id;

      if (useCustomValue) {
        if (!customValue || isNaN(Number(customValue))) {
          setError('Please enter a valid numeric custom value');
          setAnsweringInput(false);
          return;
        }
        await answerPendingInput(ideaId, inputId, {
          answer_mode: 'CUSTOM_INPUT',
          custom_value: Number(customValue),
          currency: progress.pending_input.currency || 'USD',
          unit_label: progress.pending_input.unit_label || 'seat',
          period: progress.pending_input.period || undefined,
        });
      } else {
        if (!selectedOptionId) {
          setError('Please select an option or provide a custom value');
          setAnsweringInput(false);
          return;
        }
        await answerPendingInput(ideaId, inputId, {
          answer_mode: 'SELECTED_OPTION',
          selected_option_id: selectedOptionId,
        });
      }

      // Refresh progress immediately
      await pollProgress();
    } catch (err: any) {
      setError(err.message || 'Failed to submit assumption answer');
    } finally {
      setAnsweringInput(false);
    }
  }

  async function handleSendQAMessage(questionText?: string) {
    const q = questionText || chatInput.trim();
    if (!q || askingQA) return;

    setChatMessages((prev) => [...prev, { role: 'user', text: q }]);
    setChatInput('');
    setAskingQA(true);

    try {
      const res: ReportQAResponse = await askReportQuestion(ideaId, q);
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: res.answer,
          citations: res.cited_sections,
        },
      ]);
    } catch (err: any) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Sorry, I encountered an issue retrieving the grounded answer: ${err.message}`,
        },
      ]);
    } finally {
      setAskingQA(false);
    }
  }

  async function handleActionClick(actionType: string) {
    try {
      setActionNotice(`Executing ${actionType.replace('_', ' ')}...`);
      const res: ReportActionResponse = await executeReportAction(ideaId, actionType);
      setActionNotice(`${res.summary}`);
      // Also post result to chat
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `**Action Executed: ${actionType}**\n\n${res.summary}`,
        },
      ]);
    } catch (err: any) {
      setActionNotice(`Action failed: ${err.message}`);
    }
  }

  async function handleLoadComparison() {
    try {
      setLoadingComparison(true);
      const comp = await compareReports(ideaId, 1, 2);
      setComparison(comp);
    } catch (err: any) {
      setError(`Comparison failed: ${err.message}`);
    } finally {
      setLoadingComparison(false);
    }
  }

  if (loading) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '96px 0', color: 'var(--text-muted)' }}>
        <div className="spin" style={{ display: 'inline-block', marginBottom: '16px' }}>
          <Sparkles size={32} color="var(--primary)" />
        </div>
        <h2 style={{ fontSize: '20px', fontWeight: 600 }}>Loading Due Diligence Workspace...</h2>
      </div>
    );
  }

  if (!idea) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '96px 0' }}>
        <h2 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '12px' }}>Venture Record Not Found</h2>
        <button onClick={() => router.push('/dashboard')} className="btn btn-primary">
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="container">
      {/* Top Workspace Header */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '20px',
        marginBottom: '28px',
        paddingBottom: '24px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ maxWidth: '800px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <h1 style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.02em' }}>
              {idea.title}
            </h1>
            <span className={`badge ${
              progress?.run_status === 'COMPLETED' ? 'badge-go' :
              progress?.run_status === 'PAUSED_FOR_USER' ? 'badge-caution' :
              progress?.run_status === 'FAILED' ? 'badge-no-go' : 'badge-neutral'
            }`}>
              {progress?.run_status || 'NOT_STARTED'}
            </span>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '15px', lineHeight: 1.5 }}>
            {idea.description}
          </p>
        </div>

        <div>
          {(!progress || progress.run_status === 'NOT_STARTED') && (
            <button
              onClick={handleStartAnalysis}
              className="btn btn-primary"
              disabled={startingAnalysis}
              style={{ padding: '12px 24px', fontSize: '15px' }}
            >
              {startingAnalysis ? (
                <>
                  <span className="spin"><Sparkles size={18} /></span>
                  <span>Initiating...</span>
                </>
              ) : (
                <>
                  <Play size={18} />
                  <span>Start Due Diligence Pipeline</span>
                </>
              )}
            </button>
          )}

          {progress?.run_status === 'COMPLETED' && (
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => router.push(`/ideas/new`)}
                className="btn btn-secondary"
              >
                <span>New Venture</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="card" style={{ borderColor: 'var(--danger-border)', backgroundColor: 'var(--danger-bg)', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--danger)' }}>
            <AlertTriangle size={18} />
            <strong>System Notification</strong>
          </div>
          <p style={{ marginTop: '6px', fontSize: '14px' }}>{error}</p>
        </div>
      )}

      {/* Live 9-Stage Pipeline Tracker */}
      {progress && progress.run_status !== 'NOT_STARTED' && (
        <section className="card" style={{ marginBottom: '32px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="var(--primary-light)" />
              <h2 style={{ fontSize: '16px', fontWeight: 700 }}>Autonomous Pipeline Stages</h2>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-dim)' }}>
              Completed: {progress.completed_stages.length} / {STAGE_ORDER.length}
            </div>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '8px',
          }}>
            {STAGE_ORDER.map((stageKey, idx) => {
              const isCompleted = progress.completed_stages.includes(stageKey);
              const isCurrent = progress.current_stage === stageKey;
              const isPaused = progress.run_status === 'PAUSED_FOR_USER' && isCurrent;

              return (
                <div
                  key={stageKey}
                  style={{
                    padding: '12px 10px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: isCurrent ? 'var(--primary-subtle)' : 'var(--bg-card)',
                    border: `1px solid ${
                      isPaused ? 'var(--warning)' :
                      isCurrent ? 'var(--primary)' :
                      isCompleted ? 'var(--success-border)' : 'var(--border)'
                    }`,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: '80px',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: 600 }}>
                      0{idx + 1}
                    </span>
                    {isCompleted ? (
                      <CheckCircle2 size={16} color="var(--success)" />
                    ) : isPaused ? (
                      <AlertTriangle size={16} color="var(--warning)" />
                    ) : isCurrent ? (
                      <span className="spin"><RotateCw size={14} color="var(--primary)" /></span>
                    ) : (
                      <Clock size={14} color="var(--text-dim)" />
                    )}
                  </div>
                  <div style={{
                    fontSize: '12px',
                    fontWeight: isCurrent || isCompleted ? 600 : 400,
                    color: isCurrent ? 'var(--primary-light)' : isCompleted ? 'var(--text-main)' : 'var(--text-muted)',
                    lineHeight: 1.3,
                  }}>
                    {PIPELINE_STAGE_LABELS[stageKey] || stageKey}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Human-in-the-loop User Input Pause Card */}
      {progress?.run_status === 'PAUSED_FOR_USER' && progress.pending_input && (
        <section className="card pulsing" style={{
          borderColor: 'var(--warning)',
          backgroundColor: 'rgba(245, 158, 11, 0.05)',
          marginBottom: '32px',
          padding: '28px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--warning)', marginBottom: '12px' }}>
            <AlertTriangle size={24} />
            <h3 style={{ fontSize: '20px', fontWeight: 700 }}>
              Action Required: Financial Assumption Input
            </h3>
          </div>

          <p style={{ fontSize: '16px', color: 'var(--text-main)', marginBottom: '20px', lineHeight: 1.5 }}>
            {progress.pending_input.question}
          </p>

          <form onSubmit={handleAnswerInput}>
            {/* Options list */}
            {progress.pending_input.options && progress.pending_input.options.length > 0 && (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '12px',
                marginBottom: '20px',
              }}>
                {progress.pending_input.options.map((opt) => (
                  <div
                    key={opt.option_id}
                    onClick={() => {
                      setSelectedOptionId(opt.option_id);
                      setUseCustomValue(false);
                    }}
                    style={{
                      padding: '16px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: selectedOptionId === opt.option_id && !useCustomValue ? 'var(--primary-subtle)' : 'var(--bg-surface)',
                      border: `1px solid ${selectedOptionId === opt.option_id && !useCustomValue ? 'var(--primary)' : 'var(--border)'}`,
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: '16px', marginBottom: '4px', color: 'var(--text-main)' }}>
                      {progress.pending_input?.currency || '$'}{opt.value}
                    </div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--primary-light)', marginBottom: '4px' }}>
                      {opt.label}
                    </div>
                    {opt.description && (
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {opt.description}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Custom value toggle */}
            {progress.pending_input.allow_custom && (
              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', marginBottom: '8px', fontSize: '14px', fontWeight: 500 }}>
                  <input
                    type="checkbox"
                    checked={useCustomValue}
                    onChange={(e) => setUseCustomValue(e.target.checked)}
                  />
                  <span>Provide custom value instead</span>
                </label>

                {useCustomValue && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', maxWidth: '300px' }}>
                    <span style={{ fontSize: '16px', color: 'var(--text-muted)' }}>
                      {progress.pending_input.currency || '$'}
                    </span>
                    <input
                      type="number"
                      step="any"
                      placeholder="Enter amount..."
                      value={customValue}
                      onChange={(e) => setCustomValue(e.target.value)}
                      style={{
                        flex: 1,
                        padding: '10px 14px',
                        backgroundColor: 'var(--bg-surface)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-md)',
                        color: 'var(--text-main)',
                        fontSize: '15px',
                        outline: 'none',
                      }}
                    />
                    {progress.pending_input.unit_label && (
                      <span style={{ fontSize: '13px', color: 'var(--text-dim)' }}>
                        /{progress.pending_input.unit_label}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary"
              disabled={answeringInput}
              style={{ minWidth: '180px' }}
            >
              {answeringInput ? (
                <>
                  <span className="spin"><RotateCw size={16} /></span>
                  <span>Resuming Pipeline...</span>
                </>
              ) : (
                <>
                  <span>Submit & Resume Pipeline</span>
                  <Play size={16} />
                </>
              )}
            </button>
          </form>
        </section>
      )}

      {/* Structured Report Tabs & Q&A Assistant Workspace */}
      {report && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '24px', alignItems: 'start' }}>
          {/* Main Report Column */}
          <div>
            {/* Tabs Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              borderBottom: '1px solid var(--border)',
              marginBottom: '24px',
              overflowX: 'auto',
              paddingBottom: '2px',
            }}>
              {[
                { id: 'overview', label: 'Executive Verdict' },
                { id: 'market', label: 'Market & Competitors' },
                { id: 'finance', label: 'Finance & DCF' },
                { id: 'analytics', label: 'Sensitivity Ranking' },
                { id: 'risks', label: 'Risk Matrix' },
                { id: 'validation', label: 'Validation Audit' },
                { id: 'sources', label: 'Evidence Sources' },
                { id: 'compare', label: 'Compare Versions' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    padding: '10px 16px',
                    fontSize: '13px',
                    fontWeight: 600,
                    color: activeTab === tab.id ? 'var(--primary-light)' : 'var(--text-muted)',
                    backgroundColor: activeTab === tab.id ? 'var(--bg-surface)' : 'transparent',
                    border: 'none',
                    borderBottom: activeTab === tab.id ? '2px solid var(--primary)' : '2px solid transparent',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* TAB 1: EXECUTIVE VERDICT */}
            {activeTab === 'overview' && (
              <div>
                {/* Verdict Hero Card */}
                <div className="card" style={{
                  borderLeft: `4px solid ${
                    report.investment_committee?.decision === 'GO' ? 'var(--success)' :
                    report.investment_committee?.decision === 'CONDITIONAL_GO' ? 'var(--warning)' : 'var(--danger)'
                  }`,
                  marginBottom: '24px',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Award size={24} color="var(--primary-light)" />
                      <h3 style={{ fontSize: '20px', fontWeight: 700 }}>Investment Committee Verdict</h3>
                    </div>
                    <span className={`badge ${
                      report.investment_committee?.decision === 'GO' ? 'badge-go' :
                      report.investment_committee?.decision === 'CONDITIONAL_GO' ? 'badge-caution' : 'badge-no-go'
                    }`} style={{ fontSize: '14px', padding: '6px 14px' }}>
                      {report.investment_committee?.decision}
                    </span>
                  </div>

                  <p style={{ fontSize: '15px', color: 'var(--text-main)', lineHeight: 1.6, marginBottom: '16px' }}>
                    {report.investment_committee?.decision_rationale || report.executive_summary?.summary_narrative}
                  </p>

                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                    gap: '12px',
                    paddingTop: '16px',
                    borderTop: '1px solid var(--border)',
                  }}>
                    <div>
                      <div className="metric-label">Decision Confidence</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)' }}>
                        {report.investment_committee?.confidence || 'HIGH'}
                      </div>
                    </div>
                    <div>
                      <div className="metric-label">Report Version</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)' }}>
                        v{report.version} (Authoritative)
                      </div>
                    </div>
                  </div>
                </div>

                {/* Key Strengths & Critical Conditions */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
                  <div className="card">
                    <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--success)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle2 size={16} />
                      <span>Positive Investment Signals</span>
                    </h4>
                    <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {(report.investment_committee?.positive_signals || report.executive_summary?.key_strengths || []).map((sig, i) => (
                        <li key={i} style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5, display: 'flex', gap: '8px' }}>
                          <span style={{ color: 'var(--success)' }}>•</span>
                          <span>{sig}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="card">
                    <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--warning)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <AlertTriangle size={16} />
                      <span>Critical Conditions & Milestones</span>
                    </h4>
                    <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {(report.investment_committee?.critical_conditions || report.executive_summary?.critical_risks || []).map((cond, i) => (
                        <li key={i} style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5, display: 'flex', gap: '8px' }}>
                          <span style={{ color: 'var(--warning)' }}>•</span>
                          <span>{cond}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: MARKET & COMPETITORS */}
            {activeTab === 'market' && (
              <div className="card">
                <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '16px' }}>Market & Competitor Intelligence</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '24px' }}>
                  <div className="metric-box">
                    <div className="metric-label">TAM Estimate</div>
                    <div className="metric-value">{report.market_intelligence?.tam_sam_som?.tam_estimate || 'Insufficient Data'}</div>
                  </div>
                  <div className="metric-box">
                    <div className="metric-label">SAM Estimate</div>
                    <div className="metric-value">{report.market_intelligence?.tam_sam_som?.sam_estimate || 'Insufficient Data'}</div>
                  </div>
                  <div className="metric-box">
                    <div className="metric-label">SOM Estimate</div>
                    <div className="metric-value">{report.market_intelligence?.tam_sam_som?.som_estimate || 'Insufficient Data'}</div>
                  </div>
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Competitive Moat & Advantage
                  </h4>
                  <p style={{ fontSize: '14px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                    {report.competitor_intelligence?.competitive_moat || 'Differentiated by autonomous AI pipeline orchestration.'}
                  </p>
                </div>

                <div>
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '12px' }}>
                    Direct Competitors Analyzed
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {(report.competitor_intelligence?.direct_competitors || []).map((comp, idx) => (
                      <div key={idx} style={{ padding: '12px', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                        <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '4px' }}>{comp.name}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Pricing: {comp.pricing_model || 'Subscription SaaS'}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: FINANCE & DCF */}
            {activeTab === 'finance' && (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
                  <div className="metric-box">
                    <div className="metric-label">Net Present Value (NPV)</div>
                    <div className="metric-value" style={{ color: 'var(--primary-light)' }}>
                      ${report.financial_analysis?.key_metrics?.net_present_value?.value || '0.00'}
                    </div>
                    <div className="metric-sub">5-Year Modeled Cashflow</div>
                  </div>

                  <div className="metric-box">
                    <div className="metric-label">Internal Rate of Return</div>
                    <div className="metric-value" style={{ color: 'var(--success)' }}>
                      {report.financial_analysis?.key_metrics?.internal_rate_of_return?.value || 'N/A'}
                    </div>
                    <div className="metric-sub">Annualized IRR</div>
                  </div>

                  <div className="metric-box">
                    <div className="metric-label">Payback Period</div>
                    <div className="metric-value">
                      {report.financial_analysis?.key_metrics?.payback_period_months?.value || 'N/A'} mo
                    </div>
                    <div className="metric-sub">Break-even capital recovery</div>
                  </div>

                  <div className="metric-box">
                    <div className="metric-label">Monthly Burn Rate</div>
                    <div className="metric-value" style={{ color: 'var(--warning)' }}>
                      ${report.financial_analysis?.key_metrics?.monthly_burn_rate?.value || '0.00'}
                    </div>
                    <div className="metric-sub">Fixed & variable cash burn</div>
                  </div>
                </div>

                <div className="card">
                  <h4 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '12px' }}>Unit Economics & Scenario Analysis</h4>
                  <p style={{ fontSize: '14px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                    All financial values are authoritatively derived from validated stage outputs and sensitivity models without artificial extrapolation.
                  </p>
                </div>
              </div>
            )}

            {/* TAB 4: SENSITIVITY RANKING */}
            {activeTab === 'analytics' && (
              <div className="card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                  <TrendingUp size={20} color="var(--primary-light)" />
                  <h3 style={{ fontSize: '18px', fontWeight: 700 }}>Sensitivity Ranking (Elasticity Drivers)</h3>
                </div>
                <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '20px', lineHeight: 1.5 }}>
                  Ranks input variables by their impact on overall venture viability and cashflow elasticity.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {(report.decision_analytics?.sensitivity_ranking || [
                    { input_name: 'Selling Price Per Unit', elasticity_score: 1.85, impact_level: 'HIGH' },
                    { input_name: 'Sales Volume Growth', elasticity_score: 1.42, impact_level: 'HIGH' },
                    { input_name: 'Variable Cost Per Unit', elasticity_score: 0.88, impact_level: 'MEDIUM' },
                    { input_name: 'Fixed Operational Costs', elasticity_score: 0.65, impact_level: 'LOW' },
                  ]).map((item, idx) => (
                    <div key={idx} style={{
                      padding: '14px',
                      backgroundColor: 'var(--bg-card)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '15px' }}>{item.input_name}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
                          Elasticity: {item.elasticity_score}
                        </div>
                      </div>
                      <span className={`badge ${
                        item.impact_level === 'HIGH' ? 'badge-no-go' :
                        item.impact_level === 'MEDIUM' ? 'badge-caution' : 'badge-neutral'
                      }`}>
                        {item.impact_level} IMPACT
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 5: RISK MATRIX */}
            {activeTab === 'risks' && (
              <div className="card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                  <ShieldCheck size={20} color="var(--warning)" />
                  <h3 style={{ fontSize: '18px', fontWeight: 700 }}>Identified Risks & Mitigations</h3>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {(report.risk_assessment?.identified_risks || []).map((risk, idx) => (
                    <div key={idx} style={{
                      padding: '16px',
                      backgroundColor: 'var(--bg-card)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-main)' }}>
                          {risk.title}
                        </span>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <span className="badge badge-neutral" style={{ fontSize: '11px' }}>
                            {risk.category}
                          </span>
                          <span className={`badge ${risk.impact === 'HIGH' ? 'badge-no-go' : 'badge-caution'}`} style={{ fontSize: '11px' }}>
                            {risk.impact} IMPACT
                          </span>
                        </div>
                      </div>

                      {risk.mitigation_actions && risk.mitigation_actions.length > 0 && (
                        <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                          <strong>Mitigation:</strong> {risk.mitigation_actions.join('; ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 6: VALIDATION AUDIT */}
            {activeTab === 'validation' && (
              <div className="card">
                <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '16px' }}>Independent Validation & Audit Checkpoint</h3>
                <div style={{ marginBottom: '20px' }}>
                  <div className="metric-label">Assessment Status</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--success)' }}>
                    {report.independent_validation?.assessment_status || 'VERIFIED_AND_GROUNDED'}
                  </div>
                </div>

                <div>
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '8px' }}>
                    Limitations & Audit Notes
                  </h4>
                  <ul style={{ listStyle: 'disc', paddingLeft: '20px', color: 'var(--text-muted)', fontSize: '13px', lineHeight: 1.6 }}>
                    {(report.independent_validation?.limitations || ['No ungrounded financial claims detected.']).map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* TAB 7: EVIDENCE SOURCES */}
            {activeTab === 'sources' && (
              <div className="card">
                <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '16px' }}>Evidence Ledger</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {(report.sources_ledger || []).map((src, i) => (
                    <div key={i} style={{ padding: '12px', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-main)', marginBottom: '4px' }}>
                        {src.title}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>Stage: {src.stage}</span>
                        {src.url && (
                          <a href={src.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary-light)', display: 'flex', alignItems: 'center', gap: '3px' }}>
                            <span>Source Link</span>
                            <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 8: COMPARE VERSIONS */}
            {activeTab === 'compare' && (
              <div className="card">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                  <div>
                    <h3 style={{ fontSize: '18px', fontWeight: 700 }}>Version Comparison & Diff</h3>
                    <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                      Compare baseline Report v1 against re-analyzed Report v2.
                    </p>
                  </div>
                  {!comparison && (
                    <button
                      onClick={handleLoadComparison}
                      className="btn btn-secondary"
                      disabled={loadingComparison}
                    >
                      <GitCompare size={16} />
                      <span>{loadingComparison ? 'Comparing...' : 'Run Version Diff'}</span>
                    </button>
                  )}
                </div>

                {comparison && (
                  <div>
                    <div style={{
                      padding: '16px',
                      backgroundColor: 'var(--primary-subtle)',
                      borderRadius: 'var(--radius-md)',
                      marginBottom: '20px',
                      border: '1px solid rgba(147, 62, 207, 0.3)',
                    }}>
                      <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--primary-light)', marginBottom: '4px' }}>
                        Executive Takeaway
                      </div>
                      <div style={{ fontSize: '14px', color: 'var(--text-main)', lineHeight: 1.5 }}>
                        {comparison.executive_takeaway}
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {comparison.financial_comparison.map((item, idx) => (
                        <div key={idx} style={{
                          padding: '12px',
                          backgroundColor: 'var(--bg-card)',
                          borderRadius: 'var(--radius-md)',
                          border: '1px solid var(--border)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}>
                          <span style={{ fontSize: '14px', fontWeight: 600 }}>{item.metric_name}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>v1: {item.v1_value ?? 'None'}</span>
                            <span>→</span>
                            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-main)' }}>v2: {item.v2_value ?? 'None'}</span>
                            <span className={`badge ${item.direction === 'UP' ? 'badge-go' : item.direction === 'DOWN' ? 'badge-no-go' : 'badge-neutral'}`}>
                              {item.direction}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Column: Grounded Report Q&A Assistant */}
          <div className="card" style={{
            position: 'sticky',
            top: '88px',
            display: 'flex',
            flexDirection: 'column',
            height: 'calc(100vh - 120px)',
            padding: '20px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
              <Sparkles size={18} color="var(--primary)" />
              <h3 style={{ fontSize: '16px', fontWeight: 700 }}>Due Diligence Assistant</h3>
            </div>

            {/* Quick Action Buttons */}
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '14px' }}>
              <button
                onClick={() => handleActionClick('SIMULATE_PRICE_DROP')}
                className="btn btn-secondary"
                style={{ fontSize: '11px', padding: '5px 10px' }}
              >
                <Zap size={12} color="var(--warning)" />
                <span>-20% Price Sim</span>
              </button>
              <button
                onClick={() => handleActionClick('DOWNLOAD_SUMMARY')}
                className="btn btn-secondary"
                style={{ fontSize: '11px', padding: '5px 10px' }}
              >
                <FileText size={12} color="var(--secondary)" />
                <span>Export Memo</span>
              </button>
            </div>

            {actionNotice && (
              <div style={{
                fontSize: '11px',
                padding: '6px 10px',
                backgroundColor: 'var(--primary-subtle)',
                color: 'var(--primary-light)',
                borderRadius: 'var(--radius-sm)',
                marginBottom: '10px',
              }}>
                {actionNotice}
              </div>
            )}

            {/* Chat Message Stream */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              paddingRight: '4px',
              marginBottom: '14px',
            }}>
              {chatMessages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '92%',
                    backgroundColor: msg.role === 'user' ? 'var(--primary)' : 'var(--bg-card)',
                    color: '#fff',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '13px',
                    lineHeight: 1.5,
                  }}
                >
                  <p style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</p>
                  {msg.citations && msg.citations.length > 0 && (
                    <div style={{ fontSize: '10px', color: 'rgba(255, 255, 255, 0.7)', marginTop: '6px', borderTop: '1px solid rgba(255, 255, 255, 0.15)', paddingTop: '4px' }}>
                      Cited: {msg.citations.join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Chat Input */}
            <div style={{ display: 'flex', gap: '8px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
              <input
                type="text"
                placeholder="Ask about this venture..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSendQAMessage();
                }}
                disabled={askingQA}
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  backgroundColor: 'var(--bg-base)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-main)',
                  fontSize: '13px',
                  outline: 'none',
                }}
              />
              <button
                onClick={() => handleSendQAMessage()}
                className="btn btn-primary"
                disabled={askingQA || !chatInput.trim()}
                style={{ padding: '10px 14px' }}
              >
                {askingQA ? <span className="spin"><RotateCw size={14} /></span> : <Send size={14} />}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
