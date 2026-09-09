'use client';

import Link from 'next/link';
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  FileText,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react';

const analysisAreas = [
  ['Market', Search, 'Researches market signals and constraints with explicit evidence quality.'],
  ['Competitors', Users, 'Maps direct, indirect, and substitute alternatives using grounded sources.'],
  ['Customers', Users, 'Examines customer segments, pain points, alternatives, objections, and demand signals.'],
  ['Strategy', Sparkles, 'Synthesizes positioning, value proposition, business model implications, and go-to-market.'],
  ['Finance', BarChart3, 'Builds deterministic Base, Upside, and Downside calculations from explicit assumptions.'],
  ['Risk & Decision', ShieldCheck, 'Scores grounded risks, independently validates the packet, then produces a bounded final decision.'],
];

export default function HomePage() {
  return (
    <main>
      <section className="container" style={{ padding: '72px 0 56px', textAlign: 'center' }}>
        <div style={{ display: 'inline-flex', gap: 8, alignItems: 'center', padding: '7px 14px', borderRadius: 999, border: '1px solid rgba(147, 62, 207, .35)', background: 'var(--primary-subtle)', color: 'var(--primary-light)', fontSize: 13, fontWeight: 600 }}>
          <Sparkles size={15} />
          Evidence-aware business validation & decision intelligence
        </div>

        <h1 style={{ maxWidth: 900, margin: '24px auto 0', fontSize: 52, lineHeight: 1.08, letterSpacing: '-.035em' }}>
          Validate your business idea before betting everything on it.
        </h1>

        <p style={{ maxWidth: 760, margin: '20px auto 0', color: 'var(--text-muted)', fontSize: 18, lineHeight: 1.65 }}>
          VentureMind turns a conversation about your idea into a structured profile, researches the market, competitors and customers, evaluates strategy and economics, audits the evidence, and produces an interactive decision report.
        </p>

        <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 30, flexWrap: 'wrap' }}>
          <Link href="/ideas/new" className="btn btn-primary" style={{ padding: '13px 22px' }}>
            Validate My Idea <ArrowRight size={17} />
          </Link>
          <Link href="/dashboard" className="btn btn-secondary" style={{ padding: '13px 22px' }}>
            View Ideas
          </Link>
        </div>
      </section>

      <section className="container" style={{ paddingBottom: 64 }}>
        <div className="card" style={{ padding: 26 }}>
          <div style={{ fontSize: 12, color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 700, marginBottom: 14 }}>How it works</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
            {['Describe Idea', 'AI Clarification', 'Idea Profile', 'Research', 'Strategy', 'Finance', 'Analytics', 'Risk', 'Validation', 'Final Decision', 'Interactive Report'].map((step, index) => (
              <div key={step} style={{ padding: 12, borderRadius: 10, border: '1px solid var(--border)', background: 'var(--bg-card)' }}>
                <div style={{ color: 'var(--text-dim)', fontSize: 11 }}>{String(index + 1).padStart(2, '0')}</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginTop: 5 }}>{step}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container" style={{ paddingBottom: 72 }}>
        <div style={{ textAlign: 'center', marginBottom: 26 }}>
          <div style={{ color: 'var(--primary-light)', fontSize: 12, fontWeight: 700, textTransform: 'uppercase' }}>What VentureMind analyzes</div>
          <h2 style={{ fontSize: 30, marginTop: 7 }}>One grounded decision packet, not disconnected AI answers.</h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
          {analysisAreas.map(([title, Icon, description]) => (
            <div className="card" key={String(title)}>
              <Icon size={21} color="var(--primary-light)" />
              <h3 style={{ fontSize: 17, marginTop: 13 }}>{String(title)}</h3>
              <p style={{ color: 'var(--text-muted)', lineHeight: 1.6, marginTop: 7, fontSize: 14 }}>{String(description)}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="container" style={{ paddingBottom: 80 }}>
        <div className="card" style={{ display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'center', gap: 24, padding: 30 }}>
          <div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--success)', fontSize: 13, fontWeight: 700 }}>
              <CheckCircle2 size={16} />
              Built to admit uncertainty
            </div>
            <h2 style={{ fontSize: 25, marginTop: 8 }}>Weak evidence lowers confidence instead of becoming a fake number.</h2>
            <p style={{ color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.6 }}>
              The structured report preserves evidence sources, assumptions, deterministic calculations, limitations, risks, and the conditions that could change the conclusion.
            </p>
          </div>
          <FileText size={42} color="var(--primary-light)" />
        </div>
      </section>
    </main>
  );
}
