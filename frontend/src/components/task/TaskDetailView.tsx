import React, { useState } from 'react';
import {
  Calendar,
  Clock,
  FileText,
  Trash2,
  CheckCircle2,
  ExternalLink,
  Shield,
  Plus,
} from 'lucide-react';

import { Task, TaskStatus, TaskPriority } from '../../types';
import { useAgent } from '../../context/AgentContext';

interface TaskDetailViewProps {
  task: Task;
  onClose: () => void;
}

export const TaskDetailView: React.FC<TaskDetailViewProps> = ({ task, onClose }) => {
  const {
    updateTask,
    transitionTask,
    deleteTask,
    reminders,
    createReminder,
    snoozeReminder,
    dismissReminder,
  } = useAgent();

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [nextAction, setNextAction] = useState(task.nextAction || '');
  const [dueDate, setDueDate] = useState(task.dueDate || '');
  const [personalTargetDate, setPersonalTargetDate] = useState(task.personalTargetDate || '');
  const [newReminderTitle, setNewReminderTitle] = useState('');
  const [newReminderTime, setNewReminderTime] = useState('');
  const [showAddReminder, setShowAddReminder] = useState(false);
  const [classroomSimState, setClassroomSimState] = useState<
    'prepared' | 'submitted' | 'submission_verified'
  >(task.classroomMetadata?.submissionState === 'submitted' ? 'submitted' : 'prepared');

  const taskReminders = reminders.filter((r) => r.taskId === task.id);

  const handleSaveDetails = () => {
    updateTask(task.id, {
      title,
      nextAction: nextAction || undefined,
      dueDate: dueDate || undefined,
      personalTargetDate: personalTargetDate || undefined,
    });
    setIsEditingTitle(false);
  };

  const handleStatusChange = (newStatus: TaskStatus) => {
    transitionTask(task.id, newStatus);
  };

  const handlePriorityChange = (newPriority: TaskPriority) => {
    updateTask(task.id, { priority: newPriority });
  };

  const handleDelete = () => {
    if (confirm(`Are you sure you want to delete task "${task.title}"?`)) {
      deleteTask(task.id);
      onClose();
    }
  };

  const handleAddReminder = () => {
    if (!newReminderTitle.trim()) return;
    const timeIso = newReminderTime || new Date(Date.now() + 2 * 3600 * 1000).toISOString();
    createReminder(task.id, newReminderTitle, timeIso);
    setNewReminderTitle('');
    setNewReminderTime('');
    setShowAddReminder(false);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Title & Status Bar */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            ID: {task.id}
          </span>
          <button
            onClick={handleDelete}
            className="u-btn u-btn-danger"
            style={{ padding: '3px 8px', fontSize: '11px' }}
            title="Delete Task"
          >
            <Trash2 size={12} />
            Delete
          </button>
        </div>

        {isEditingTitle ? (
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{
                flex: 1,
                padding: '6px 8px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                fontSize: '14px',
                fontWeight: 650,
              }}
            />
            <button
              onClick={handleSaveDetails}
              className="u-btn u-btn-primary"
              style={{ fontSize: '12px' }}
            >
              Save
            </button>
          </div>
        ) : (
          <h2
            onClick={() => setIsEditingTitle(true)}
            style={{
              fontSize: '17px',
              fontWeight: 700,
              color: 'var(--onyx)',
              lineHeight: 1.35,
              cursor: 'pointer',
            }}
            title="Click to edit title"
          >
            {task.title}
          </h2>
        )}
      </div>

      {/* Status & Priority Selectors */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
          padding: '12px',
          backgroundColor: 'var(--surface-subtle)',
          borderRadius: 'var(--radius-sm)',
        }}
      >
        <div>
          <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
            Workflow Lane
          </label>
          <select
            value={task.status}
            onChange={(e) => handleStatusChange(e.target.value as TaskStatus)}
            style={{
              width: '100%',
              padding: '6px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: '#FFFFFF',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            <option value="inbox">Inbox</option>
            <option value="next">Next</option>
            <option value="in_progress">In Progress</option>
            <option value="waiting">Waiting / Blocked</option>
            <option value="review">Review</option>
            <option value="ready_to_submit">Ready to Submit</option>
            <option value="done">Done</option>
            <option value="archived">Archived</option>
          </select>
        </div>

        <div>
          <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
            Priority
          </label>
          <select
            value={task.priority}
            onChange={(e) => handlePriorityChange(e.target.value as TaskPriority)}
            style={{
              width: '100%',
              padding: '6px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: '#FFFFFF',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            <option value="high">High Priority</option>
            <option value="medium">Medium Priority</option>
            <option value="low">Low Priority</option>
          </select>
        </div>
      </div>

      {/* Dates Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--onyx)' }}>
          Deadlines & Targets
        </span>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Calendar size={12} />
              Official Due Date
            </span>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => {
                setDueDate(e.target.value);
                updateTask(task.id, { dueDate: e.target.value });
              }}
              style={{
                width: '100%',
                padding: '4px 6px',
                marginTop: '3px',
                fontSize: '12px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
              }}
            />
          </div>

          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={12} />
              Personal Target
            </span>
            <input
              type="date"
              value={personalTargetDate}
              onChange={(e) => {
                setPersonalTargetDate(e.target.value);
                updateTask(task.id, { personalTargetDate: e.target.value });
              }}
              style={{
                width: '100%',
                padding: '4px 6px',
                marginTop: '3px',
                fontSize: '12px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
              }}
            />
          </div>
        </div>
      </div>

      {/* Next Action Box */}
      <div>
        <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--onyx)', display: 'block', marginBottom: '4px' }}>
          Concrete Next Action
        </span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <input
            type="text"
            value={nextAction}
            onChange={(e) => setNextAction(e.target.value)}
            placeholder="e.g. Run tests on question 2 solutions"
            style={{
              flex: 1,
              padding: '6px 8px',
              fontSize: '12.5px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border-subtle)',
            }}
          />
          <button
            onClick={handleSaveDetails}
            className="u-btn u-btn-secondary"
            style={{ fontSize: '11.5px', padding: '4px 8px' }}
          >
            Save
          </button>
        </div>
      </div>

      {/* Classroom Workflow if applicable */}
      {task.classroomMetadata && (
        <div
          style={{
            padding: '14px',
            backgroundColor: 'var(--surface-warm)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(18, 22, 25, 0.12)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--onyx)', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <ExternalLink size={13} color="var(--accent)" />
              Google Classroom Workflow
            </span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 650,
                color:
                  classroomSimState === 'submission_verified'
                    ? 'var(--status-success)'
                    : classroomSimState === 'submitted'
                    ? 'var(--accent-text)'
                    : 'var(--status-warning)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              STATE: {classroomSimState.toUpperCase()}
            </span>
          </div>

          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            <div>Course: <strong>{task.classroomMetadata.courseName}</strong></div>
            <div>Assignment: <strong>{task.classroomMetadata.assignmentName}</strong></div>
          </div>

          {/* Staged submission simulation controls */}
          <div
            style={{
              paddingTop: '8px',
              borderTop: '1px solid rgba(18, 22, 25, 0.08)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Simulation Control (Explicit Guarded Turn-In):
            </div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <button
                onClick={() => setClassroomSimState('prepared')}
                className="u-btn u-btn-secondary"
                style={{ fontSize: '11px', padding: '3px 8px' }}
              >
                Reset to Prepared
              </button>
              <button
                onClick={() => setClassroomSimState('submitted')}
                className="u-btn u-btn-secondary"
                style={{ fontSize: '11px', padding: '3px 8px' }}
              >
                Simulate Turn-In
              </button>
              <button
                onClick={() => setClassroomSimState('submission_verified')}
                className="u-btn u-btn-primary"
                style={{ fontSize: '11px', padding: '3px 8px' }}
              >
                <CheckCircle2 size={12} />
                Verify Submission State
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Attached Local Files */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--onyx)' }}>
            Attached Files & Workspaces ({task.attachments.length})
          </span>
        </div>

        {task.attachments.length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
            No files attached to this task.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {task.attachments.map((file, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  backgroundColor: 'var(--surface-subtle)',
                  borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                  <FileText size={13} color="var(--accent)" />
                  <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {file.name}
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                    ({file.size})
                  </span>
                </div>
                {file.verified && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '2px',
                      color: 'var(--status-success)',
                      fontSize: '11px',
                      fontWeight: 600,
                    }}
                  >
                    <CheckCircle2 size={12} /> Verified
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Reminders Timeline */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--onyx)' }}>
            Reminders ({taskReminders.length})
          </span>
          <button
            onClick={() => setShowAddReminder(!showAddReminder)}
            className="u-btn u-btn-ghost"
            style={{ fontSize: '11.5px', padding: '2px 6px' }}
          >
            <Plus size={12} /> Add Reminder
          </button>
        </div>

        {showAddReminder && (
          <div
            style={{
              padding: '10px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '8px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <input
              type="text"
              placeholder="Reminder note (e.g. Check draft)"
              value={newReminderTitle}
              onChange={(e) => setNewReminderTitle(e.target.value)}
              style={{
                width: '100%',
                padding: '4px 6px',
                fontSize: '12px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
              }}
            />
            <div style={{ display: 'flex', gap: '6px' }}>
              <input
                type="datetime-local"
                value={newReminderTime}
                onChange={(e) => setNewReminderTime(e.target.value)}
                style={{
                  flex: 1,
                  padding: '4px 6px',
                  fontSize: '11px',
                  borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--border-subtle)',
                }}
              />
              <button
                onClick={handleAddReminder}
                className="u-btn u-btn-primary"
                style={{ fontSize: '11px', padding: '3px 8px' }}
              >
                Schedule
              </button>
            </div>
          </div>
        )}

        {taskReminders.length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            No persistent reminders configured for this task.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {taskReminders.map((rem) => (
              <div
                key={rem.id}
                style={{
                  padding: '8px 10px',
                  backgroundColor: 'var(--surface-subtle)',
                  borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px',
                  fontSize: '12px',
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: 'var(--onyx)' }}>{rem.title}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {new Date(rem.remindAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · Status: {rem.status}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '4px' }}>
                  {rem.status === 'scheduled' && (
                    <>
                      <button
                        onClick={() => snoozeReminder(rem.id, 30)}
                        className="u-btn u-btn-secondary"
                        style={{ fontSize: '10px', padding: '2px 5px' }}
                      >
                        Snooze 30m
                      </button>
                      <button
                        onClick={() => dismissReminder(rem.id)}
                        className="u-btn u-btn-ghost"
                        style={{ fontSize: '10px', padding: '2px 5px' }}
                      >
                        Dismiss
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Room Sensitivity & Policy Footer */}
      <div
        style={{
          padding: '10px 12px',
          backgroundColor: 'var(--surface-subtle)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-subtle)',
          fontSize: '11.5px',
          color: 'var(--text-secondary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <Shield size={14} color="var(--accent)" />
        <span>Stored in <strong>{task.room}</strong> room. Restricted from cloud inference by default.</span>
      </div>
    </div>
  );
};
