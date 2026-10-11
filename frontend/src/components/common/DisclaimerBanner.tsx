import React from 'react';
import { Info, ShieldAlert } from 'lucide-react';
declare const __LARA_LOCAL_DEMO__: boolean;

export const DisclaimerBanner: React.FC = () => {
  return (
    <div
      style={{
        backgroundColor: '#121619',
        color: '#E3E7D3',
        padding: '6px 16px',
        fontSize: '11.5px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid rgba(227, 231, 211, 0.15)',
        letterSpacing: '0.01em',
        zIndex: 50,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <ShieldAlert size={14} color="#0075A2" />
        <span style={{ fontWeight: 650, color: '#FFFFFF' }}>LOCAL APPLICATION:</span>
        <span style={{ color: '#BDC2BF' }}>
          {__LARA_LOCAL_DEMO__
            ? 'Synthetic seeded records are demonstration content; live work is saved in the local backend. Conversation memory uses local indexing when its services are ready.'
            : 'Tasks, reminders, conversations, projects, calendar events, and AI Loops use the paired local backend. Conversation memory uses local indexing when its services are ready.'}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            color: '#E3E7D3',
          }}
        >
          <Info size={12} />
          Local-only inference
        </span>
      </div>
    </div>
  );
};
