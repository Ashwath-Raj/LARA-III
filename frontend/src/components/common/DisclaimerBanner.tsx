import React from 'react';
import { Info, ShieldAlert } from 'lucide-react';

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
        <span style={{ fontWeight: 650, color: '#FFFFFF' }}>LOCAL PROTOTYPE:</span>
        <span style={{ color: '#BDC2BF' }}>
          Browser-stored demo data only. No backend, provider, OS notification, or external action is connected.
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
          Actions are simulated
        </span>
      </div>
    </div>
  );
};
