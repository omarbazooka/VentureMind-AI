import React from 'react';
import './globals.css';
import Navbar from '@/components/Navbar';

export const metadata = {
  title: 'VentureMind AI — Autonomous VC Due Diligence & Investment Committee Intelligence',
  description: 'Production AI due diligence platform: deterministic research join, financial sensitivity modeling, and grounded investment committee decisions.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <main style={{ minHeight: 'calc(100vh - 68px)', padding: '32px 0 64px 0' }}>
          {children}
        </main>
      </body>
    </html>
  );
}
