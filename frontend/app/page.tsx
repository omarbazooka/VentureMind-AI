'use client';

import React from 'react';
import Link from 'next/link';
import {
  Sparkles,
  ArrowRight,
  TrendingUp,
  ShieldAlert,
  BarChart3,
  CheckCircle2,
  Cpu,
  Layers,
  FileText
} from 'lucide-react';

export default function HomePage() {
  return (
    <div className="container">
      {/* Hero Section */}
      <section style={{
        textAlign: 'center',
        padding: '60px 0 80px 0',
        maxWidth: '860px',
        margin: '0 auto',
      }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 16px',
          borderRadius: '9999px',
          backgroundColor: 'var(--primary-subtle)',
          border: '1px solid rgba(147, 62, 207, 0.3)',
          color: 'var(--primary-light)',
          fontSize: '13px',
          fontWeight: 600,
          marginBottom: '24px',
        }}>
          <Sparkles size={16} />
          <span>Autonomous Venture Capital Due Diligence Platform</span>
        </div>

        <h1 style={{
          fontSize: '48px',
          fontWeight: 800,
          letterSpacing: '-0.03em',
          lineHeight: 1.15,
          marginBottom: '20px',
        }}>
          Institutional-Grade <span style={{
            background: 'linear-gradient(135deg, #c084fc 0%, #933ecf 50%, #3b82f6 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>AI Due Diligence</span> & Investment Committee Intelligence
        </h1>

        <p style={{
          fontSize: '18px',
          color: 'var(--text-muted)',
          lineHeight: 1.6,
          marginBottom: '36px',
        }}>
          Transform startup ideas into comprehensive investment memos in minutes.
          Powered by multi-agent crews, deterministic research joins, financial sensitivity modeling,
          and adversarial audit validation.
        </p>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px' }}>
          <Link href="/dashboard" className="btn btn-primary" style={{ padding: '14px 28px', fontSize: '15px' }}>
            <span>Explore Ventures</span>
            <ArrowRight size={18} />
          </Link>
          <Link href="/ideas/new" className="btn btn-secondary" style={{ padding: '14px 24px', fontSize: '15px' }}>
            <span>Evaluate New Venture</span>
          </Link>
        </div>
      </section>

      {/* Feature Grid */}
      <section style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '24px',
        marginBottom: '80px',
      }}>
        <div className="card">
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            backgroundColor: 'rgba(147, 62, 207, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '16px',
            color: 'var(--primary-light)',
          }}>
            <Cpu size={24} />
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>9-Stage Analysis Pipeline</h3>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Orchestrates Market Research, Competitor Intel, Customer Signals, Strategy, DCF Finance, Sensitivity Rankings, Risk Matrix, Validation, and Committee Decision.
          </p>
        </div>

        <div className="card">
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            backgroundColor: 'rgba(16, 185, 129, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '16px',
            color: 'var(--success)',
          }}>
            <TrendingUp size={24} />
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>Deterministic Financial Grounding</h3>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Authoritative numbers never hallucinate. Multi-scenario unit economics with Net Present Value, Internal Rate of Return, Payback Period, and Monthly Burn Rate.
          </p>
        </div>

        <div className="card">
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            backgroundColor: 'rgba(245, 158, 11, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '16px',
            color: 'var(--warning)',
          }}>
            <BarChart3 size={24} />
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>Decision Analytics & Sensitivity</h3>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Identifies core sensitivity drivers via elasticity rankings. Pauses the pipeline when assumptions require human clarification and resumes without losing progress.
          </p>
        </div>

        <div className="card">
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            backgroundColor: 'rgba(59, 130, 246, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '16px',
            color: 'var(--secondary)',
          }}>
            <CheckCircle2 size={24} />
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>Grounded Investment Committee</h3>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Synthesizes an institutional Investment Committee verdict (GO / CONDITIONAL_GO / NO_GO) accompanied by an interactive Q&A assistant and scenario action triggers.
          </p>
        </div>
      </section>

      {/* Live Pipeline Preview Banner */}
      <section className="card" style={{
        background: 'linear-gradient(180deg, var(--bg-surface) 0%, rgba(30, 31, 32, 0.6) 100%)',
        border: '1px solid var(--border-light)',
        padding: '36px',
        textAlign: 'center',
      }}>
        <h2 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '12px' }}>
          Ready to experience institutional AI due diligence?
        </h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '24px', maxWidth: '600px', margin: '0 auto 24px auto' }}>
          Browse sample venture analyses or submit a new concept to see the complete autonomous pipeline in action.
        </p>
        <Link href="/dashboard" className="btn btn-primary" style={{ padding: '12px 24px' }}>
          <span>Launch Due Diligence Workspace</span>
          <ArrowRight size={16} />
        </Link>
      </section>
    </div>
  );
}
