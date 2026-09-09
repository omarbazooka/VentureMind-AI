'use client';

import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileText,
  Play,
  RotateCw,
  Send,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

import {
  AnalysisProgressResponse,
  ChatMessage,
  IdeaItem,
  IdeaProfile,
  ReportActionRequest,
  StructuredReport,
  answerPendingInput,
  executeReportAction,
  getAnalysisProgress,
  getIdea,
  getMessages,
  getProfile,
  getReport,
  sendMessage,
  startAnalysis,
} from '@/lib/api';

const STAGES = [
  ['MARKET_RESEARCH', 'Market'],
  ['COMPETITOR_INTELLIGENCE', 'Competitors'],
  ['CUSTOMER_INTELLIGENCE', 'Customers'],
  ['BUSINESS_STRATEGY', 'Strategy'],
  ['FINANCE', 'Finance'],
  ['DECISION_ANALYTICS', 'Analytics'],
  ['RISK', 'Risk'],
  ['INDEPENDENT_VALIDATION', 'Validation'],
  ['INVESTMENT_COMMITTEE', 'Final Decision'],
] as const;

const REPORT_TABS = [
  'overview',
  'market',
  'competitors',
  'customers',
  'strategy',
  'finance',
  'analytics',
  'risk',
  'validation',
  'sources',
] as const;

type ReportTab = (typeof REPORT_TABS)[number];

