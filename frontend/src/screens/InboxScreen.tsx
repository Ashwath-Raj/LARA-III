import React, { useState } from 'react';
import {
  StickyNote,
  Plus,
} from 'lucide-react';

import { useAgent } from '../context/AgentContext';
import { TaskCard } from '../components/task/TaskCard';
import { TaskCategory, TaskPriority, TaskStatus } from '../types';

const CATEGORIES: Array<TaskCategory | 'all'> = [
  'all',
  'Academics',
  'Projects',
  'Hackathons',
  'AI/ML',
  'Robotics',
  'Quantum',
  'Opportunities',
  'Personal/Admin',
];

export const InboxScreen: React.FC = () => {
  const {
    tasks,
    searchQuery,
    setSearchQuery,
    createTask,
    setIsQuickCaptureOpen,
  } = useAgent();

  const [selectedCat, setSelectedCat] = useState<TaskCategory | 'all'>('all');
  const [selectedPriority, setSelectedPriority] = useState<TaskPriority | 'all'>('all');
  const [selectedStatus, setSelectedStatus] = useState<TaskStatus | 'all'>('inbox');
  const [sortBy, setSortBy] = useState<'deadline' | 'priority' | 'recent'>('deadline');
  const [showAddNote, setShowAddNote] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteCategory, setNoteCategory] = useState<TaskCategory>('Personal/Admin');
  const [noteError, setNoteError] = useState('');

  // Filter tasks in inbox state, or all tasks matching query
  const inboxTasks = tasks.filter((t) => {
    const matchesInbox = selectedStatus === 'all' || t.status === selectedStatus;
    const matchesCategory = selectedCat === 'all' || t.category === selectedCat;
    const matchesPriority = selectedPriority === 'all' || t.priority === selectedPriority;
    const matchesSearch =
      !searchQuery ||
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.course?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesInbox && matchesCategory && matchesPriority && matchesSearch;
  });

  const sortedTasks = [...inboxTasks].sort((a, b) => {
    if (sortBy === 'priority') return ['high', 'medium', 'low'].indexOf(a.priority) - ['high', 'medium', 'low'].indexOf(b.priority);
    if (sortBy === 'recent') return b.updatedAt.localeCompare(a.updatedAt);
    return (a.dueDate || '9999-12-31').localeCompare(b.dueDate || '9999-12-31');
  });

  const stickyNotes = sortedTasks.filter((t) => t.isSticky);
  const regularInbox = sortedTasks.filter((t) => !t.isSticky);

  const handleCreateNote = async () => {
    if (!noteTitle.trim()) return;
    setNoteError('');
    try {
      await createTask({
        title: noteTitle,
        category: noteCategory,
        room: 'operations',
        priority: 'medium',
        isSticky: true,
        stickyColor: 'beige',
        nextAction: 'Triage note or assign to project.',
      });
      setNoteTitle('');
      setShowAddNote(false);
    } catch {
      setNoteError('The note was not saved. Your title is still here; check browser storage and try again.');
    }
  };

  return (
    <div className="u-workspace-scroll inbox-workspace" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {/* Compact filters and actions */}
      <div className="inbox-toolbar"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div className="inbox-controls">
          <input className="inbox-search" type="search" aria-label="Search inbox items" placeholder="Search inbox" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} />
          <select aria-label="Filter by category" value={selectedCat} onChange={(event) => setSelectedCat(event.target.value as TaskCategory | 'all')}>
            {CATEGORIES.map((category) => <option key={category} value={category}>{category === 'all' ? 'All categories' : category}</option>)}
          </select>
          <select aria-label="Filter by status" value={selectedStatus} onChange={(event) => setSelectedStatus(event.target.value as TaskStatus | 'all')}>
            <option value="inbox">Inbox</option><option value="all">All statuses</option><option value="next">Next</option><option value="in_progress">In progress</option><option value="waiting">Waiting</option><option value="review">Review</option><option value="ready_to_submit">Ready to submit</option><option value="done">Done</option><option value="archived">Archived</option>
          </select>
          <select aria-label="Filter by priority" value={selectedPriority} onChange={(event) => setSelectedPriority(event.target.value as TaskPriority | 'all')}>
            <option value="all">All priorities</option><option value="high">High priority</option><option value="medium">Medium priority</option><option value="low">Low priority</option>
          </select>
          <select aria-label="Sort tasks" value={sortBy} onChange={(event) => setSortBy(event.target.value as typeof sortBy)}>
            <option value="deadline">Sort: deadline</option><option value="priority">Sort: priority</option><option value="recent">Sort: recently updated</option>
          </select>
          <button
            onClick={() => setShowAddNote(!showAddNote)}
            className="u-btn u-btn-secondary"
            style={{ fontSize: '12.5px' }}
          >
            <StickyNote size={14} color="var(--accent)" />
            + New Sticky Note
          </button>
          <button
            onClick={() => setIsQuickCaptureOpen(true)}
            className="u-btn u-btn-primary"
            style={{ fontSize: '12.5px' }}
          >
            <Plus size={14} />
            Quick Capture
          </button>
        </div>
      </div>

      {/* Add Sticky Note Inline Box */}
      {showAddNote && (
        <div
          className="u-card-sticky"
          style={{
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--onyx)' }}>
              Pin a Quick Thought or Note
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              Warm Paper · #E3E7D3
            </span>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="text"
              placeholder="e.g. Look into FlashAttention-3 Triton kernel benchmark results"
              value={noteTitle}
              onChange={(e) => { setNoteTitle(e.target.value); setNoteError(''); }}
              style={{
                flex: 1,
                padding: '8px 10px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: '#FFFFFF',
                fontSize: '13px',
              }}
              autoFocus
            />

            <select
              value={noteCategory}
              onChange={(e) => setNoteCategory(e.target.value as TaskCategory)}
              style={{
                padding: '8px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: '#FFFFFF',
                fontSize: '12px',
              }}
            >
              <option value="Personal/Admin">Personal/Admin</option>
              <option value="Academics">Academics</option>
              <option value="Projects">Projects</option>
              <option value="AI/ML">AI/ML</option>
              <option value="Quantum">Quantum</option>
              <option value="Robotics">Robotics</option>
              <option value="Opportunities">Opportunities</option>
            </select>

            <button onClick={handleCreateNote} className="u-btn u-btn-primary" style={{ fontSize: '12px' }}>
              Pin Note
            </button>
          </div>
          {noteError && <p className="inbox-error" role="alert">{noteError}</p>}
        </div>
      )}

      {/* Sticky Notes Grid */}
      {stickyNotes.length > 0 && (
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '12px',
            }}
          >
            <StickyNote size={15} color="var(--accent)" />
            <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--onyx)' }}>
              Pinned Sticky Notes ({stickyNotes.length})
            </h2>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: '14px',
            }}
          >
            {stickyNotes.map((task) => (
              <TaskCard key={task.id} task={task} showMoveControls />
            ))}
          </div>
        </div>
      )}

      {/* Untriaged Inbox List */}
      <div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '12px',
          }}
        >
          <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--onyx)' }}>
            Items in this view ({regularInbox.length})
          </h2>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Capture, filter, sort, and move items to a Kanban lane
          </span>
        </div>

        {regularInbox.length === 0 ? (
          <div
            className="u-card"
            style={{
              padding: '40px',
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: '13px',
            }}
          >
            {searchQuery || selectedCat !== 'all' || selectedPriority !== 'all' || selectedStatus !== 'inbox'
              ? <>No tasks match these filters. <button className="text-action" onClick={() => { setSearchQuery(''); setSelectedCat('all'); setSelectedPriority('all'); setSelectedStatus('inbox'); }}>Clear filters</button></>
              : <>Inbox is clear. Use <strong>Quick Capture</strong> to record your next assignment or research note.</>}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {regularInbox.map((task) => (
              <TaskCard key={task.id} task={task} showMoveControls />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
