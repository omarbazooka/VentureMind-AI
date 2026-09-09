'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { createIdea } from '@/lib/api';
import { Sparkles, ArrowRight, Lightbulb, AlertCircle } from 'lucide-react';

export default function NewIdeaPage() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !description.trim()) {
      setError('Please provide both venture title and concept description.');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const newIdea = await createIdea({
        title: title.trim(),
        description: description.trim(),
      });
      router.push(`/ideas/${newIdea.id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to submit venture concept');
      setSubmitting(false);
    }
  }

  return (
    <div className="container" style={{ maxWidth: '680px' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '8px' }}>
          New Venture Intake
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '15px' }}>
          Enter your venture concept. Our multi-agent intelligence pipeline will conduct market research,
          construct DCF financial models, perform sensitivity testing, and formulate an Investment Committee verdict.
        </p>
      </div>

      <div className="card">
        {error && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            backgroundColor: 'var(--danger-bg)',
            border: '1px solid var(--danger-border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--danger)',
            fontSize: '14px',
            marginBottom: '20px',
          }}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>
              Venture Name / Title
            </label>
            <input
              type="text"
              placeholder="e.g., FleetPulse AI"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              minLength={3}
              maxLength={120}
              style={{
                width: '100%',
                padding: '12px 16px',
                backgroundColor: 'var(--bg-base)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-main)',
                fontSize: '15px',
                outline: 'none',
              }}
            />
          </div>

          <div style={{ marginBottom: '28px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>
              Concept Description & Value Proposition
            </label>
            <textarea
              placeholder="Describe what problem you are solving, target customers, business model, and initial pricing assumptions..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              minLength={10}
              maxLength={2000}
              rows={6}
              style={{
                width: '100%',
                padding: '14px 16px',
                backgroundColor: 'var(--bg-base)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-main)',
                fontSize: '14px',
                lineHeight: 1.6,
                outline: 'none',
                resize: 'vertical',
              }}
            />
            <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '6px' }}>
              Include target market, customer pain point, and proposed pricing (e.g. $49/mo per seat) for optimal model accuracy.
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '12px' }}>
            <button
              type="button"
              onClick={() => router.push('/dashboard')}
              className="btn btn-secondary"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting}
              style={{ minWidth: '160px' }}
            >
              {submitting ? (
                <>
                  <span className="spin"><Sparkles size={16} /></span>
                  <span>Creating...</span>
                </>
              ) : (
                <>
                  <span>Launch Due Diligence</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Helper Card */}
      <div style={{
        marginTop: '24px',
        padding: '16px 20px',
        borderRadius: 'var(--radius-md)',
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
      }}>
        <Lightbulb size={20} color="var(--primary-light)" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
          <strong>How it works:</strong> Once submitted, the autonomous pipeline will research market signals, verify competitor pricing, calculate DCF/LBO unit economics, and test financial sensitivities. If key variables are missing, the system will pause and ask for your inputs.
        </div>
      </div>
    </div>
  );
}
