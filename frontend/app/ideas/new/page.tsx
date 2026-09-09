'use client';

import React, { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowRight, Lightbulb, Sparkles } from 'lucide-react';

import { createIdea, sendMessage } from '@/lib/api';

export default function NewIdeaPage() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const cleanTitle = title.trim();
    const cleanDescription = description.trim();

    if (!cleanTitle || !cleanDescription) {
      setError('Please provide a title and describe the idea.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const idea = await createIdea({
        title: cleanTitle,
        description: cleanDescription,
      });

      // Feed the initial concept through the same Chat/Intake path that owns
      // IdeaProfile extraction, validation, clarification, and readiness.
      await sendMessage(idea.id, cleanDescription);
      router.push(`/ideas/${idea.id}`);
    } catch (err: any) {
      setError(err.message || 'Could not create the idea workspace.');
      setSubmitting(false);
    }
  }

  return (
    <div className="container" style={{ maxWidth: 760, paddingBottom: 48 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ color: 'var(--primary-light)', fontSize: 12, fontWeight: 700, textTransform: 'uppercase' }}>
          Start Idea
        </div>
        <h1 style={{ fontSize: 34, fontWeight: 800, marginTop: 6 }}>What are you thinking about?</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 15, lineHeight: 1.6, marginTop: 10 }}>
          Give VentureMind the idea in your own words. The Chat AI will extract grounded facts into an Idea Profile and ask the most useful clarification before analysis can start.
        </p>
      </div>

      <div className="card">
        {error && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: 12, border: '1px solid var(--danger-border)', borderRadius: 10, color: 'var(--danger)', marginBottom: 18 }}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            Idea name
          </label>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. CareDesk AI"
            minLength={3}
            maxLength={200}
            required
            style={{ width: '100%', padding: '12px 14px', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-main)', marginBottom: 20 }}
          />

          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            Describe the idea
          </label>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Who is it for, what problem does it solve, where will it operate, and how might it make money? Share only what you actually know."
            minLength={10}
            maxLength={10000}
            rows={8}
            required
            style={{ width: '100%', padding: '14px', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-main)', lineHeight: 1.6, resize: 'vertical' }}
          />

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 22 }}>
            <button type="button" className="btn btn-secondary" disabled={submitting} onClick={() => router.push('/dashboard')}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? <span className="spin"><Sparkles size={16} /></span> : <ArrowRight size={16} />}
              {submitting ? 'Starting conversation…' : 'Start Conversation'}
            </button>
          </div>
        </form>
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 18, color: 'var(--text-muted)', fontSize: 13, lineHeight: 1.55 }}>
        <Lightbulb size={18} color="var(--primary-light)" style={{ flexShrink: 0 }} />
        <span>
          Analysis never starts automatically. VentureMind first builds and validates the Idea Profile, then enables an explicit Start Analysis action only when the profile is ready.
        </span>
      </div>
    </div>
  );
}
