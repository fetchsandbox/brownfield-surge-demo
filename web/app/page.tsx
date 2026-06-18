'use client';

import { useState } from 'react';

export default function Home() {
  const [status, setStatus] = useState<string>('');

  async function handleShipDemo() {
    setStatus('Marking demo order as shipped…');
    try {
      const res = await fetch(
        (process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000') +
          '/api/orders/demo-order/ship',
        { method: 'POST' },
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setStatus(
          `Not wired yet (${res.status}): ${err.detail || 'see README'}`,
        );
        return;
      }
      const data = await res.json();
      if (data.sms_sent) {
        setStatus(`Shipped + SMS sent (message_id=${data.message_id}).`);
      } else {
        setStatus(
          `Shipped — but SMS notification not wired yet. ` +
            `See README → "What's NOT wired yet".`,
        );
      }
    } catch (e) {
      setStatus(`Error: ${e instanceof Error ? e.message : 'unknown'}`);
    }
  }

  return (
    <main
      style={{
        maxWidth: 640,
        margin: '80px auto',
        padding: 24,
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <h1 style={{ fontSize: 32, marginBottom: 8 }}>Acme Orders</h1>
      <p style={{ color: '#666', marginBottom: 8, lineHeight: 1.5 }}>
        Order management demo. Clerk for auth, Postgres for orders.
        Surge for SMS notifications — not wired yet. That's the
        agent's job.
      </p>
      <p
        style={{
          color: '#888',
          marginBottom: 32,
          fontSize: 14,
          lineHeight: 1.5,
        }}
      >
        See README → &ldquo;What&rsquo;s NOT wired yet&rdquo;.
      </p>

      <div
        style={{
          background: '#fafafa',
          border: '1px solid #eee',
          borderRadius: 12,
          padding: 24,
          marginBottom: 24,
        }}
      >
        <div style={{ fontSize: 14, color: '#666', marginBottom: 4 }}>
          Order #demo-order
        </div>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Acme Pro Plan</div>
        <div style={{ color: '#666', marginTop: 6, fontSize: 14 }}>
          Customer phone: +1 (801) 555-1234 · Status: pending
        </div>
      </div>

      <button
        onClick={handleShipDemo}
        style={{
          display: 'inline-block',
          padding: '14px 28px',
          background: '#16a34a',
          color: 'white',
          border: 'none',
          borderRadius: 8,
          fontWeight: 600,
          fontSize: 16,
          cursor: 'pointer',
        }}
      >
        Mark shipped + notify customer
      </button>

      {status && (
        <p
          style={{
            marginTop: 24,
            padding: 12,
            background: '#fff8e1',
            border: '1px solid #ffd54f',
            borderRadius: 8,
            color: '#5d4037',
            fontSize: 14,
          }}
        >
          {status}
        </p>
      )}
    </main>
  );
}
