import React, { useState } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
  useDroppable,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  GripVertical,
  Plus,
  Search,
  Filter,
  Calendar,
  RotateCcw,
} from 'lucide-react';

import { useAgent } from '../context/AgentContext';
import { Task, TaskStatus } from '../types';
import { PriorityBadge, RoomBadge } from '../components/common/Badge';

const LANES: Array<{ id: 'backlog' | 'in_progress' | 'done'; title: string; color: string; statuses: TaskStatus[]; target: TaskStatus }> = [
  { id: 'backlog', title: 'Backlog', color: 'var(--grey-olive)', statuses: ['inbox', 'next', 'waiting'], target: 'next' },
  { id: 'in_progress', title: 'In Progress', color: 'var(--cerulean)', statuses: ['in_progress', 'review', 'ready_to_submit'], target: 'in_progress' },
  { id: 'done', title: 'Done', color: 'var(--status-success)', statuses: ['done'], target: 'done' },
];

const DropLane: React.FC<{ id: string; style: React.CSSProperties; children: React.ReactNode }> = ({ id, style, children }) => {
  const { setNodeRef, isOver } = useDroppable({ id });
  return <div ref={setNodeRef} id={id} data-drop-active={isOver || undefined} style={style}>{children}</div>;
};

interface SortableTaskCardProps {
  task: Task;
  onSelect: (task: Task) => void;
  onStatusChange: (taskId: string, status: TaskStatus) => void;
}

const SortableTaskCard: React.FC<SortableTaskCardProps> = ({ task, onSelect, onStatusChange }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id, data: { task } });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
    backgroundColor: 'var(--surface-primary)',
    borderRadius: '8px',
    border: '1px solid var(--border-subtle)',
    boxShadow: 'var(--shadow-sm)',
    padding: '10px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    userSelect: 'none',
    cursor: 'pointer',
    position: 'relative',
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={() => onSelect(task)}
    >
      {/* Card Header with Drag Handle */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <PriorityBadge priority={task.priority} size="small" />
          <RoomBadge room={task.room} size="small" />
        </div>

        <div
          {...attributes}
          {...listeners}
          onClick={(e) => e.stopPropagation()}
          style={{
            cursor: 'grab',
            color: 'var(--grey-olive)',
            display: 'flex',
            alignItems: 'center',
            padding: '2px',
          }}
          title="Drag to reorder or change lane"
        >
          <GripVertical size={14} />
        </div>
      </div>

      {/* Task Title */}
      <div
        style={{
          fontSize: '13px',
          fontWeight: 600,
          color: 'var(--onyx)',
          lineHeight: 1.3,
        }}
      >
        {task.title}
      </div>

      {/* Task Description / Notes */}
      {task.description && (
        <div
          style={{
            fontSize: '11.5px',
            color: 'var(--text-secondary)',
            lineHeight: 1.35,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}
        >
          {task.description}
        </div>
      )}

      {/* Card Footer: Due Date, Reminders */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '11px',
          color: 'var(--text-muted)',
          paddingTop: '4px',
          borderTop: '1px solid var(--border-subtle)',
        }}
      >
        {task.dueDate ? (
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              color: task.dueDate && task.dueDate < new Date().toISOString().slice(0, 10) ? 'var(--status-danger)' : 'var(--text-muted)',
              fontWeight: task.dueDate && task.dueDate < new Date().toISOString().slice(0, 10) ? 600 : 400,
            }}
          >
            <Calendar size={12} />
            {task.dueDate}
          </span>
        ) : (
          <span />
        )}

      {task.remindersCount > 0 && (
          <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
            {task.remindersCount} reminders
          </span>
        )}
      </div>
      <label className="kanban-move-control" onClick={(event) => event.stopPropagation()}>
        <span>Move to</span>
        <select className="kanban-status-select" aria-label={`Move ${task.title} to lane`} value={task.status} onChange={(event) => onStatusChange(task.id, event.target.value as TaskStatus)}>
          <option value="inbox">Inbox</option><option value="next">Next</option><option value="in_progress">In progress</option><option value="waiting">Waiting</option><option value="review">Review</option><option value="ready_to_submit">Ready to submit</option><option value="done">Done</option><option value="archived">Archived</option>
        </select>
      </label>
    </div>
  );
};

