import React, { useState } from 'react';
import {
  Calendar,
  Clock,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  FileText,
  Bell,
  GraduationCap,
} from 'lucide-react';

import { Task, TaskStatus } from '../../types';
import { PriorityBadge, StatusBadge } from '../common/Badge';
import { useAgent } from '../../context/AgentContext';

interface TaskCardProps {
  task: Task;
  onOpenDetail?: (task: Task) => void;
  showMoveControls?: boolean;
}

const STATUS_LANES: TaskStatus[] = [
  'inbox',
  'next',
  'in_progress',
  'waiting',
  'review',
  'ready_to_submit',
  'done',
  'archived',
];

export const TaskCard: React.FC<TaskCardProps> = ({
  task,
  onOpenDetail,
  showMoveControls = false,
}) => {
  const { transitionTask, openTaskDetail } = useAgent();
  const [moveError, setMoveError] = useState('');

  const handleCardClick = () => {
    if (onOpenDetail) onOpenDetail(task);
    else openTaskDetail(task);
  };

  const currentIdx = STATUS_LANES.indexOf(task.status);

  const moveToStatus = async (status: TaskStatus) => {
    setMoveError('');
    try {
      await transitionTask(task.id, status);
    } catch {
      setMoveError('Move not saved. The task remains in its current lane.');
    }
  };

  const handleMoveLeft = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (currentIdx > 0) {
      void moveToStatus(STATUS_LANES[currentIdx - 1]);
    }
  };

  const handleMoveRight = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (currentIdx < STATUS_LANES.length - 1) {
      void moveToStatus(STATUS_LANES[currentIdx + 1]);
    }
  };

  const isSticky = task.isSticky;
  const cardClass = isSticky ? 'u-card-sticky' : 'u-card';

  return (
    <div
      className={cardClass}
      onClick={handleCardClick}
      style={{
        padding: '16px',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        position: 'relative',
        borderLeft:
          task.priority === 'high'
            ? '3px solid var(--cerulean)'
            : undefined,
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
          handleCardClick();
        }
      }}
      aria-label={`Task: ${task.title}`}
    >
      {/* Top Header: Category & Priority */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span
            style={{
              fontSize: '11px',
              fontWeight: 650,
              textTransform: 'uppercase',
              color: 'var(--text-secondary)',
              letterSpacing: '0.04em',
            }}
          >
            {task.category}
          </span>
          {task.course && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px',
                fontSize: '11px',
                color: 'var(--accent-text)',
                backgroundColor: 'rgba(0, 117, 162, 0.08)',
                padding: '1px 6px',
                borderRadius: 'var(--radius-xs)',
              }}
            >
              <GraduationCap size={12} />
              {task.course.split(':')[0]}
            </span>
          )}
        </div>
        <PriorityBadge priority={task.priority} />
      </div>

      {/* Task Title */}
      <h3
        style={{
          fontSize: '14.5px',
          fontWeight: 650,
          color: 'var(--onyx)',
          lineHeight: 1.35,
        }}
      >
        {task.title}
      </h3>

      {/* Next Action Pill if exists */}
      {task.nextAction && (
        <div
          style={{
            backgroundColor: isSticky ? 'rgba(18, 22, 25, 0.06)' : 'var(--surface-subtle)',
            padding: '6px 10px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '6px',
          }}
        >
          <ArrowRight
            size={13}
            color="var(--accent)"
            style={{ marginTop: '2px', flexShrink: 0 }}
          />
          <span style={{ lineHeight: 1.3 }}>{task.nextAction}</span>
        </div>
      )}

      {/* Metadata Row: Due Date, Reminders, Attachments */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '12px',
          color: 'var(--text-muted)',
          paddingTop: '4px',
          borderTop: '1px solid rgba(18, 22, 25, 0.08)',
          marginTop: '2px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {task.dueDate ? (
            <span
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                color:
                  Boolean(task.dueDate && task.dueDate < new Date().toISOString().slice(0, 10))
                    ? 'var(--status-danger)'
                    : 'var(--text-secondary)',
                fontWeight: 600,
              }}
            >
              <Calendar size={13} />
              {task.dueDate}
            </span>
          ) : (
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={13} />
              No deadline
            </span>
          )}

          {task.attachments.length > 0 && (
            <span
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                color: 'var(--text-secondary)',
              }}
              title={`${task.attachments.length} files attached`}
            >
              <FileText size={12} />
              {task.attachments.length}
            </span>
          )}

          {task.remindersCount > 0 && (
            <span
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                color: 'var(--status-warning)',
              }}
              title={`${task.remindersCount} active reminders`}
            >
              <Bell size={12} />
              {task.remindersCount}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <StatusBadge status={task.status} />

          {/* Lane Shift Controls for Kanban & Inbox */}
          {showMoveControls && (
            <div
              style={{ display: 'flex', alignItems: 'center', gap: '2px' }}
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={handleMoveLeft}
                disabled={currentIdx <= 0}
                aria-label="Move task left"
                style={{
                  padding: '3px',
                  borderRadius: 'var(--radius-xs)',
                  color: currentIdx > 0 ? 'var(--text-primary)' : 'var(--silver)',
                  cursor: currentIdx > 0 ? 'pointer' : 'default',
                }}
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={handleMoveRight}
                disabled={currentIdx >= STATUS_LANES.length - 1}
                aria-label="Move task right"
                style={{
                  padding: '3px',
                  borderRadius: 'var(--radius-xs)',
                  color: currentIdx < STATUS_LANES.length - 1 ? 'var(--text-primary)' : 'var(--silver)',
                  cursor: currentIdx < STATUS_LANES.length - 1 ? 'pointer' : 'default',
                }}
              >
                <ChevronRight size={14} />
              </button>
            </div>
          )}
        </div>
      </div>
      {moveError && <p className="task-move-error" role="alert">{moveError}</p>}
    </div>
  );
};