function humanize(value: string) {
  return value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not provided';
  if (Array.isArray(value)) return value.map(displayValue).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function metricValue(
  scenario: StructuredReport['finance']['base_scenario'],
  metricName: string,
): string {
  const metric = scenario.metrics.find((item) => item.metric_name === metricName);
  if (!metric) return 'Unavailable';
  const suffix = [metric.currency, metric.period ? `/ ${humanize(metric.period)}` : null]
    .filter(Boolean)
    .join(' ');
  return `${metric.value}${suffix ? ` ${suffix}` : ''}`;
}

function findingText(item: Record<string, any>) {
  return item.statement || item.relevance_summary || item.title || JSON.stringify(item);
}

function currentStageStatus(progress: AnalysisProgressResponse | null, stage: string) {
  if (!progress) return 'PENDING';
  const candidates = progress.stage_runs.filter((item) => item.stage === stage);
  if (!candidates.length) return 'PENDING';
  return candidates[candidates.length - 1].status;
}

export default function IdeaWorkspacePage() {
  const params = useParams();
  const ideaId = params.ideaId as string;

  const [idea, setIdea] = useState<IdeaItem | null>(null);
  const [profile, setProfile] = useState<IdeaProfile | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [progress, setProgress] = useState<AnalysisProgressResponse | null>(null);
  const [report, setReport] = useState<StructuredReport | null>(null);
  const [activeTab, setActiveTab] = useState<ReportTab>('overview');
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const [starting, setStarting] = useState(false);
  const [answering, setAnswering] = useState(false);
  const [selectedOption, setSelectedOption] = useState('');
  const [customValue, setCustomValue] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  const [actionOutput, setActionOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const readyForAnalysis = profile?.readiness === 'READY_FOR_ANALYSIS';
  const analysisActive = progress && ['QUEUED', 'RUNNING', 'PAUSED_FOR_USER'].includes(progress.run_status);

  const profileEntries = useMemo(
    () => Object.entries(profile?.profile_data || {}),
    [profile],
  );

  useEffect(() => {
    void loadWorkspace();
  }, [ideaId]);

  useEffect(() => {
    if (!analysisActive || progress?.run_status === 'PAUSED_FOR_USER') return;
    const timer = window.setInterval(() => void refreshProgress(), 2500);
    return () => window.clearInterval(timer);
  }, [analysisActive, progress?.run_status]);

  async function loadWorkspace() {
    setLoading(true);
    setError(null);
    try {
      const [ideaData, profileData, messageData, progressData] = await Promise.all([
        getIdea(ideaId),
        getProfile(ideaId),
        getMessages(ideaId),
        getAnalysisProgress(ideaId),
      ]);
      setIdea(ideaData);
      setProfile(profileData);
      setMessages(messageData);
      setProgress(progressData);
      if (progressData.has_report) {
        setReport(await getReport(ideaId));
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load this idea workspace.');
    } finally {
      setLoading(false);
    }
  }

  async function refreshProgress() {
    try {
      const next = await getAnalysisProgress(ideaId);
      setProgress(next);
      if (next.has_report && !report) {
        setReport(await getReport(ideaId));
      }
    } catch (err: any) {
      setError(err.message || 'Failed to refresh analysis progress.');
    }
  }

  async function refreshProfile() {
    setProfile(await getProfile(ideaId));
  }

  async function handleChatSubmit(event: FormEvent) {
    event.preventDefault();
    const content = chatInput.trim();
    if (!content || sending) return;

    setSending(true);
    setError(null);
    try {
      const turn = await sendMessage(ideaId, content);
      setMessages((previous) => [
        ...previous,
        turn.user_message,
        turn.assistant_message,
      ]);
      setChatInput('');
      await refreshProfile();
    } catch (err: any) {
      setError(err.message || 'Chat request failed.');
    } finally {
      setSending(false);
    }
  }

  async function handleStartAnalysis() {
    if (!readyForAnalysis) return;
    setStarting(true);
    setError(null);
    try {
      await startAnalysis(ideaId);
      await refreshProgress();
    } catch (err: any) {
      setError(err.message || 'Could not start analysis.');
    } finally {
      setStarting(false);
    }
  }

  async function handleFinanceAnswer(event: FormEvent) {
    event.preventDefault();
    const pending = progress?.pending_input;
    if (!pending) return;

    setAnswering(true);
    setError(null);
    try {
      if (useCustom) {
        const numericValue = Number(customValue);
        if (!Number.isFinite(numericValue) || numericValue < 0) {
          throw new Error('Enter a valid non-negative numeric value.');
        }
        await answerPendingInput(ideaId, pending.input_id, {
          value: numericValue,
          currency: pending.currency || undefined,
          unit_label: pending.unit_label || undefined,
          period: pending.period || undefined,
        });
      } else {
        if (!selectedOption) throw new Error('Select an option or choose custom value.');
        await answerPendingInput(ideaId, pending.input_id, { choice: selectedOption });
      }
      setSelectedOption('');
      setCustomValue('');
      setUseCustom(false);
      await refreshProgress();
    } catch (err: any) {
      setError(err.message || 'Could not submit Finance input.');
    } finally {
      setAnswering(false);
    }
  }

  async function runReportAction(request: ReportActionRequest) {
    setActionOutput('Loading grounded report data...');
    try {
      const response = await executeReportAction(ideaId, request);
      setActionOutput(`${response.title}\n\n${response.content}`);
    } catch (err: any) {
      setActionOutput(`Action failed: ${err.message}`);
    }
  }

  if (loading) {
    return (
      <div className="container" style={{ padding: '80px 0', textAlign: 'center' }}>
        <span className="spin"><Sparkles size={28} /></span>
        <p style={{ color: 'var(--text-muted)', marginTop: 12 }}>Loading idea workspace…</p>
      </div>
    );
  }

  if (!idea) {
    return <div className="container"><p>Idea not found.</p></div>;
  }

  return (
    <div className="container" style={{ paddingBottom: 48 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: 20, alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <div style={{ color: 'var(--primary-light)', fontSize: 12, fontWeight: 700, textTransform: 'uppercase' }}>Idea Workspace</div>
          <h1 style={{ fontSize: 30, marginTop: 6 }}>{idea.title}</h1>
          <p style={{ color: 'var(--text-muted)', maxWidth: 760, marginTop: 8 }}>{idea.description}</p>
        </div>
        <span className="badge badge-neutral">{progress?.run_status || 'NOT_STARTED'}</span>
      </header>

      {error && (
        <div className="card" style={{ borderColor: 'var(--danger-border)', marginBottom: 20 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--danger)' }}>
            <AlertTriangle size={18} />
            <strong>{error}</strong>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.35fr) minmax(320px, .65fr)', gap: 20, alignItems: 'start' }}>
        <main>
          <section className="card" style={{ minHeight: 420, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--border)', paddingBottom: 14 }}>
              <Sparkles size={18} color="var(--primary-light)" />
              <div>
                <strong>Chat AI</strong>
                <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>Grounded in this idea, its profile, and available analysis state.</div>
              </div>
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, padding: '18px 0', maxHeight: 520, overflowY: 'auto' }}>
              {messages.length === 0 && (
                <div style={{ color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.6 }}>
                  Describe the customer, problem, geography, business model, pricing, or anything else you already know. VentureMind will update the structured Idea Profile and ask the highest-value clarification when needed.
                </div>
              )}
              {messages.map((message) => (
                <div
                  key={message.id}
                  style={{
                    alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '86%',
                    padding: '10px 13px',
                    borderRadius: 12,
                    whiteSpace: 'pre-wrap',
                    background: message.role === 'user' ? 'var(--primary)' : 'var(--bg-card)',
                    border: message.role === 'user' ? 'none' : '1px solid var(--border)',
                    fontSize: 14,
                    lineHeight: 1.55,
                  }}
                >
                  {message.content}
                </div>
              ))}
            </div>

            <form onSubmit={handleChatSubmit} style={{ display: 'flex', gap: 8, borderTop: '1px solid var(--border)', paddingTop: 14 }}>
              <input
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder={report ? 'Ask about the report, evidence, finance, or risks…' : 'Tell VentureMind more about the idea…'}
                disabled={sending}
                style={{ flex: 1, padding: '11px 13px', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-main)' }}
              />
              <button className="btn btn-primary" disabled={sending || !chatInput.trim()}>
                {sending ? <span className="spin"><RotateCw size={15} /></span> : <Send size={15} />}
              </button>
            </form>
          </section>

          {progress?.run_status === 'PAUSED_FOR_USER' && progress.pending_input && (
            <section className="card" style={{ marginTop: 20, borderColor: 'var(--warning)' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--warning)' }}>
                <AlertTriangle size={20} />
                <h2 style={{ fontSize: 18 }}>Finance needs one decision-critical input</h2>
              </div>
              <p style={{ margin: '12px 0 18px', color: 'var(--text-muted)' }}>{progress.pending_input.question}</p>
              <form onSubmit={handleFinanceAnswer}>
                {!!progress.pending_input.options.length && (
                  <div style={{ display: 'grid', gap: 8, marginBottom: 14 }}>
                    {progress.pending_input.options.map((option) => (
                      <label key={option.option_id} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: 12, border: '1px solid var(--border)', borderRadius: 10, cursor: 'pointer' }}>
                        <input
                          type="radio"
                          name="finance-option"
                          checked={!useCustom && selectedOption === option.option_id}
                          onChange={() => { setUseCustom(false); setSelectedOption(option.option_id); }}
                        />
                        <span>
                          <strong>{option.label}</strong>
                          <span style={{ display: 'block', color: 'var(--text-muted)', fontSize: 13, marginTop: 3 }}>
                            {displayValue(option.value)} {option.currency || progress.pending_input?.currency || ''} {option.unit_label ? `/ ${option.unit_label}` : ''}
                          </span>
                          {option.rationale && <span style={{ display: 'block', color: 'var(--text-dim)', fontSize: 12, marginTop: 4 }}>{option.rationale}</span>}
                        </span>
                      </label>
                    ))}
                  </div>
                )}
                {progress.pending_input.allow_custom && (
                  <div style={{ marginBottom: 14 }}>
                    <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                      <input type="checkbox" checked={useCustom} onChange={(event) => setUseCustom(event.target.checked)} />
                      Use a custom value
                    </label>
                    {useCustom && (
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={customValue}
                        onChange={(event) => setCustomValue(event.target.value)}
                        placeholder="Enter value"
                        style={{ width: '100%', padding: '10px 12px', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-main)' }}
                      />
                    )}
                  </div>
                )}
                <button className="btn btn-primary" disabled={answering}>
                  {answering ? <span className="spin"><RotateCw size={15} /></span> : <Play size={15} />}
                  Submit & Resume
                </button>
              </form>
            </section>
          )}

          {report && (
            <section style={{ marginTop: 20 }}>
              <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 10 }}>
                {REPORT_TABS.map((tab) => (
                  <button
                    key={tab}
                    className={activeTab === tab ? 'btn btn-primary' : 'btn btn-secondary'}
                    onClick={() => setActiveTab(tab)}
                    style={{ whiteSpace: 'nowrap', fontSize: 12 }}
                  >
                    {humanize(tab)}
                  </button>
                ))}
              </div>

              <div className="card">
                {activeTab === 'overview' && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center' }}>
                      <div>
                        <div className="metric-label">Final Decision</div>
                        <h2 style={{ fontSize: 28, marginTop: 6 }}>{report.decision.decision}</h2>
                      </div>
                      <span className="badge badge-neutral">Confidence: {report.decision.confidence}</span>
                    </div>
                    <p style={{ color: 'var(--text-muted)', lineHeight: 1.65, marginTop: 16 }}>{report.decision.rationale}</p>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18, marginTop: 22 }}>
                      <div>
                        <h3 style={{ fontSize: 14, marginBottom: 8 }}>Positive signals</h3>
                        {report.decision.strongest_positive_signals.length ? report.decision.strongest_positive_signals.map((item) => <p key={item} style={{ color: 'var(--text-muted)', marginBottom: 6 }}>• {item}</p>) : <p style={{ color: 'var(--text-dim)' }}>None recorded.</p>}
                      </div>
                      <div>
                        <h3 style={{ fontSize: 14, marginBottom: 8 }}>Negative signals</h3>
                        {report.decision.strongest_negative_signals.length ? report.decision.strongest_negative_signals.map((item) => <p key={item} style={{ color: 'var(--text-muted)', marginBottom: 6 }}>• {item}</p>) : <p style={{ color: 'var(--text-dim)' }}>None recorded.</p>}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === 'market' && (
                  <div>
                    <h2 style={{ marginBottom: 8 }}>Market Intelligence</h2>
                    <p style={{ color: 'var(--text-muted)', lineHeight: 1.6 }}>{report.market.summary}</p>
                    <p style={{ marginTop: 10, fontSize: 13 }}>Evidence quality: <strong>{report.market.evidence_quality}</strong></p>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 18 }}>
                      {(['tam', 'sam', 'som'] as const).map((name) => {
                        const metric = report.market.market_metrics[name];
                        return <div className="metric-box" key={name}><div className="metric-label">{name.toUpperCase()}</div><div className="metric-value">{metric.value || humanize(metric.status)}</div>{metric.explanation && <div className="metric-sub">{metric.explanation}</div>}</div>;
                      })}
                    </div>
                    <div style={{ marginTop: 18 }}>{report.market.findings.map((item, index) => <p key={index} style={{ color: 'var(--text-muted)', marginBottom: 8 }}>• {findingText(item)}</p>)}</div>
                  </div>
                )}

                {activeTab === 'competitors' && (
                  <div>
                    <h2>Competitor Intelligence</h2>
                    <p style={{ color: 'var(--text-muted)', lineHeight: 1.6, margin: '8px 0 16px' }}>{report.competitors.summary}</p>
                    {report.competitors.competitors.map((competitor, index) => (
                      <div key={index} style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 10, marginBottom: 8 }}>
                        <strong>{competitor.name || `Competitor ${index + 1}`}</strong>
                        {competitor.relationship && <span style={{ marginLeft: 8, color: 'var(--text-dim)', fontSize: 12 }}>{competitor.relationship}</span>}
                        {competitor.relevance_summary && <p style={{ color: 'var(--text-muted)', marginTop: 6 }}>{competitor.relevance_summary}</p>}
                        {competitor.pricing?.statement && <p style={{ color: 'var(--text-muted)', marginTop: 6 }}>Pricing evidence: {competitor.pricing.statement}</p>}
                      </div>
                    ))}
                  </div>
                )}

                {activeTab === 'customers' && (
                  <div>
                    <h2>Customer Intelligence</h2>
                    <p style={{ color: 'var(--text-muted)', lineHeight: 1.6, margin: '8px 0 16px' }}>{report.customer.summary}</p>
                    {report.customer.findings.map((item, index) => <p key={index} style={{ color: 'var(--text-muted)', marginBottom: 8 }}>• {findingText(item)}</p>)}
                  </div>
                )}

                {activeTab === 'strategy' && (
                  <div>
                    <h2>Business Strategy</h2>
                    <p style={{ color: 'var(--text-muted)', lineHeight: 1.6, marginTop: 8 }}>{report.strategy.executive_summary}</p>
                    <h3 style={{ fontSize: 14, margin: '18px 0 8px' }}>Go-to-market implications</h3>
                    {report.strategy.go_to_market.map((item, index) => <p key={index} style={{ color: 'var(--text-muted)', marginBottom: 8 }}>• {findingText(item)}</p>)}
                  </div>
                )}

                {activeTab === 'finance' && (
                  <div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}><BarChart3 size={18} /><h2>Deterministic Finance</h2></div>
                    <p style={{ color: 'var(--text-muted)', lineHeight: 1.6 }}>{report.finance.executive_summary}</p>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 18 }}>
                      {[report.finance.base_scenario, report.finance.upside_scenario, report.finance.downside_scenario].map((scenario) => (
                        <div className="metric-box" key={scenario.scenario}>
                          <div className="metric-label">{scenario.scenario}</div>
                          <div style={{ marginTop: 8 }}>Revenue: <strong>{metricValue(scenario, 'REVENUE')}</strong></div>
                          <div style={{ marginTop: 6 }}>Operating result: <strong>{metricValue(scenario, 'OPERATING_RESULT')}</strong></div>
                          <div style={{ marginTop: 6 }}>Break-even: <strong>{metricValue(scenario, 'BREAK_EVEN_UNITS')}</strong></div>
                        </div>
                      ))}
                    </div>
                    {!!report.finance.limitations.length && <div style={{ marginTop: 18, color: 'var(--text-dim)' }}>Limitations: {report.finance.limitations.join(' • ')}</div>}
                  </div>
                )}

                {activeTab === 'analytics' && (
                  <div>
                    <h2>Decision Analytics</h2>
                    {report.chart_data.sensitivity_ranking.length ? report.chart_data.sensitivity_ranking.map((item, index) => (
                      <div key={index} style={{ padding: 12, borderBottom: '1px solid var(--border)' }}>
                        <strong>#{item.rank ?? index + 1} {humanize(String(item.input_name || 'input'))}</strong>
                        <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>Max modeled impact: {item.max_abs_ranking_metric_change_percent ?? 'Unavailable'}%</div>
                      </div>
                    )) : <p style={{ color: 'var(--text-dim)' }}>No authoritative sensitivity ranking is available.</p>}
                  </div>
                )}

                {activeTab === 'risk' && (
                  <div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><ShieldCheck size={18} /><h2>Risk Analysis</h2></div>
                    <p style={{ color: 'var(--text-muted)', margin: '8px 0 16px' }}>{report.risk.executive_summary}</p>
                    {report.risk.risks.map((risk, index) => (
                      <div key={index} style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 10, marginBottom: 8 }}>
                        <strong>{risk.title || `Risk ${index + 1}`}</strong>
                        <div style={{ color: 'var(--text-dim)', fontSize: 12, marginTop: 4 }}>{risk.category} • likelihood {risk.likelihood} • impact {risk.impact} • level {risk.risk_level}</div>
                        {risk.statement && <p style={{ color: 'var(--text-muted)', marginTop: 6 }}>{risk.statement}</p>}
                        {!!risk.mitigation_actions?.length && <p style={{ color: 'var(--text-muted)', marginTop: 6 }}>Mitigation: {risk.mitigation_actions.join('; ')}</p>}
                      </div>
                    ))}
                  </div>
                )}

                {activeTab === 'validation' && (
                  <div>
                    <h2>Independent Validation</h2>
                    <p style={{ marginTop: 8 }}>Status: <strong>{report.validation.status}</strong></p>
                    <p style={{ color: 'var(--text-muted)', lineHeight: 1.6, marginTop: 10 }}>{report.validation.executive_assessment}</p>
                    {report.validation.issues.map((issue, index) => <p key={index} style={{ color: 'var(--text-muted)', marginTop: 8 }}>• {findingText(issue)}</p>)}
                    {!!report.validation.limitations.length && <p style={{ color: 'var(--text-dim)', marginTop: 14 }}>Limitations: {report.validation.limitations.join(' • ')}</p>}
                  </div>
                )}

                {activeTab === 'sources' && (
                  <div>
                    <h2>Evidence Sources</h2>
                    {report.sources.length ? report.sources.map((source) => (
                      <div key={source.source_id} style={{ padding: 12, borderBottom: '1px solid var(--border)' }}>
                        <strong>{source.title}</strong>
                        <div style={{ color: 'var(--text-dim)', fontSize: 12, marginTop: 4 }}>{source.provenance} • {humanize(source.stage)}</div>
                        {source.url && <a href={source.url} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', gap: 4, alignItems: 'center', marginTop: 6, color: 'var(--primary-light)' }}>Open source <ExternalLink size={12} /></a>}
                      </div>
                    )) : <p style={{ color: 'var(--text-dim)' }}>No persisted web sources are available for this report.</p>}
                  </div>
                )}
              </div>

              <div className="card" style={{ marginTop: 12 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  <button className="btn btn-secondary" onClick={() => void runReportAction({ action: 'CHALLENGE_CONCLUSION' })}>Challenge Conclusion</button>
                  <button className="btn btn-secondary" onClick={() => void runReportAction({ action: 'WHAT_COULD_CHANGE' })}>What Could Change?</button>
                  <button className="btn btn-secondary" onClick={() => void runReportAction({ action: 'EXPLAIN_CALCULATION', target_metric: 'break_even' })}>Explain Break-Even</button>
                  <button className="btn btn-secondary" onClick={() => void runReportAction({ action: 'SHOW_SOURCES' })}><FileText size={14} /> Sources</button>
                </div>
                {actionOutput && <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', color: 'var(--text-muted)', marginTop: 14, lineHeight: 1.55 }}>{actionOutput}</pre>}
              </div>
            </section>
          )}
        </main>

        <aside style={{ position: 'sticky', top: 88 }}>
          {!analysisActive && !report && (
            <section className="card">
              <h2 style={{ fontSize: 17 }}>Idea Profile</h2>
              <div style={{ marginTop: 8, fontSize: 13, color: readyForAnalysis ? 'var(--success)' : 'var(--warning)' }}>
                {readyForAnalysis ? 'READY FOR ANALYSIS' : humanize(profile?.readiness || 'NOT_READY')}
              </div>
              <div style={{ marginTop: 16, display: 'grid', gap: 10 }}>
                {profileEntries.length ? profileEntries.map(([key, value]) => (
                  <div key={key} style={{ paddingBottom: 9, borderBottom: '1px solid var(--border)' }}>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase' }}>{humanize(key)}</div>
                    <div style={{ fontSize: 13, marginTop: 3 }}>{displayValue(value)}</div>
                  </div>
                )) : <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>The profile is still empty. Continue the conversation.</p>}
              </div>
              {!!profile?.unknown_fields.length && <p style={{ marginTop: 14, color: 'var(--text-dim)', fontSize: 12 }}>Still unknown: {profile.unknown_fields.map(humanize).join(', ')}</p>}
              <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', marginTop: 18 }} disabled={!readyForAnalysis || starting} onClick={handleStartAnalysis}>
                {starting ? <span className="spin"><RotateCw size={15} /></span> : <Play size={15} />}
                Start Analysis
              </button>
              {!readyForAnalysis && <p style={{ color: 'var(--text-dim)', fontSize: 12, marginTop: 8 }}>Analysis starts only after the authoritative profile reaches READY_FOR_ANALYSIS.</p>}
            </section>
          )}

          {analysisActive && (
            <section className="card">
              <h2 style={{ fontSize: 17 }}>Analysis Progress</h2>
              <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>Live backend stage state — no timer simulation.</p>
              <div style={{ display: 'grid', gap: 8, marginTop: 16 }}>
                {STAGES.map(([stage, label]) => {
                  const status = currentStageStatus(progress, stage);
                  return (
                    <div key={stage} style={{ display: 'flex', gap: 9, alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                      {status === 'COMPLETED' ? <CheckCircle2 size={15} color="var(--success)" /> : status === 'RUNNING' ? <span className="spin"><RotateCw size={15} /></span> : status === 'PAUSED_FOR_USER' ? <AlertTriangle size={15} color="var(--warning)" /> : <Clock size={15} color="var(--text-dim)" />}
                      <div style={{ flex: 1 }}><div style={{ fontSize: 13 }}>{label}</div><div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{status}</div></div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {report && (
            <section className="card">
              <h2 style={{ fontSize: 17 }}>Report Ready</h2>
              <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 8 }}>Version {report.version} • {report.decision.decision} • {report.decision.confidence} confidence</p>
              <p style={{ color: 'var(--text-dim)', fontSize: 12, marginTop: 10 }}>Use the same Chat AI to ask grounded follow-up questions. Explicit report actions are available below the report.</p>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
