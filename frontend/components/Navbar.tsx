'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Sparkles, Layers, PlusCircle, ShieldCheck } from 'lucide-react';

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav style={{
      borderBottom: '1px solid var(--border)',
      backgroundColor: 'rgba(19, 19, 20, 0.85)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div className="container" style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '68px',
      }}>
        {/* Brand Logo */}
        <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, var(--primary) 0%, #6366f1 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 16px var(--primary-glow)',
          }}>
            <Sparkles size={20} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '18px', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>VentureMind</span>
              <span style={{ color: 'var(--primary-light)', fontSize: '14px', fontWeight: 600 }}>AI</span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Investment Committee Intelligence
            </div>
          </div>
        </Link>

        {/* Navigation Links */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Link
            href="/dashboard"
            className={`btn ${pathname === '/dashboard' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '13px', padding: '8px 14px' }}
          >
            <Layers size={16} />
            <span>Ventures</span>
          </Link>

          <Link
            href="/ideas/new"
            className="btn btn-primary"
            style={{ fontSize: '13px', padding: '8px 14px' }}
          >
            <PlusCircle size={16} />
            <span>New Venture</span>
          </Link>
        </div>
      </div>
    </nav>
  );
}
