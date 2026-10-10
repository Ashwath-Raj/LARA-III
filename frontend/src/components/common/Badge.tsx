import React from 'react';
import { TaskPriority, TaskStatus, KnowledgeRoom, RoomSensitivity } from '../../types';

export const PriorityBadge: React.FC<{ priority: TaskPriority; size?: 'small' | 'medium' }> = ({
  priority,
  size,
}) => {
  const isSmall = size === 'small';
  const style: React.CSSProperties = isSmall ? { fontSize: '10px', padding: '1px 5px' } : {};

  if (priority === 'high') {
    return (
      <span className="u-badge u-badge-priority-high" style={style}>
        ● High Priority
      </span>
    );
  }
  if (priority === 'medium') {
    return (
      <span className="u-badge u-badge-priority-med" style={style}>
        ▲ Med Priority
      </span>
    );
  }
  return (
    <span className="u-badge u-badge-priority-low" style={style}>
      ▽ Low Priority
    </span>
  );
};

export const StatusBadge: React.FC<{ status: TaskStatus; size?: 'small' | 'medium' }> = ({
  status,
  size,
}) => {
  const labels: Record<TaskStatus, { label: string; bg: string; color: string }> = {
    inbox: { label: 'Inbox', bg: 'rgba(18, 22, 25, 0.08)', color: 'var(--text-secondary)' },
    next: { label: 'Next Action', bg: 'rgba(0, 117, 162, 0.12)', color: 'var(--accent-text)' },
    in_progress: { label: 'In Progress', bg: 'rgba(0, 117, 162, 0.16)', color: 'var(--accent)' },
    waiting: { label: 'Waiting / Blocked', bg: 'rgba(153, 98, 0, 0.14)', color: 'var(--status-warning)' },
    review: { label: 'Under Review', bg: 'rgba(18, 22, 25, 0.10)', color: 'var(--text-primary)' },
    ready_to_submit: { label: 'Ready to Submit', bg: 'rgba(29, 115, 55, 0.14)', color: 'var(--status-success)' },
    done: { label: 'Done', bg: 'rgba(29, 115, 55, 0.16)', color: 'var(--status-success)' },
    archived: { label: 'Archived', bg: 'rgba(18, 22, 25, 0.06)', color: 'var(--text-muted)' },
  };

  const current = labels[status] || { label: status, bg: '#eee', color: '#333' };
  const isSmall = size === 'small';

  return (
    <span
      className="u-badge"
      style={{
        backgroundColor: current.bg,
        color: current.color,
        ...(isSmall ? { fontSize: '10px', padding: '1px 5px' } : {}),
      }}
    >
      {current.label}
    </span>
  );
};

export const RoomBadge: React.FC<{ room: KnowledgeRoom; size?: 'small' | 'medium' }> = ({
  room,
  size,
}) => {
  const displayNames: Record<KnowledgeRoom, string> = {
    academic: 'Academic',
    projects: 'Projects',
    operations: 'Operations',
    public_research: 'Public Research',
    opportunities: 'Opportunities',
    personal_vault: 'Personal Vault',
    health: 'Health',
  };

  const isSmall = size === 'small';

  return (
    <span
      className="u-badge u-badge-room"
      style={isSmall ? { fontSize: '10px', padding: '1px 5px' } : {}}
    >
      {displayNames[room] || room}
    </span>
  );
};

export const SensitivityBadge: React.FC<{ sensitivity: RoomSensitivity }> = ({ sensitivity }) => {
  if (sensitivity === 'local_only') {
    return <span className="u-badge u-badge-sensitivity-local">🔒 Local-Only (Airgapped)</span>;
  }
  if (sensitivity === 'restricted') {
    return <span className="u-badge u-badge-sensitivity-restricted">🛡 Restricted (Bridged)</span>;
  }
  return <span className="u-badge u-badge-sensitivity-cloud">🌐 Cloud-Allowed</span>;
};
