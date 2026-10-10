import React from 'react';
import {
  Shield,
  UserCheck,
  ArrowRightLeft,
  Layers,
} from 'lucide-react';

import { useAgent } from '../context/AgentContext';
import { INITIAL_ROOMS, INITIAL_PERSONAS, INITIAL_BRIDGES } from '../data/mockData';
import { KnowledgeRoom, PersonaId } from '../types';
import { SensitivityBadge } from '../components/common/Badge';

export const RoomsScreen: React.FC = () => {
  const {
    activeRoom,
    setActiveRoom,
    activePersona,
    setActivePersona,
  } = useAgent();

  const currentPersonaDef = INITIAL_PERSONAS.find((p) => p.id === activePersona);
  const currentRoomDef = INITIAL_ROOMS.find((r) => r.id === activeRoom);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Top Banner: Compartmentalization Overview */}
      <div
        className="u-paper-surface"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '20px',
          backgroundColor: 'var(--surface-primary)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Shield size={18} color="var(--accent)" />
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--onyx)' }}>
              Compartmentalized Memory & Autonomy Matrix
            </h2>
          </div>
          <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Rooms enforce strict retrieval boundaries. Sensitive rooms (Academic, Projects, Personal Vault, Health) are excluded from cloud inference prompts by default.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Active Room:
          </span>
          <span
            style={{
              padding: '4px 10px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 700,
              fontSize: '12.5px',
              color: 'var(--onyx)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            {currentRoomDef?.name}
          </span>
        </div>
      </div>

      {/* Persona Selection Row */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <UserCheck size={16} color="var(--accent)" />
            <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--onyx)' }}>
              Purpose-Specific Personas
            </h2>
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Personas provide specialized workflows under central policy rules.
          </span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '12px',
          }}
        >
          {INITIAL_PERSONAS.map((persona) => {
            const isSelected = activePersona === persona.id;

            return (
              <div
                key={persona.id}
                onClick={() => setActivePersona(persona.id as PersonaId)}
                className="u-card"
                style={{
                  padding: '16px',
                  cursor: 'pointer',
                  borderColor: isSelected ? 'var(--cerulean)' : 'var(--border-subtle)',
                  backgroundColor: isSelected ? 'var(--surface-warm)' : 'var(--surface-primary)',
                  borderLeft: isSelected ? '4px solid var(--cerulean)' : undefined,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--onyx)' }}>
                    {persona.name}
                  </span>
                  {isSelected && (
                    <span
                      style={{
                        fontSize: '10px',
                        backgroundColor: 'var(--cerulean)',
                        color: '#FFFFFF',
                        padding: '1px 6px',
                        borderRadius: 'var(--radius-full)',
                        fontWeight: 700,
                      }}
                    >
                      ACTIVE
                    </span>
                  )}
                </div>

                <div style={{ fontSize: '11px', color: 'var(--accent-text)', fontWeight: 600 }}>
                  Role: {persona.role}
                </div>

                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.35 }}>
                  {persona.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Permissions Matrix for Active Persona */}
      {currentPersonaDef && (
        <div className="u-card" style={{ padding: '16px', overflowX: 'auto' }}>
          <div style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--onyx)' }}>
              Effective Permissions for: {currentPersonaDef.name}
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Legend: R=Read, W=Write, P=Prepare, A=Approval required, No access=Denied
            </span>
          </div>

          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '12.5px',
              textAlign: 'left',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '8px 12px' }}>Knowledge Room</th>
                <th style={{ padding: '8px 12px' }}>Sensitivity Level</th>
                <th style={{ padding: '8px 12px' }}>Default Cloud Policy</th>
                <th style={{ padding: '8px 12px', textAlign: 'center' }}>Permission</th>
              </tr>
            </thead>
            <tbody>
              {INITIAL_ROOMS.map((room) => {
                const grant = currentPersonaDef.accessMatrix[room.id] || 'none';
                const isRoomActive = activeRoom === room.id;

                return (
                  <tr
                    key={room.id}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      backgroundColor: isRoomActive ? 'rgba(0, 117, 162, 0.05)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '10px 12px', fontWeight: 600, color: 'var(--onyx)' }}>
                      {room.name} {isRoomActive && <span style={{ color: 'var(--accent)' }}>● Active</span>}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <SensitivityBadge sensitivity={room.sensitivity} />
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                      {room.defaultCloudPolicy}
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-xs)',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          fontSize: '12px',
                          backgroundColor:
                            grant === 'R/W'
                              ? 'rgba(29, 115, 55, 0.15)'
                              : grant === 'R'
                              ? 'rgba(0, 117, 162, 0.12)'
                              : grant === 'P'
                              ? 'rgba(153, 98, 0, 0.12)'
                              : 'rgba(18, 22, 25, 0.08)',
                          color:
                            grant === 'R/W'
                              ? 'var(--status-success)'
                              : grant === 'R'
                              ? 'var(--accent)'
                              : grant === 'P'
                              ? 'var(--status-warning)'
                              : 'var(--text-muted)',
                        }}
                      >
                        {grant === 'none' ? 'No access' : grant}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Knowledge Rooms Selector Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--onyx)' }}>
          Knowledge Rooms Catalog ({INITIAL_ROOMS.length})
        </h2>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '14px',
          }}
        >
          {INITIAL_ROOMS.map((room) => {
            const isSelected = activeRoom === room.id;

            return (
              <div
                key={room.id}
                onClick={() => setActiveRoom(room.id as KnowledgeRoom)}
                className="u-card"
                style={{
                  padding: '18px',
                  cursor: 'pointer',
                  borderColor: isSelected ? 'var(--cerulean)' : 'var(--border-subtle)',
                  backgroundColor: isSelected ? 'rgba(0, 117, 162, 0.04)' : 'var(--surface-primary)',
                  borderLeft: isSelected ? '4px solid var(--cerulean)' : undefined,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Layers size={16} color="var(--accent)" />
                    <span style={{ fontSize: '14.5px', fontWeight: 700, color: 'var(--onyx)' }}>
                      {room.name}
                    </span>
                  </div>
                  <SensitivityBadge sensitivity={room.sensitivity} />
                </div>

                <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  {room.description}
                </p>

                <div
                  style={{
                    backgroundColor: 'var(--surface-subtle)',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-xs)',
                    fontSize: '11.5px',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <strong style={{ color: 'var(--onyx)' }}>Typical content:</strong> {room.typicalContent}
                </div>

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '11px',
                    color: 'var(--text-muted)',
                    borderTop: '1px solid var(--border-subtle)',
                    paddingTop: '8px',
                  }}
                >
                  <span>{room.itemCount} linked entities</span>
                  <span>{room.bridgesCount} cross-room bridges</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cross-Room Bridges Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ArrowRightLeft size={16} color="var(--accent)" />
          <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--onyx)' }}>
            Active Cross-Room Bridges ({INITIAL_BRIDGES.length})
          </h2>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          Bridges project explicit narrow fields across rooms (e.g. sharing assignment title without exposing lecture notes). They never open raw database access.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {INITIAL_BRIDGES.map((bridge) => (
            <div
              key={bridge.id}
              className="u-card"
              style={{
                padding: '16px 20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="u-code-tag">{bridge.sourceRoom}</span>
                  <span>→</span>
                  <span className="u-code-tag">{bridge.destinationRoom}</span>
                </div>
                <span
                  style={{
                    fontSize: '11px',
                    color: 'var(--status-success)',
                    fontWeight: 700,
                  }}
                >
                  ACTIVE BRIDGE
                </span>
              </div>

              <div style={{ fontSize: '12.5px', color: 'var(--text-primary)' }}>
                {bridge.purpose}
              </div>

              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Shared Fields:</span>
                {bridge.sharedFields.map((f) => (
                  <span key={f} className="u-code-tag">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
