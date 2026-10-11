import React, { useEffect, useState } from 'react';
import { Cpu, Shield, Bell, CalendarDays, CheckCircle2, Server, Moon } from 'lucide-react';

import { useAgent } from '../context/AgentContext';
import { UNAVAILABLE_GOOGLE_CALENDAR } from '../api/types';
import { LocalUbuntuAgentApi } from '../api/localAdapter';

export const SettingsScreen: React.FC = () => {
  const { settings, updateSettings, resetDemoData } = useAgent();

  const [activeModel, setActiveModel] = useState(settings.activeModel || 'gemma:2b-instruct-q4_K_M');
  const [temperature, setTemperature] = useState(settings.temperature ?? 0.2);
  const [routingPolicy, setRoutingPolicy] = useState(settings.routingPolicy || 'local_first');
  const [autonomyTier, setAutonomyTier] = useState(settings.autonomyTier || 'cautious');
  const [requireExternal, setRequireExternal] = useState(settings.requireApprovalForExternal ?? true);
  const [requireDelete, setRequireDelete] = useState(settings.requireApprovalForFileDelete ?? true);
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(settings.quietHours?.enabled ?? true);
  const [quietStart, setQuietStart] = useState(settings.quietHours?.start || '23:00');
  const [quietEnd, setQuietEnd] = useState(settings.quietHours?.end || '07:30');
  const [desktopNotifs, setDesktopNotifs] = useState(settings.desktopNotifications ?? true);
  const [savedNotice, setSavedNotice] = useState(false);
  const [resetNotice, setResetNotice] = useState(false);
  const [runtime, setRuntime] = useState<any>(null);
  useEffect(() => { new LocalUbuntuAgentApi().readiness().then(setRuntime).catch(() => setRuntime({ status:'unavailable', database:'unavailable', local_model:{status:'unavailable'} })); }, []);

  const handleSave = async () => {
    await updateSettings({
      activeModel,
      temperature,
      routingPolicy,
      autonomyTier,
      requireApprovalForExternal: requireExternal,
      requireApprovalForFileDelete: requireDelete,
      quietHours: {
        enabled: quietHoursEnabled,
        start: quietStart,
        end: quietEnd,
      },
      desktopNotifications: desktopNotifs,
    });
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 4000);
  };

  return (
    <div className="settings-workspace" style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '860px' }}>
      <p role="note">Settings persistence is not available yet. Values on this screen are for reference and will not be saved.</p>
      {resetNotice && <div role="status" aria-live="polite" style={{ padding: '12px 16px', color: 'var(--status-success)', background: 'var(--status-success-bg)', borderRadius: 'var(--radius-sm)', fontSize: '13px' }}>Demo data was reset to the local sample records.</div>}
      {savedNotice && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--status-success-bg)',
            color: 'var(--status-success)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid rgba(29, 115, 55, 0.2)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          <CheckCircle2 size={16} />
          Preferences updated and saved to local settings store.
        </div>
      )}

      {/* Provider settings remain read-only until the backend exposes settings persistence. */}
      <div className="u-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={18} color="var(--accent)" />
            <h2 style={{ fontSize: '15.5px', fontWeight: 700, color: 'var(--onyx)' }}>
              Provider configuration (read-only)
            </h2>
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            LOCAL-FIRST ARCHITECTURE
          </span>
        </div>

        <div className="provider-cards" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
          {/* Ollama Local */}
          <div
            style={{
              padding: '14px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--onyx)' }}>
                Local model provider
              </span>
              <span
                style={{
                  fontSize: '11px',
                  color: 'var(--status-warning)',
                  fontWeight: 700,
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {String(runtime?.local_model?.status || 'checking').replaceAll('_',' ').toUpperCase()}
              </span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Configured model: <code>{runtime?.local_model?.model || 'Ollama default'}</code>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Chat and AI Loops use this local provider when it reports available.
            </div>
          </div>

          {/* Cloud Reasoner */}
          <div
            style={{
              padding: '14px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--onyx)' }}>
                Hosted Cloud Reasoner
              </span>
              <span
                style={{
                  fontSize: '11px',
                  color: 'var(--status-warning)',
                  fontWeight: 700,
                  fontFamily: 'var(--font-mono)',
                }}
              >
                NOT CONNECTED
              </span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Hosted provider
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Hosted inference is disabled by the local-only provider policy.
            </div>
          </div>
        </div>
      </div>

      {/* Section 2: Model Routing & Inference Preferences */}
      <div className="u-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={18} color="var(--accent)" />
          <h2 style={{ fontSize: '15.5px', fontWeight: 700, color: 'var(--onyx)' }}>
            Model Routing & Execution Preferences
          </h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div>
            <label style={{ fontSize: '12px', fontWeight: 650, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
              Preferred model (not connected)
            </label>
            <select
              value={activeModel}
              onChange={(e) => setActiveModel(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--surface-primary)',
                fontSize: '13px',
              }}
            >
              <option value="gemma:2b-instruct-q4_K_M">gemma:2b-instruct-q4_K_M</option>
              <option value="gemma:7b-instruct-q4_K_M">gemma:7b-instruct-q4_K_M</option>
              <option value="mistral:7b-instruct">mistral:7b-instruct</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: '12px', fontWeight: 650, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
              Inference Routing Policy
            </label>
            <select
              value={routingPolicy}
              onChange={(e) => setRoutingPolicy(e.target.value as any)}
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--surface-primary)',
                fontSize: '13px',
              }}
            >
              <option value="local_first">Local first preference (provider unavailable)</option>
              <option value="local_only">Local only preference</option>
              <option value="cloud_permitted">Hosted provider preference (unavailable)</option>
            </select>
          </div>
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label style={{ fontSize: '12px', fontWeight: 650, color: 'var(--text-secondary)' }}>
              Sampling Temperature: {temperature}
            </label>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              0.0 = Deterministic extraction · 0.7 = Creative synthesis
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
            style={{ width: '100%' }}
          />
        </div>
      </div>

      {/* Section 3: Autonomy & Guardrails */}
      <div className="u-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Shield size={18} color="var(--accent)" />
          <h2 style={{ fontSize: '15.5px', fontWeight: 700, color: 'var(--onyx)' }}>
            Autonomy Tier & Policy Enforcement
          </h2>
        </div>

        <div>
          <label style={{ fontSize: '12px', fontWeight: 650, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
            Default Autonomy Risk Level
          </label>
          <select
            value={autonomyTier}
            onChange={(e) => setAutonomyTier(e.target.value as any)}
            style={{
              width: '100%',
              padding: '8px 10px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--surface-primary)',
              fontSize: '13px',
            }}
          >
            <option value="cautious">Cautious (Require approval for external writes and destructive actions)</option>
            <option value="strict_approval">Strict (Require confirmation on all tool calls)</option>
            <option value="autonomous_routine">Autonomous Routine (Execute read-only and local edits automatically)</option>
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="checkbox"
              id="external-appr"
              checked={requireExternal}
              onChange={(e) => setRequireExternal(e.target.checked)}
            />
            <label htmlFor="external-appr" style={{ fontSize: '12.5px', color: 'var(--onyx)', cursor: 'pointer' }}>
              <strong>Mandatory approval for external submissions</strong> (e.g. Google Classroom turn-in, emails)
            </label>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="checkbox"
              id="file-delete-appr"
              checked={requireDelete}
              onChange={(e) => setRequireDelete(e.target.checked)}
            />
            <label htmlFor="file-delete-appr" style={{ fontSize: '12.5px', color: 'var(--onyx)', cursor: 'pointer' }}>
              <strong>Mandatory approval for workspace file deletions and cache purges</strong>
            </label>
          </div>
        </div>
      </div>

      {/* Section 4: Notifications & Quiet Hours */}
      <div className="u-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Bell size={18} color="var(--accent)" />
          <h2 style={{ fontSize: '15.5px', fontWeight: 700, color: 'var(--onyx)' }}>
            Desktop Notifications & Quiet Hours
          </h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="checkbox"
            id="notif-toggle"
            checked={desktopNotifs}
            onChange={(e) => setDesktopNotifs(e.target.checked)}
          />
          <label htmlFor="notif-toggle" style={{ fontSize: '12.5px', color: 'var(--onyx)', cursor: 'pointer' }}>
            Enable Ubuntu Desktop notifications for upcoming deadlines and approval requests
          </label>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
            <input type="checkbox" checked={quietHoursEnabled} onChange={(event) => setQuietHoursEnabled(event.target.checked)} />
            Enable quiet hours
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Moon size={14} color="var(--text-secondary)" />
            <span style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Quiet Hours:
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="time"
              value={quietStart}
              onChange={(e) => setQuietStart(e.target.value)}
              style={{ padding: '4px 8px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)', fontSize: '12px' }}
            />
            <span>to</span>
            <input
              type="time"
              value={quietEnd}
              onChange={(e) => setQuietEnd(e.target.value)}
              style={{ padding: '4px 8px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)', fontSize: '12px' }}
            />
          </div>
        </div>
      </div>

      <section className="u-card calendar-integration-card" aria-labelledby="calendar-integration-title">
        <header className="calendar-integration-heading">
          <div><CalendarDays size={18} /><div><h2 id="calendar-integration-title">Google Calendar</h2><p>Account connection and event sync</p></div></div>
          <span className="calendar-connection-state">{UNAVAILABLE_GOOGLE_CALENDAR.status.replace(/_/g, ' ')}</span>
        </header>
        <p className="calendar-connection-copy"><strong>Not configured.</strong> This browser demo has no Google Calendar connector, OAuth session, account identity, or successful sync history.</p>
        <dl className="calendar-connection-details">
          <div><dt>Account</dt><dd>None connected</dd></div>
          <div><dt>Last successful sync</dt><dd>None recorded</dd></div>
          <div><dt>Connection availability</dt><dd>Unavailable until a trusted backend is configured</dd></div>
        </dl>
        <div className="calendar-connection-actions">
          <button type="button" className="u-btn u-btn-primary" disabled title="A server-side Calendar connector is not configured">Connect Google Calendar</button>
          <button type="button" className="u-btn u-btn-secondary" disabled>Sync now</button>
          <button type="button" className="u-btn u-btn-secondary" disabled>Disconnect</button>
        </div>
        <p className="calendar-connection-note">Before enabling these controls, implement the backend OAuth callback, encrypted token storage and revocation, principal-scoped event access, explicit scope consent, sync status/error reporting, and idempotent event synchronization. No token or connection state is stored in this browser.</p>
      </section>

      {/* Save Button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginTop: '8px' }}>
        <button
          onClick={() => {
            if (window.confirm('Reset all LARA IV demo tasks, reminders, approvals, jobs, activity, messages, projects, and settings in this browser to the sample data?')) {
              void resetDemoData().then(() => {
                setActiveModel('gemma:2b-instruct-q4_K_M');
                setTemperature(0.2);
                setRoutingPolicy('local_first');
                setAutonomyTier('cautious');
                setRequireExternal(true);
                setRequireDelete(true);
                setQuietHoursEnabled(true);
                setQuietStart('23:00');
                setQuietEnd('07:30');
                setDesktopNotifs(true);
                setSavedNotice(false);
                setResetNotice(true);
              });
            }
          }}
          className="u-btn u-btn-danger"
          disabled
          title="Demo reset is disabled for the persistent backend"
          style={{ padding: '8px 16px', fontSize: '12px' }}
        >
          Reset demo data
        </button>
        <button onClick={handleSave} disabled title="Settings persistence is not implemented" className="u-btn u-btn-primary" style={{ padding: '8px 24px', fontSize: '13.5px' }}>
          Save System Preferences
        </button>
      </div>
    </div>
  );
};