export const KanbanWorkspace: React.FC = () => {
  const {
    tasks,
    openTaskDetail,
    transitionTask,
    reorderTasks,
    createTask,
    activeRoom,
    canUndo,
    undo,
  } = useAgent();

  const [searchFilter, setSearchFilter] = useState('');
  const [selectedRoomFilter, setSelectedRoomFilter] = useState<string>('all');
  const [activeDragTask, setActiveDragTask] = useState<Task | null>(null);
  const [moveFeedback, setMoveFeedback] = useState<{ kind: 'status' | 'error'; text: string } | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const filteredTasks = tasks.filter((t) => {
    const matchesSearch =
      t.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (t.description && t.description.toLowerCase().includes(searchFilter.toLowerCase()));
    const matchesRoom = selectedRoomFilter === 'all' || t.room === selectedRoomFilter;
    return matchesSearch && matchesRoom;
  });

  const handleTaskMove = async (taskId: string, targetStatus: TaskStatus) => {
    const validStatuses: TaskStatus[] = ['inbox', 'next', 'in_progress', 'waiting', 'review', 'ready_to_submit', 'done', 'archived'];
    if (!validStatuses.includes(targetStatus)) {
      setMoveFeedback({ kind: 'error', text: 'That destination is not a valid task status. No change was made.' });
      return;
    }
    const task = tasks.find((item) => item.id === taskId);
    if (!task) {
      setMoveFeedback({ kind: 'error', text: 'This task is no longer available. Refresh the board before moving it.' });
      return;
    }
    if (task.status === targetStatus) return;
    setMoveFeedback(null);
    try {
      const saved = await transitionTask(taskId, targetStatus);
      setMoveFeedback({ kind: 'status', text: `Moved “${saved.title}” to ${targetStatus.replace(/_/g, ' ')}. Saved in this browser.` });
    } catch {
      setMoveFeedback({ kind: 'error', text: 'The move was not saved. The task remains in its previous lane; check browser storage and try again.' });
    }
  };

  const handleTaskReorder = async (sourceIndex: number, destinationIndex: number, status: TaskStatus) => {
    setMoveFeedback(null);
    try {
      await reorderTasks(sourceIndex, destinationIndex, status);
      setMoveFeedback({ kind: 'status', text: 'Task order saved in this browser.' });
    } catch {
      setMoveFeedback({ kind: 'error', text: 'The new task order was not saved. The previous order remains.' });
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    const task = tasks.find((t) => t.id === event.active.id);
    if (task) {
      setActiveDragTask(task);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveDragTask(null);
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    const activeTask = tasks.find((t) => t.id === activeId);
    if (!activeTask) return;

    // If dropped on another task in the same lane, reorder
    const overTask = tasks.find((t) => t.id === overId);
    const destinationLane = LANES.find((lane) => lane.id === overId);
    if (destinationLane && !destinationLane.statuses.includes(activeTask.status)) {
      void handleTaskMove(activeId, destinationLane.target);
      return;
    }
    if (overTask && activeTask.status === overTask.status && activeId !== overId) {
      const laneTasks = tasks.filter((t) => t.status === activeTask.status);
      const sourceIndex = laneTasks.findIndex((t) => t.id === activeId);
      const destIndex = laneTasks.findIndex((t) => t.id === overId);
      if (sourceIndex !== -1 && destIndex !== -1) {
        void handleTaskReorder(sourceIndex, destIndex, activeTask.status);
      }
      } else if (overTask && activeTask.status !== overTask.status) {
      const targetLane = LANES.find((lane) => lane.statuses.includes(overTask.status));
      if (targetLane && !targetLane.statuses.includes(activeTask.status)) void handleTaskMove(activeId, targetLane.target);
    }
  };

  const handleQuickAdd = (status: TaskStatus) => {
    const title = prompt(`Add a task to "${status.replace(/_/g, ' ')}":`);
    if (title && title.trim()) {
      createTask({
        title: title.trim(),
        room: activeRoom,
        category: 'Personal/Admin',
        priority: 'medium',
      }).then((created) => {
        if (created.status !== status) {
          transitionTask(created.id, status);
        }
      });
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--app-canvas)',
        overflow: 'hidden',
      }}
    >
      {moveFeedback && <p className={`kanban-move-feedback ${moveFeedback.kind === 'error' ? 'is-error' : ''}`} role={moveFeedback.kind === 'error' ? 'alert' : 'status'}>{moveFeedback.text}</p>}
      {/* Top Filter Bar */}
      <div
        style={{
          padding: '12px 20px',
          backgroundColor: 'var(--surface-primary)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, maxWidth: '460px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 10px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
              flex: 1,
            }}
          >
            <Search size={14} color="var(--grey-olive)" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Filter tasks on board..."
              style={{
                border: 'none',
                outline: 'none',
                backgroundColor: 'transparent',
                fontSize: '12px',
                width: '100%',
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={14} color="var(--grey-olive)" />
            <select
              value={selectedRoomFilter}
              onChange={(e) => setSelectedRoomFilter(e.target.value)}
              style={{
                padding: '6px 8px',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--surface-subtle)',
                fontSize: '12px',
              }}
            >
              <option value="all">All Rooms</option>
              <option value="academic">Academic</option>
              <option value="projects">Projects</option>
              <option value="opportunities">Opportunities</option>
              <option value="operations">Operations</option>
              <option value="public_research">Public Research</option>
              <option value="personal_vault">Personal Vault</option>
              <option value="health">Health</option>
            </select>
          </div>
        </div>

        {canUndo && (
          <button
            onClick={() => undo()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              backgroundColor: 'var(--surface-warm)',
              color: 'var(--onyx)',
              borderRadius: '6px',
              border: '1px solid var(--border-strong)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <RotateCcw size={13} />
            Undo Last Move
          </button>
        )}
      </div>

      {/* Three workflow lanes; supported review and waiting states remain visible on each card. */}
      <div
        style={{
          flex: 1,
          overflowX: 'auto',
          overflowY: 'hidden',
          padding: '16px 20px',
          display: 'flex',
          gap: '14px',
        }}
      >
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          {LANES.map((lane) => {
            const laneTasks = filteredTasks.filter((t) => lane.statuses.includes(t.status));
            return (
              <DropLane
                key={lane.id}
                id={lane.id}
                style={{
                  width: '280px',
                  minWidth: '280px',
                  backgroundColor: 'var(--surface-secondary)',
                  borderRadius: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  maxHeight: '100%',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                {/* Lane Header */}
                <div
                  style={{
                    padding: '12px 14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderBottom: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: lane.color,
                      }}
                    />
                    <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--onyx)' }}>
                      {lane.title}
                    </span>
                    <span
                      style={{
                        fontSize: '11px',
                        fontFamily: 'var(--font-mono)',
                        padding: '1px 6px',
                        borderRadius: '10px',
                        backgroundColor: 'var(--surface-primary)',
                        color: 'var(--text-secondary)',
                        fontWeight: 600,
                      }}
                    >
                      {laneTasks.length}
                    </span>
                  </div>

                  <button
                    onClick={() => handleQuickAdd(lane.target)}
                    style={{
                      padding: '2px',
                      borderRadius: '4px',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                    }}
                    title={`Add task to ${lane.title}`}
                  >
                    <Plus size={15} />
                  </button>
                </div>

                {/* Sortable Tasks List */}
                <div
                  style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '10px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                  }}
                >
                  <SortableContext
                    items={laneTasks.map((t) => t.id)}
                    strategy={verticalListSortingStrategy}
                  >
                    {laneTasks.map((task) => (
                      <SortableTaskCard
                        key={task.id}
                        task={task}
                        onSelect={openTaskDetail}
                        onStatusChange={(taskId, status) => { void transitionTask(taskId, status); }}
                      />
                    ))}
                  </SortableContext>

                  {laneTasks.length === 0 && (
                    <div
                      style={{
                        padding: '24px 12px',
                        textAlign: 'center',
                        color: 'var(--text-muted)',
                        fontSize: '11.5px',
                        border: '1px dashed var(--border-subtle)',
                        borderRadius: '6px',
                      }}
                    >
                      No tasks in this lane
                    </div>
                  )}
                </div>
              </DropLane>
            );
          })}

          <DragOverlay>
            {activeDragTask ? (
              <div
                style={{
                  backgroundColor: 'var(--surface-primary)',
                  borderRadius: '8px',
                  border: '2px solid var(--cerulean)',
                  boxShadow: 'var(--shadow-lg)',
                  padding: '10px 12px',
                  width: '260px',
                }}
              >
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--onyx)' }}>
                  {activeDragTask.title}
                </div>
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>
    </div>
  );
};
