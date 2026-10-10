import React from 'react';
import { Plus } from 'lucide-react';
import { useAgent } from '../context/AgentContext';
import { TaskCard } from '../components/task/TaskCard';
import { TaskStatus } from '../types';

interface KanbanColumnDef {
  id: string;
  title: string;
  statuses: TaskStatus[];
  headerColor: string;
  defaultTargetStatus: TaskStatus;
}

const COLUMNS: KanbanColumnDef[] = [
  {
    id: 'backlog',
    title: 'Backlog / Next',
    statuses: ['inbox', 'next'],
    headerColor: 'var(--text-secondary)',
    defaultTargetStatus: 'next',
  },
  {
    id: 'in_progress',
    title: 'In Progress',
    statuses: ['in_progress'],
    headerColor: 'var(--accent)',
    defaultTargetStatus: 'in_progress',
  },
  {
    id: 'waiting',
    title: 'Waiting / Blocked',
    statuses: ['waiting'],
    headerColor: 'var(--status-warning)',
    defaultTargetStatus: 'waiting',
  },
  {
    id: 'ready_to_submit',
    title: 'Ready to Submit',
    statuses: ['ready_to_submit', 'review'],
    headerColor: 'var(--status-success)',
    defaultTargetStatus: 'ready_to_submit',
  },
  {
    id: 'done',
    title: 'Done',
    statuses: ['done'],
    headerColor: 'var(--status-success)',
    defaultTargetStatus: 'done',
  },
];

export const KanbanScreen: React.FC = () => {
  const { tasks, searchQuery, setIsQuickCaptureOpen } = useAgent();

  const filteredTasks = tasks.filter((t) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      t.title.toLowerCase().includes(q) ||
      t.category.toLowerCase().includes(q) ||
      t.course?.toLowerCase().includes(q) ||
      t.description?.toLowerCase().includes(q)
    );
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Kanban Board Horizontal Scrolling Lanes */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, minmax(260px, 1fr))',
          gap: '16px',
          alignItems: 'start',
          paddingBottom: '32px',
          overflowX: 'auto',
        }}
      >
        {COLUMNS.map((col) => {
          const colTasks = filteredTasks.filter((t) => col.statuses.includes(t.status));

          return (
            <div
              key={col.id}
              style={{
                backgroundColor: 'var(--surface-secondary)',
                borderRadius: 'var(--radius-md)',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                minHeight: '580px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {/* Column Header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: '8px',
                  borderBottom: '1px solid rgba(18, 22, 25, 0.08)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: col.headerColor,
                      display: 'inline-block',
                    }}
                  />
                  <h2
                    style={{
                      fontSize: '13.5px',
                      fontWeight: 700,
                      color: 'var(--onyx)',
                    }}
                  >
                    {col.title}
                  </h2>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      backgroundColor: 'rgba(18, 22, 25, 0.08)',
                      padding: '1px 6px',
                      borderRadius: 'var(--radius-full)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {colTasks.length}
                  </span>
                  <button
                    onClick={() => setIsQuickCaptureOpen(true)}
                    aria-label={`Add task to ${col.title}`}
                    style={{
                      padding: '2px',
                      borderRadius: 'var(--radius-xs)',
                      color: 'var(--text-muted)',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                  >
                    <Plus size={14} />
                  </button>
                </div>
              </div>

              {/* Cards Container */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  flex: 1,
                }}
              >
                {colTasks.length === 0 ? (
                  <div
                    style={{
                      padding: '24px 12px',
                      textAlign: 'center',
                      fontSize: '11.5px',
                      color: 'var(--text-muted)',
                      border: '1px dashed var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    No tasks in lane
                  </div>
                ) : (
                  colTasks.map((task) => (
                    <TaskCard key={task.id} task={task} showMoveControls />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
