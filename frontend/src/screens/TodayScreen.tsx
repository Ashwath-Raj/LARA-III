import React from 'react';
import {
  Calendar,
  Bell,
  AlertTriangle,
  Cpu,
  Database,
  ShieldCheck,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

import { useAgent } from '../context/AgentContext';
import { TaskCard } from '../components/task/TaskCard';
import { Button } from '../components/common/Button';

export const TodayScreen: React.FC = () => {
  const {
    tasks,
    reminders,
    approvals,
    jobs,
    snoozeReminder,
    dismissReminder,
    setIsQuickCaptureOpen,
    setActiveScreen,
  } = useAgent();

  // Filter tasks due today or urgent
  const dueTodayTasks = tasks.filter(
    (t) =>
      t.dueDate === '2026-10-10' ||
      t.dueDate === '2026-10-11' ||
      t.status === 'ready_to_submit'
  );

  const pendingApprovals = approvals.filter((a) => a.status === 'pending');
  const upcomingReminders = reminders.filter(
    (r) => r.status === 'scheduled' || r.status === 'snoozed'
  );
  const activeJobs = jobs.filter((j) => j.status === 'executing' || j.status === 'awaiting_approval');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner: Quick Summary & Status Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '14px',
        }}
      >
        <div className="u-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Due Today & Ready
            </span>
            <Calendar size={16} color="var(--accent)" />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--onyx)', marginTop: '6px' }}>
            {dueTodayTasks.length}
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Includes 1 staged Classroom submission
          </div>
        </div>

        <div className="u-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Active Reminders
            </span>
            <Bell size={16} color="var(--status-warning)" />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--onyx)', marginTop: '6px' }}>
            {upcomingReminders.length}
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Next alert: 20:00 (Classroom check)
          </div>
        </div>

        <div className="u-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Pending Approvals
            </span>
            <AlertTriangle size={16} color="var(--status-danger)" />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--onyx)', marginTop: '6px' }}>
            {pendingApprovals.length}
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--status-danger)', marginTop: '2px' }}>
            {pendingApprovals.length > 0 ? 'Action required in Activity' : 'All cleared'}
          </div>
        </div>

        <div className="u-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Running Agent Jobs
            </span>
            <Cpu size={16} color="var(--status-success)" />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--onyx)', marginTop: '6px' }}>
            {activeJobs.length}
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Bounded local-only executions
          </div>
        </div>
      </div>

      {/* Quick Capture Prominent Action Area */}
      <div
        className="u-paper-surface"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          padding: '16px 20px',
          backgroundColor: 'var(--surface-warm)',
          borderColor: 'rgba(18, 22, 25, 0.14)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--cerulean)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF',
            }}
          >
            <Sparkles size={18} />
          </div>
          <div>
            <div style={{ fontSize: '14.5px', fontWeight: 700, color: 'var(--onyx)' }}>
              Natural-Language Task & Deadline Capture
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Say &ldquo;My Algorithms assignment is due on 14 October, attach assignment3_solutions.pdf&rdquo; to parse and schedule.
            </div>
          </div>
        </div>

        <Button
          variant="primary"
          onClick={() => setIsQuickCaptureOpen(true)}
          icon={<Sparkles size={14} />}
        >
          Quick Capture (Ctrl+K)
        </Button>
      </div>

      {/* Main Two-Column Layout: Due Today & Upcoming Reminders */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '24px' }}>
        {/* Left Column: Tasks Due Today */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--onyx)' }}>
              Deadlines & Immediate Tasks ({dueTodayTasks.length})
            </h2>
            <button
              onClick={() => setActiveScreen('kanban')}
              className="u-btn u-btn-ghost"
              style={{ fontSize: '12px' }}
            >
              Open Kanban Board <ArrowRight size={13} />
            </button>
          </div>

          {dueTodayTasks.length === 0 ? (
            <div className="u-card" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
              No tasks due today. All coursework and deliverables are up to date!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {dueTodayTasks.map((t) => (
                <TaskCard key={t.id} task={t} />
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Upcoming Reminders & Local-System Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Reminders List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--onyx)' }}>
                Upcoming Reminders ({upcomingReminders.length})
              </h2>
              <button
                onClick={() => setActiveScreen('reminders')}
                className="u-btn u-btn-ghost"
                style={{ fontSize: '12px' }}
              >
                View all
              </button>
            </div>

            <div className="u-card" style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {upcomingReminders.length === 0 ? (
                <div style={{ padding: '16px', textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                  No upcoming reminders queued.
                </div>
              ) : (
                upcomingReminders.slice(0, 4).map((rem) => (
                  <div
                    key={rem.id}
                    style={{
                      padding: '10px 12px',
                      backgroundColor: 'var(--surface-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '13px', fontWeight: 650, color: 'var(--onyx)' }}>
                        {rem.title}
                      </span>
                      <span
                        style={{
                          fontSize: '11px',
                          color: rem.status === 'snoozed' ? 'var(--status-warning)' : 'var(--accent)',
                          fontWeight: 600,
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {rem.status.toUpperCase()}
                      </span>
                    </div>

                    {rem.taskTitle && (
                      <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                        Task: {rem.taskTitle}
                      </div>
                    )}

                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginTop: '4px',
                        paddingTop: '4px',
                        borderTop: '1px solid var(--border-subtle)',
                      }}
                    >
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        Time: {new Date(rem.remindAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button
                          onClick={() => snoozeReminder(rem.id, 30)}
                          className="u-btn u-btn-secondary"
                          style={{ fontSize: '10px', padding: '2px 6px' }}
                        >
                          Snooze
                        </button>
                        <button
                          onClick={() => dismissReminder(rem.id)}
                          className="u-btn u-btn-ghost"
                          style={{ fontSize: '10px', padding: '2px 6px' }}
                        >
                          Dismiss
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Local System Status Widget */}
          <div
            className="u-card"
            style={{
              padding: '16px',
              backgroundColor: 'var(--surface-primary)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--onyx)' }}>
                Local System & Privacy Status
              </span>
              <span
                style={{
                  fontSize: '10px',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                SIMULATED
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
                  <Cpu size={14} color="var(--status-success)" />
                  Ollama Local Inference
                </span>
                <span style={{ fontWeight: 600, color: 'var(--status-success)', fontFamily: 'var(--font-mono)' }}>
                  Gemma 2B · Simulated
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
                  <Database size={14} color="var(--accent)" />
                  SQLite State DB
                </span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  Healthy (42 rows)
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'space-between' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
                  <ShieldCheck size={14} color="var(--accent)" />
                  Execution Security
                </span>
                <span style={{ fontWeight: 600, color: 'var(--status-success)', fontFamily: 'var(--font-mono)' }}>
                  Guarded · No Root Shell
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
