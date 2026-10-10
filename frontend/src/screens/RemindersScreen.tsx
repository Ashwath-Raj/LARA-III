import React, { useState } from 'react';
import {
  Bell,
  Clock,
  Plus,
  CheckCircle,
  AlertCircle,
  RotateCcw,
  Calendar,
} from 'lucide-react';

import { useAgent } from '../context/AgentContext';
import { ReminderStatus } from '../types';

export const RemindersScreen: React.FC = () => {
  const {
    reminders,
    tasks,
    snoozeReminder,
    dismissReminder,
    cancelReminder,
    createReminder,
    openTaskDetail,
  } = useAgent();

  const [filter, setFilter] = useState<ReminderStatus | 'all'>('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [selectedTaskId, setSelectedTaskId] = useState('');
  const [newRemindTime, setNewRemindTime] = useState('');

  const filteredReminders = reminders.filter((r) => {
    if (filter === 'all') return true;
    return r.status === filter;
  });

  const handleAdd = () => {
    if (!newTitle.trim()) return;
    const timeIso = newRemindTime || new Date(Date.now() + 3600 * 1000).toISOString();
    createReminder(selectedTaskId || '', newTitle, timeIso);
    setNewTitle('');
    setSelectedTaskId('');
    setNewRemindTime('');
    setShowAddModal(false);
  };

  const getStatusBadge = (status: ReminderStatus) => {
    switch (status) {
      case 'scheduled':
        return (
          <span className="u-badge" style={{ backgroundColor: 'rgba(0, 117, 162, 0.12)', color: 'var(--accent)' }}>
            <Clock size={11} /> Scheduled
          </span>
        );
      case 'snoozed':
        return (
          <span className="u-badge" style={{ backgroundColor: 'rgba(153, 98, 0, 0.14)', color: 'var(--status-warning)' }}>
            <RotateCcw size={11} /> Snoozed (+30m)
          </span>
        );
      case 'delivered':
        return (
          <span className="u-badge" style={{ backgroundColor: 'rgba(29, 115, 55, 0.14)', color: 'var(--status-success)' }}>
            <CheckCircle size={11} /> Delivered
          </span>
        );
      case 'missed':
        return (
          <span className="u-badge" style={{ backgroundColor: 'rgba(181, 43, 39, 0.12)', color: 'var(--status-danger)' }}>
            <AlertCircle size={11} /> Missed (Offline)
          </span>
        );
      case 'dismissed':
        return (
          <span className="u-badge" style={{ backgroundColor: 'rgba(18, 22, 25, 0.08)', color: 'var(--text-muted)' }}>
            Dismissed
          </span>
        );
      case 'cancelled':
        return <span className="u-badge" style={{ backgroundColor: 'rgba(18, 22, 25, 0.08)', color: 'var(--text-muted)' }}>Cancelled</span>;
      default:
        return null;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Filter Bar & Actions */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {(['all', 'scheduled', 'snoozed', 'delivered', 'missed', 'dismissed'] as const).map(
            (st) => {
              const count =
                st === 'all'
                  ? reminders.length
                  : reminders.filter((r) => r.status === st).length;
              const isSelected = filter === st;

              return (
                <button
                  key={st}
                  onClick={() => setFilter(st)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '12px',
                    fontWeight: isSelected ? 650 : 500,
                    backgroundColor: isSelected ? 'var(--cerulean)' : 'var(--surface-primary)',
                    color: isSelected ? '#FFFFFF' : 'var(--text-primary)',
                    border: isSelected ? '1px solid var(--cerulean)' : '1px solid var(--border-subtle)',
                  }}
                >
                  {st.charAt(0).toUpperCase() + st.slice(1)} ({count})
                </button>
              );
            }
          )}
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="u-btn u-btn-primary"
          style={{ fontSize: '12.5px' }}
        >
          <Plus size={14} /> Schedule Reminder
        </button>
      </div>

      {/* Add Reminder Inline Form */}
      {showAddModal && (
        <div
          className="u-card"
          style={{
            padding: '16px 20px',
            backgroundColor: 'var(--surface-primary)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--onyx)' }}>
            Schedule New Desktop Reminder
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '10px' }}>
            <input
              type="text"
              placeholder="Reminder label (e.g. Turn in Algorithms Assignment 3)"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              style={{
                padding: '8px 10px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                fontSize: '13px',
              }}
            />

            <select
              value={selectedTaskId}
              onChange={(e) => setSelectedTaskId(e.target.value)}
              style={{
                padding: '8px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                fontSize: '12.5px',
              }}
            >
              <option value="">Link to Task (Optional)</option>
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>

            <input
              type="datetime-local"
              value={newRemindTime}
              onChange={(e) => setNewRemindTime(e.target.value)}
              style={{
                padding: '8px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                fontSize: '12px',
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
            <button
              onClick={() => setShowAddModal(false)}
              className="u-btn u-btn-ghost"
              style={{ fontSize: '12px' }}
            >
              Cancel
            </button>
            <button
              onClick={handleAdd}
              className="u-btn u-btn-primary"
              style={{ fontSize: '12px' }}
            >
              Save Schedule
            </button>
          </div>
        </div>
      )}

      {/* Reminders Cards List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {filteredReminders.length === 0 ? (
          <div className="u-card" style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No reminders found matching the selected filter.
          </div>
        ) : (
          filteredReminders.map((rem) => {
            const linkedTask = rem.taskId ? tasks.find((t) => t.id === rem.taskId) : null;

            return (
              <div
                key={rem.id}
                className="u-card"
                style={{
                  padding: '16px 20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '16px',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', minWidth: 0, flex: 1 }}>
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: 'rgba(0, 117, 162, 0.08)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--accent)',
                      flexShrink: 0,
                      marginTop: '2px',
                    }}
                  >
                    <Bell size={16} />
                  </div>

                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <h3 style={{ fontSize: '14.5px', fontWeight: 650, color: 'var(--onyx)' }}>
                        {rem.title}
                      </h3>
                      {getStatusBadge(rem.status)}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Calendar size={13} />
                        Scheduled: {new Date(rem.remindAt).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                      </span>

                      {rem.snoozeUntil && (
                        <span style={{ color: 'var(--status-warning)' }}>
                          Snoozed until: {new Date(rem.snoozeUntil).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}

                      {linkedTask && (
                        <button
                          onClick={() => openTaskDetail(linkedTask)}
                          style={{
                            color: 'var(--accent)',
                            fontWeight: 600,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '3px',
                          }}
                        >
                          Task: {linkedTask.title}
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {rem.status === 'scheduled' && (
                    <>
                      <button
                        onClick={() => snoozeReminder(rem.id, 30)}
                        className="u-btn u-btn-secondary"
                        style={{ fontSize: '12px', padding: '5px 10px' }}
                      >
                        Snooze 30m
                      </button>
                      <button
                        onClick={() => snoozeReminder(rem.id, 120)}
                        className="u-btn u-btn-secondary"
                        style={{ fontSize: '12px', padding: '5px 10px' }}
                      >
                        Snooze 2h
                      </button>
                      <button
                        onClick={() => dismissReminder(rem.id)}
                        className="u-btn u-btn-ghost"
                        style={{ fontSize: '12px', padding: '5px 10px' }}
                      >
                        Dismiss
                      </button>
                      <button
                        onClick={() => cancelReminder(rem.id)}
                        className="u-btn u-btn-ghost"
                        style={{ fontSize: '12px', padding: '5px 10px' }}
                      >
                        Cancel reminder
                      </button>
                    </>
                  )}
                  {rem.status === 'snoozed' && (
                    <button
                      onClick={() => dismissReminder(rem.id)}
                      className="u-btn u-btn-ghost"
                      style={{ fontSize: '12px', padding: '5px 10px' }}
                    >
                      Dismiss
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
