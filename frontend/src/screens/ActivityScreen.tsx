import React, { useState } from 'react';
import {
  Activity,
  CheckCircle2,
  XCircle,
  Play,
  Pause,
  StopCircle,
  ShieldAlert,
  Terminal,
  Clock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

import { useAgent } from '../context/AgentContext';

export const ActivityScreen: React.FC = () => {
  const {
    jobs,
    approvals,
    auditEvents,
    decideApproval,
    pauseJob,
    resumeJob,
    cancelJob,
  } = useAgent();

  const [expandedJobId, setExpandedJobId] = useState<string | null>(jobs[0]?.id || null);
  const [activeTab, setActiveTab] = useState<'approvals' | 'jobs' | 'audit'>('approvals');
  const [simulatedFeedback, setSimulatedFeedback] = useState<string | null>(null);

  const pendingApprovals = approvals.filter((a) => a.status === 'pending');
  const pastApprovals = approvals.filter((a) => a.status !== 'pending');

  const handleDecision = async (approvalId: string, decision: 'approve' | 'reject') => {
    const appr = approvals.find((a) => a.id === approvalId);
    await decideApproval(approvalId, decision);
    setSimulatedFeedback(
      decision === 'approve'
        ? `[SIMULATED APPROVAL]: Action "${appr?.plainLanguageAction}" approved in mock state. Target job advanced to verification.`
        : `[SIMULATED REJECTION]: Action "${appr?.plainLanguageAction}" denied by policy gate.`
    );
    setTimeout(() => setSimulatedFeedback(null), 6000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Simulation Feedback Alert */}
      {simulatedFeedback && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--surface-dark)',
            color: '#FFFFFF',
            borderRadius: 'var(--radius-sm)',
            fontSize: '12.5px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            borderLeft: '4px solid var(--cerulean)',
          }}
        >
          <Activity size={16} color="var(--cerulean)" />
          <span>{simulatedFeedback}</span>
        </div>
      )}

      {/* Tabs Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '8px',
        }}
      >
        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={() => setActiveTab('approvals')}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '13px',
              fontWeight: activeTab === 'approvals' ? 700 : 500,
              backgroundColor: activeTab === 'approvals' ? 'var(--cerulean)' : 'transparent',
              color: activeTab === 'approvals' ? '#FFFFFF' : 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <ShieldAlert size={14} />
            Pending Approvals ({pendingApprovals.length})
          </button>

          <button
            onClick={() => setActiveTab('jobs')}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '13px',
              fontWeight: activeTab === 'jobs' ? 700 : 500,
              backgroundColor: activeTab === 'jobs' ? 'var(--cerulean)' : 'transparent',
              color: activeTab === 'jobs' ? '#FFFFFF' : 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Terminal size={14} />
            Agent Runs & Traces ({jobs.length})
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '13px',
              fontWeight: activeTab === 'audit' ? 700 : 500,
              backgroundColor: activeTab === 'audit' ? 'var(--cerulean)' : 'transparent',
              color: activeTab === 'audit' ? '#FFFFFF' : 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Clock size={14} />
            Deterministic Audit Log ({auditEvents.length})
          </button>
        </div>
      </div>

      {/* Tab 1: Approval Queue */}
      {activeTab === 'approvals' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {pendingApprovals.length === 0 ? (
            <div className="u-card" style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
              <CheckCircle2 size={24} color="var(--status-success)" style={{ margin: '0 auto 8px' }} />
              <div>Approval queue is clear. No high-risk or external operations currently waiting.</div>
            </div>
          ) : (
            pendingApprovals.map((appr) => (
              <div
                key={appr.id}
                className="u-card"
                style={{
                  padding: '20px',
                  borderLeft: '4px solid var(--status-danger)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        className="u-badge"
                        style={{
                          backgroundColor: 'var(--status-danger-bg)',
                          color: 'var(--status-danger)',
                        }}
                      >
                        HIGH RISK: {appr.riskTier.toUpperCase()}
                      </span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {appr.id}
                      </span>
                    </div>

                    <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--onyx)', marginTop: '4px' }}>
                      {appr.title}
                    </h3>
                  </div>

                  <span
                    style={{
                      fontSize: '11px',
                      color: 'var(--status-warning)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    Expires: {new Date(appr.expiresAt).toLocaleTimeString()}
                  </span>
                </div>

                <div style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                  <strong>Action:</strong> {appr.plainLanguageAction}
                </div>

                <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  <strong>Reason:</strong> {appr.reason}
                </div>

                {/* Exact Target & Normalized Arguments Inspection Box */}
                <div
                  style={{
                    backgroundColor: 'var(--surface-subtle)',
                    padding: '12px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  <div style={{ color: 'var(--text-secondary)' }}>
                    TARGET: <span style={{ color: 'var(--onyx)', fontWeight: 600 }}>{appr.targetResource}</span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    DESTINATION: <span style={{ color: 'var(--accent)' }}>{appr.destination}</span> (Leaves machine: {appr.leavesMachine ? 'YES' : 'NO'})
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    POLICY BASIS: <span style={{ color: 'var(--onyx)' }}>{appr.policyBasis}</span>
                  </div>
                  <div style={{ marginTop: '4px', color: 'var(--text-muted)' }}>
                    ARGUMENTS: {JSON.stringify(appr.normalizedArguments, null, 2)}
                  </div>
                </div>

                {/* Specific Action Buttons adhering to Docs/07_UI_UX_SPEC.md §91 */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    paddingTop: '6px',
                    borderTop: '1px solid var(--border-subtle)',
                  }}
                >
                  <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                    Reversibility: <strong>{appr.reversibility}</strong>
                  </span>

                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button
                      onClick={() => handleDecision(appr.id, 'reject')}
                      className="u-btn u-btn-ghost"
                      style={{ color: 'var(--status-danger)', fontSize: '12.5px' }}
                    >
                      <XCircle size={14} />
                      Reject Proposal
                    </button>

                    <button
                      onClick={() => handleDecision(appr.id, 'approve')}
                      className="u-btn u-btn-primary"
                      style={{ fontSize: '12.5px' }}
                    >
                      <CheckCircle2 size={14} />
                      {appr.specificButtonLabel}
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}

          {/* Past Decided Approvals */}
          {pastApprovals.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Recent Decision History ({pastApprovals.length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {pastApprovals.map((pa) => (
                  <div
                    key={pa.id}
                    className="u-card"
                    style={{
                      padding: '10px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '12px',
                    }}
                  >
                    <span>{pa.title}</span>
                    <span
                      style={{
                        fontWeight: 700,
                        color: pa.status === 'approved' ? 'var(--status-success)' : 'var(--status-danger)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {pa.status.toUpperCase()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Agent Runs & Tool Traces */}
      {activeTab === 'jobs' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {jobs.map((job) => {
            const isExpanded = expandedJobId === job.id;

            return (
              <div
                key={job.id}
                className="u-card"
                style={{
                  padding: '18px 20px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span
                      className="u-badge"
                      style={{
                        backgroundColor:
                          job.status === 'completed'
                            ? 'var(--status-success-bg)'
                            : job.status === 'awaiting_approval'
                            ? 'var(--status-warning-bg)'
                            : 'var(--accent-soft)',
                        color:
                          job.status === 'completed'
                            ? 'var(--status-success)'
                            : job.status === 'awaiting_approval'
                            ? 'var(--status-warning)'
                            : 'var(--accent)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {job.status.toUpperCase()}
                    </span>
                    <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--onyx)' }}>
                      {job.goal}
                    </h3>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {job.status === 'executing' && (
                      <button
                        onClick={() => pauseJob(job.id)}
                        className="u-btn u-btn-secondary"
                        style={{ fontSize: '11px', padding: '4px 8px' }}
                      >
                        <Pause size={12} /> Pause
                      </button>
                    )}
                    {job.status === 'paused' && (
                      <button
                        onClick={() => resumeJob(job.id)}
                        className="u-btn u-btn-secondary"
                        style={{ fontSize: '11px', padding: '4px 8px' }}
                      >
                        <Play size={12} /> Resume
                      </button>
                    )}
                    {job.status !== 'completed' && job.status !== 'failed' && (
                      <button
                        onClick={() => cancelJob(job.id)}
                        className="u-btn u-btn-ghost"
                        style={{ fontSize: '11px', padding: '4px 8px', color: 'var(--status-danger)' }}
                      >
                        <StopCircle size={12} /> Cancel
                      </button>
                    )}
                    <button
                      onClick={() => setExpandedJobId(isExpanded ? null : job.id)}
                      className="u-btn u-btn-ghost"
                      style={{ padding: '4px' }}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <span>Stage: <strong>{job.currentStage}</strong></span>
                  <span>Model: <code className="u-code-tag">{job.modelUsed}</code></span>
                  <span>Tokens: {job.budgetTokensUsed} / {job.budgetMaxTokens}</span>
                </div>

                {/* Collapsible Traces & Evidence */}
                {isExpanded && (
                  <div
                    style={{
                      paddingTop: '12px',
                      borderTop: '1px solid var(--border-subtle)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                    }}
                  >
                    {job.executiveSummary && (
                      <div
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          padding: '10px 14px',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '12.5px',
                        }}
                      >
                        <strong>Executive Summary:</strong> {job.executiveSummary}
                      </div>
                    )}

                    <div>
                      <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--onyx)', display: 'block', marginBottom: '6px' }}>
                        Bounded Tool Traces ({job.toolTraces.length})
                      </span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {job.toolTraces.map((trace) => (
                          <div
                            key={trace.id}
                            style={{
                              padding: '8px 12px',
                              backgroundColor: '#FFFFFF',
                              border: '1px solid var(--border-subtle)',
                              borderRadius: 'var(--radius-xs)',
                              fontSize: '12px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span className="u-code-tag">{trace.tool}</span>
                              <span>{trace.summary}</span>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                              {trace.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Tab 3: Deterministic Audit Log */}
      {activeTab === 'audit' && (
        <div className="u-card" style={{ padding: '16px', overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                <th style={{ padding: '8px 10px' }}>Timestamp (UTC)</th>
                <th style={{ padding: '8px 10px' }}>Event Type</th>
                <th style={{ padding: '8px 10px' }}>Aggregate</th>
                <th style={{ padding: '8px 10px' }}>Actor</th>
                <th style={{ padding: '8px 10px' }}>Safe Payload</th>
              </tr>
            </thead>
            <tbody>
              {auditEvents.map((ev) => (
                <tr key={ev.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    {ev.occurredAt.replace('T', ' ').slice(0, 19)}
                  </td>
                  <td style={{ padding: '8px 10px', fontWeight: 650, color: 'var(--onyx)' }}>
                    <code className="u-code-tag">{ev.eventType}</code>
                  </td>
                  <td style={{ padding: '8px 10px', color: 'var(--text-secondary)' }}>
                    {ev.aggregateType}:{ev.aggregateId}
                  </td>
                  <td style={{ padding: '8px 10px', color: 'var(--accent-text)', fontWeight: 600 }}>
                    {ev.actor}
                  </td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {JSON.stringify(ev.safePayload)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
