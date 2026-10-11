import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  Calendar,
  LayoutGrid,
  Share2,
  TerminalSquare,
  Shield,
  Activity,
  Settings,
  Plus,
  ArrowRight,
  FolderKanban,
  CheckCircle,
} from 'lucide-react';

import { useAgent } from '../../context/AgentContext';
import { KnowledgeRoom } from '../../types';
import { INITIAL_ROOMS } from '../../data/mockData';

export const CommandPalette: React.FC = () => {
  const {
    commandPaletteOpen,
    setCommandPaletteOpen,
    setActiveScreen,
    setActiveRoom,
    tasks,
    setIsQuickCaptureOpen,
    openTaskDetail,
  } = useAgent();

  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (commandPaletteOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [commandPaletteOpen]);

  if (!commandPaletteOpen) return null;

  interface CommandItem {
    id: string;
    title: string;
    subtitle: string;
    icon: React.ReactNode;
    action: () => void;
    category: 'Screens' | 'Rooms' | 'Tasks' | 'Actions';
  }

  const allItems: CommandItem[] = [
    // Quick Actions
    {
      id: 'action-quick-capture',
      title: 'Quick Capture New Task',
      subtitle: 'Create a saved task in the local SQLite database',
      icon: <Plus size={16} color="var(--cerulean)" />,
      category: 'Actions',
      action: () => {
        setCommandPaletteOpen(false);
        setIsQuickCaptureOpen(true);
      },
    },
    // Screen Navigation
    {
      id: 'nav-today',
      title: 'Go to Today Workspace',
      subtitle: 'View immediate deadlines, workload timeline, and actions',
      icon: <Calendar size={16} />,
      category: 'Screens',
      action: () => {
        setActiveScreen('today');
        setCommandPaletteOpen(false);
      },
    },
    {
      id: 'nav-kanban',
      title: 'Go to Kanban Board',
      subtitle: '8-lane task status board with drag & drop reordering',
      icon: <LayoutGrid size={16} />,
      category: 'Screens',
      action: () => {
        setActiveScreen('kanban');
        setCommandPaletteOpen(false);
      },
    },
    {
      id: 'nav-graph',
      title: 'Go to Knowledge Graph',
      subtitle: 'Interactive room node network and provenance bridges',
      icon: <Share2 size={16} />,
      category: 'Screens',
      action: () => {
        setActiveScreen('graph');
        setCommandPaletteOpen(false);
      },
    },
    {
      id: 'nav-workbench',
      title: 'Go to Agent Workbench',
      subtitle: 'Local model chat; tools and memory search are unavailable',
      icon: <TerminalSquare size={16} />,
      category: 'Screens',
      action: () => {
        setActiveScreen('workbench');
        setCommandPaletteOpen(false);
      },
    },
    {
      id: 'nav-projects',
      title: 'Go to Projects',
      subtitle: 'Milestones, dependencies, and linked deliverables',
      icon: <FolderKanban size={16} />,
      category: 'Screens',
      action: () => {
        setActiveScreen('projects');
        setCommandPaletteOpen(false);
      },
    },
    {
      id: 'nav-activity',
      title: 'Go to Runs & Reports',
      subtitle: 'Execution telemetry, step logs, and approval queue',
      icon: <Activity size={16} />,
      category: 'Screens',
      action: () => {
        setActiveScreen('activity');
        setCommandPaletteOpen(false);
      },
    },
    {
      id: 'nav-settings',
      title: 'Go to System Preferences',
      subtitle: 'Configure local model routing, autonomy gates, and storage',
      icon: <Settings size={16} />,
      category: 'Screens',
      action: () => {
        setActiveScreen('settings');
        setCommandPaletteOpen(false);
      },
    },
    // Rooms
    ...INITIAL_ROOMS.map((r) => ({
      id: `room-${r.id}`,
      title: `Switch to ${r.name} Room`,
      subtitle: `Sensitivity: ${r.sensitivity} | ${r.description}`,
      icon: <Shield size={16} color="var(--cerulean)" />,
      category: 'Rooms' as const,
      action: () => {
        setActiveRoom(r.id as KnowledgeRoom);
        setCommandPaletteOpen(false);
      },
    })),
    // Tasks
    ...tasks.map((t) => ({
      id: `task-${t.id}`,
      title: t.title,
      subtitle: `Status: ${t.status} | Priority: ${t.priority} | Due: ${t.dueDate || 'No date'}`,
      icon: <CheckCircle size={16} color="var(--grey-olive)" />,
      category: 'Tasks' as const,
      action: () => {
        openTaskDetail(t);
        setCommandPaletteOpen(false);
      },
    })),
  ];

  const filteredItems = allItems.filter(
    (item) =>
      item.title.toLowerCase().includes(query.toLowerCase()) ||
      item.subtitle.toLowerCase().includes(query.toLowerCase()) ||
      item.category.toLowerCase().includes(query.toLowerCase())
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % (filteredItems.length || 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + (filteredItems.length || 1)) % (filteredItems.length || 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredItems[selectedIndex]) {
        filteredItems[selectedIndex].action();
      }
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(18, 22, 25, 0.65)',
        backdropFilter: 'blur(4px)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '10vh',
      }}
      onClick={() => setCommandPaletteOpen(false)}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '620px',
          backgroundColor: 'var(--surface-primary)',
          borderRadius: '12px',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border-subtle)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '75vh',
        }}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search input */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '14px 18px',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <Search size={18} color="var(--grey-olive)" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Type a command, search tasks, or switch rooms..."
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              fontSize: '15px',
              backgroundColor: 'transparent',
              color: 'var(--text-primary)',
            }}
          />
          <kbd
            style={{
              padding: '2px 6px',
              borderRadius: '4px',
              backgroundColor: 'var(--surface-subtle)',
              border: '1px solid var(--border-subtle)',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--text-muted)',
            }}
          >
            ESC to close
          </kbd>
        </div>

        {/* Results List */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '8px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          {filteredItems.length === 0 ? (
            <div
              style={{
                padding: '32px 16px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: '13px',
              }}
            >
              No matching commands or items found for "{query}".
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => item.action()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    backgroundColor: isSelected ? 'var(--surface-warm)' : 'transparent',
                    cursor: 'pointer',
                    transition: 'background 0.1s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '28px',
                        height: '28px',
                        borderRadius: '6px',
                        backgroundColor: isSelected ? '#ffffff' : 'var(--surface-subtle)',
                        border: '1px solid var(--border-subtle)',
                        flexShrink: 0,
                      }}
                    >
                      {item.icon}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: isSelected ? 600 : 500,
                          color: 'var(--onyx)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {item.title}
                      </div>
                      <div
                        style={{
                          fontSize: '11px',
                          color: 'var(--text-muted)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {item.subtitle}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <span
                      style={{
                        fontSize: '10px',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor: 'var(--surface-subtle)',
                        color: 'var(--text-secondary)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {item.category}
                    </span>
                    {isSelected && <ArrowRight size={14} color="var(--cerulean)" />}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '8px 16px',
            backgroundColor: 'var(--surface-subtle)',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '11px',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          <span>Use ↑ ↓ to navigate, Enter to select</span>
          <span>LARA IV Workspace</span>
        </div>
      </div>
    </div>
  );
};
