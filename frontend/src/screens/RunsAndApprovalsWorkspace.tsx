import React, { useEffect, useState } from 'react';
import {
  Activity,
  FileCheck2,
  Shield,
  Clock,
} from 'lucide-react';

import { useAgent } from '../context/AgentContext';
import { RoomBadge } from '../components/common/Badge';

export const RunsAndApprovalsWorkspace: React.FC = () => {
  const {
    approvals,
    jobs,
    auditEvents,
    decideApproval,
    openApprovalDetail,
    activeScreen,
    setActiveScreen,
    setSelectedJob,
    closeAllDrawers,
    clearRunPreview,
  } = useAgent();

  const [activeTab, setActiveTab] = useState<'approvals' | 'jobs' | 'audit'>(activeScreen === 'activity' ? 'jobs' : 'approvals');
  const [selectedAuditFilter] = useState('all');

  useEffect(() => {
    setActiveTab(activeScreen === 'activity' ? 'jobs' : 'approvals');
  }, [activeScreen]);

  const pendingApprovals = approvals.filter((a) => a.status === 'pending');

  const filteredAudits = auditEvents.filter(
    (e) => selectedAuditFilter === 'all' || e.aggregateType === selectedAuditFilter
  );

  const requestApprovalDecision = (approvalId: string, decision: 'approve' | 'reject') => {
    const approval = approvals.find((item) => item.id === approvalId);
    if (!approval) return;
    const verb = decision === 'approve' ? 'simulate approval for' : 'simulate rejection of';
    if (window.confirm(`${verb} “${approval.plainLanguageAction}” targeting ${approval.targetResource}? No external action will run.`)) {
      void decideApproval(approvalId, decision);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--app-canvas)',
        overflowY: 'auto',
        padding: '24px 32px',
        gap: '20px',
      }}
    >
      {/* Top Tab Bar */}
      <div className="operations-workspace"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '12px',
        }}
      >
        <div className="operations-tabs" style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setActiveTab('approvals')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontWeight: 600,
              fontSize: '13px',
              backgroundColor: activeTab === 'approvals' ? 'var(--surface-primary)' : 'transparent',
              color: activeTab === 'approvals' ? 'var(--onyx)' : 'var(--text-secondary)',
              border: '1px solid',
              borderColor: activeTab === 'approvals' ? 'var(--border-subtle)' : 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <FileCheck2 size={15} color="var(--status-danger)" />
            <span>Approval Queue ({pendingApprovals.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('jobs')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontWeight: 600,
              fontSize: '13px',
              backgroundColor: activeTab === 'jobs' ? 'var(--surface-primary)' : 'transparent',
              color: activeTab === 'jobs' ? 'var(--onyx)' : 'var(--text-secondary)',
              border: '1px solid',
              borderColor: activeTab === 'jobs' ? 'var(--border-subtle)' : 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Activity size={15} color="var(--cerulean)" />
            <span>Agent Jobs ({jobs.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontWeight: 600,
              fontSize: '13px',
              backgroundColor: activeTab === 'audit' ? 'var(--surface-primary)' : 'transparent',
              color: activeTab === 'audit' ? 'var(--onyx)' : 'var(--text-secondary)',
              border: '1px solid',
              borderColor: activeTab === 'audit' ? 'var(--border-subtle)' : 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Shield size={15} color="var(--grey-olive)" />
            <span>Deterministic Audit Trail ({auditEvents.length})</span>
          </button>
        </div>
      </div>

      {/* APPROVALS TAB */}
      {activeTab === 'approvals' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '840px' }}>
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--onyx)', marginBottom: '12px' }}>
              Pending Human-in-the-Loop Reviews ({pendingApprovals.length})
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {pendingApprovals.map((app) => (
                <div
                  key={app.id}
                  style={{
                    backgroundColor: 'var(--surface-primary)',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                    padding: '16px',
                    boxShadow: 'var(--shadow-sm)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          backgroundColor: 'var(--status-danger-bg)',
                          color: 'var(--status-danger)',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {app.riskTier.toUpperCase()} RISK
                      </span>
                      <RoomBadge room={app.sourceRoom} size="small" />
                    </div>

                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      Created: {app.createdAt.slice(11, 19)}
                    </span>
                  </div>

                  <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--onyx)' }}>
                    {app.plainLanguageAction}
                  </div>

                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Target: <code style={{ fontFamily: 'var(--font-mono)' }}>{app.targetResource}</code>
                  </div>
                  <dl className="approval-summary-grid">
                    <div><dt>Destination</dt><dd>{app.destination}</dd></div>
                    <div><dt>Leaves this device</dt><dd>{app.leavesMachine ? 'Yes' : 'No'}</dd></div>
                    <div><dt>Reversibility</dt><dd>{app.reversibility}</dd></div>
                    <div><dt>Expires</dt><dd><time dateTime={app.expiresAt}>{new Date(app.expiresAt).toLocaleString()}</time></dd></div>
                  </dl>
                  <details className="approval-arguments-preview" open>
                    <summary>Exact proposed arguments</summary>
                    <pre>{JSON.stringify(app.normalizedArguments, null, 2)}</pre>
                  </details>

                  <div
                    style={{
                      padding: '8px 12px',
                      borderRadius: '6px',
                      backgroundColor: 'var(--surface-subtle)',
                      fontSize: '11px',
                      color: 'var(--text-muted)',
                    }}
                  >
                    Policy Basis: {app.policyBasis}
                  </div>

                  <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                    <button
                      onClick={() => requestApprovalDecision(app.id, 'approve')}
                      style={{
                        padding: '6px 14px',
                        backgroundColor: 'var(--status-success)',
                        color: '#ffffff',
                        borderRadius: '6px',
                        fontWeight: 600,
                        fontSize: '12px',
                        cursor: 'pointer',
                      }}
                    >
                      Simulate: {app.specificButtonLabel || 'Approve Action'}
                    </button>
                    <button
                      onClick={() => requestApprovalDecision(app.id, 'reject')}
                      style={{
                        padding: '6px 14px',
                        backgroundColor: 'var(--status-danger)',
                        color: '#ffffff',
                        borderRadius: '6px',
                        fontWeight: 600,
                        fontSize: '12px',
                        cursor: 'pointer',
                      }}
                    >
                      Record demo rejection
                    </button>
                    <button
                      onClick={() => openApprovalDetail(app)}
                      style={{
                        padding: '6px 12px',
                        backgroundColor: 'var(--surface-subtle)',
                        color: 'var(--text-secondary)',
                        borderRadius: '6px',
                        fontSize: '12px',
                        cursor: 'pointer',
                        marginLeft: 'auto',
                      }}
                    >
                      Inspect Payload
                    </button>
                  </div>
                </div>
              ))}

              {pendingApprovals.length === 0 && (
                <div
                  style={{
                    padding: '24px',
                    textAlign: 'center',
                    backgroundColor: 'var(--surface-primary)',
                    borderRadius: '8px',
                    color: 'var(--text-muted)',
                    fontSize: '13px',
                  }}
                >
                  All high-risk approvals are reviewed.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* JOBS TAB */}
      {activeTab === 'jobs' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '840px' }}>
          {jobs.map((job) => (
            <div
              key={job.id}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); closeAllDrawers(); clearRunPreview(); setSelectedJob(job); setActiveScreen('run_console'); } }}
              onClick={() => { closeAllDrawers(); clearRunPreview(); setSelectedJob(job); setActiveScreen('run_console'); }}
              style={{
                backgroundColor: 'var(--surface-primary)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
                padding: '14px 16px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <RoomBadge room={job.room} size="small" />
                  <span
                    style={{
                      fontSize: '10.5px',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 700,
                      color:
                        job.status === 'executing'
                          ? 'var(--cerulean)'
                          : job.status === 'completed'
                          ? 'var(--status-success)'
                          : 'var(--text-muted)',
                    }}
                  >
                    {job.status.toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--onyx)' }}>
                  {job.goal}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Stage: {job.currentStage}
                </div>
              </div>

              <Clock size={15} color="var(--grey-olive)" />
            </div>
          ))}
        </div>
      )}

      {/* AUDIT TRAIL TAB */}
      {activeTab === 'audit' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '840px' }}>
          {filteredAudits.map((event) => (
            <div
              key={event.id}
              style={{
                backgroundColor: 'var(--surface-primary)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
                padding: '12px 16px',
                fontFamily: 'var(--font-mono)',
                fontSize: '11.5px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontWeight: 700, color: 'var(--cerulean)' }}>{event.eventType}</span>
                <span style={{ color: 'var(--text-muted)' }}>{event.occurredAt.slice(11, 19)}</span>
              </div>
              <div style={{ color: 'var(--text-secondary)' }}>
                Target: {event.aggregateType} #{event.aggregateId} • Actor: {event.actor}
              </div>
              <pre
                style={{
                  marginTop: '6px',
                  padding: '6px 8px',
                  backgroundColor: 'var(--surface-subtle)',
                  borderRadius: '4px',
                  fontSize: '10.5px',
                  overflowX: 'auto',
                }}
              >
                {JSON.stringify(event.safePayload, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
