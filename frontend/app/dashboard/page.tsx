'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { listIdeas, IdeaItem } from '@/lib/api';
import {
  Layers,
  PlusCircle,
  Clock,
  ArrowRight,
  Sparkles,
  Search,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react';

export default function DashboardPage() {
  const [ideas, setIdeas] = useState<IdeaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    loadIdeas();
  }, []);

  async function loadIdeas() {
    try {
      setLoading(true);
      setError(null);
      const data = await listIdeas();
      setIdeas(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load ideas');
    } finally {
      setLoading(false);
    }
  }

  const filteredIdeas = ideas.filter((idea) =>
    idea.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    idea.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="container">
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '32px',
      }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '4px' }}>
            Venture Evaluations
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
            Manage and inspect autonomous due diligence reports across active startup evaluations.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button onClick={loadIdeas} className="btn btn-secondary" title="Refresh">
            <RotateCcw size={16} />
            <span>Refresh</span>
          </button>
          <Link href="/ideas/new" className="btn btn-primary">
            <PlusCircle size={16} />
            <span>Evaluate New Venture</span>
          </Link>
        </div>
      </div>

      {/* Search Bar */}
      <div style={{
        marginBottom: '24px',
        position: 'relative',
        maxWidth: '480px',
      }}>
        <Search size={18} style={{
          position: 'absolute',
          left: '14px',
          top: '50%',
          transform: 'translateY(-50%)',
          color: 'var(--text-dim)',
        }} />
        <input
          type="text"
          placeholder="Search by venture name or concept..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            width: '100%',
            padding: '12px 14px 12px 42px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--text-main)',
            fontSize: '14px',
            outline: 'none',
          }}
        />
      </div>

      {/* Loading state */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '64px 0', color: 'var(--text-muted)' }}>
          <div className="spin" style={{ display: 'inline-block', marginBottom: '12px' }}>
            <Sparkles size={28} color="var(--primary)" />
          </div>
          <p>Loading venture due diligence records...</p>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="card" style={{ borderColor: 'var(--danger-border)', backgroundColor: 'var(--danger-bg)', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--danger)' }}>
            <AlertTriangle size={18} />
            <strong>Connection Error</strong>
          </div>
          <p style={{ marginTop: '8px', fontSize: '14px', color: 'var(--text-main)' }}>{error}</p>
        </div>
      )}

      {/* Ideas Grid */}
      {!loading && !error && filteredIdeas.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '64px 24px' }}>
          <Layers size={40} color="var(--text-dim)" style={{ marginBottom: '16px' }} />
          <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>No venture records found</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginBottom: '24px' }}>
            Submit an idea to kick off the autonomous due diligence pipeline.
          </p>
          <Link href="/ideas/new" className="btn btn-primary">
            <PlusCircle size={16} />
            <span>Create First Venture Evaluation</span>
          </Link>
        </div>
      )}

      {!loading && !error && filteredIdeas.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
          gap: '20px',
        }}>
          {filteredIdeas.map((idea) => (
            <Link
              key={idea.id}
              href={`/ideas/${idea.id}`}
              className="card card-interactive"
              style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                minHeight: '200px',
              }}
            >
              <div>
                <div style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: '12px',
                  marginBottom: '10px',
                }}>
                  <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)' }}>
                    {idea.title}
                  </h3>
                  <span className="badge badge-neutral" style={{ fontSize: '11px', flexShrink: 0 }}>
                    {idea.state || 'EVALUATION'}
                  </span>
                </div>

                <p style={{
                  fontSize: '14px',
                  color: 'var(--text-muted)',
                  lineHeight: 1.5,
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  marginBottom: '16px',
                }}>
                  {idea.description}
                </p>
              </div>

              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingTop: '14px',
                borderTop: '1px solid var(--border)',
                fontSize: '12px',
                color: 'var(--text-dim)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={14} />
                  <span>
                    {idea.created_at
                      ? new Date(idea.created_at).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })
                      : 'Recently created'}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--primary-light)', fontWeight: 500 }}>
                  <span>Open Workspace</span>
                  <ArrowRight size={14} />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
