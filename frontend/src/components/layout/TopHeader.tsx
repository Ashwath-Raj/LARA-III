import React from 'react';
import {
  Shield,
  User,
  Plus,
  Radio,
  Search,
  RotateCcw,
} from 'lucide-react';

import { useAgent } from '../../context/AgentContext';
import { RoomBadge } from '../common/Badge';
import { INITIAL_PERSONAS } from '../../data/mockData';

export const TopHeader: React.FC = () => {
  const {
    activeScreen,
    activeRoom,
    activePersona,
    canUndo,
    undo,
    setIsQuickCaptureOpen,
    setCommandPaletteOpen,
  } = useAgent();

  const titles: Record<string, { title: string; breadcrumb: string }> = {
    today: { title: 'Today', breadcrumb: 'Daily work' },
    inbox: { title: 'Task Inbox', breadcrumb: 'Capture / Raw Items' },
    kanban: { title: 'Task Board', breadcrumb: 'Workflow / 8 Lanes' },
    calendar: { title: 'Calendar & Deadlines', breadcrumb: 'Planning / Schedule' },
    projects: { title: 'Projects Workspace', breadcrumb: 'Context / Milestones' },
    graph: { title: 'Knowledge Graph', breadcrumb: 'Context / Semantic Network' },
    workbench: { title: 'Ask LARA', breadcrumb: 'Conversation / Local simulation' },
    activity: { title: 'Runs & Reports', breadcrumb: 'Operations / Telemetry' },
    approvals: { title: 'Approval Queue', breadcrumb: 'Governance / High-Risk Gates' },
    reminders: { title: 'Reminder Schedule', breadcrumb: 'Planning / Alerts' },
    rooms: { title: 'Rooms & Policy', breadcrumb: 'Security / Compartmentalization' },
    settings: { title: 'System Preferences', breadcrumb: 'Configuration / Local Engine' },
  };

  const currentInfo = titles[activeScreen] || { title: 'LARA IV', breadcrumb: 'Workspace' };
  const currentPersona = INITIAL_PERSONAS.find((p) => p.id === activePersona);

  return (
    <header
      style={{
        height: '52px',
        padding: '0 20px',
        backgroundColor: 'var(--surface-primary)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        flexShrink: 0,
        zIndex: 10,
      }}
    >
      {/* Breadcrumb and Screen Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
        <div>
          <div
            style={{
              fontSize: '10.5px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.4px',
              lineHeight: 1,
            }}
          >
            {currentInfo.breadcrumb}
          </div>
          <h1
            style={{
              fontSize: '15px',
              fontWeight: 700,
              color: 'var(--onyx)',
              lineHeight: 1.3,
              marginTop: '1px',
            }}
          >
            {currentInfo.title}
          </h1>
        </div>

        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '10px',
            color: 'var(--status-success)',
            backgroundColor: 'rgba(29, 115, 55, 0.08)',
            padding: '2px 6px',
            borderRadius: '4px',
            fontWeight: 600,
            fontFamily: 'var(--font-mono)',
          }}
        >
          <Radio size={10} />
          BROWSER DEMO
        </span>
      </div>

      {/* Global Search / Command Bar Trigger */}
      <div style={{ flex: 1, maxWidth: '380px' }}>
        <button
          onClick={() => setCommandPaletteOpen(true)}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 12px',
            backgroundColor: 'var(--surface-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '6px',
            fontSize: '12px',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            transition: 'border-color 0.15s ease',
          }}
          title="Open Command Palette (Ctrl+K)"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Search size={14} color="var(--grey-olive)" />
            <span>Search tasks, rooms, commands...</span>
          </div>
          <kbd
            style={{
              padding: '1px 5px',
              borderRadius: '3px',
              backgroundColor: 'var(--surface-primary)',
              border: '1px solid var(--border-subtle)',
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              color: 'var(--text-secondary)',
            }}
          >
            Ctrl+K
          </kbd>
        </button>
      </div>

      {/* Active Context Badges & Quick Action Buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {/* Undo Action Button */}
        {canUndo && (
          <button
            onClick={() => undo()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '5px 10px',
              borderRadius: '6px',
              backgroundColor: 'var(--status-warning-bg)',
              color: 'var(--status-warning)',
              border: '1px solid var(--status-warning)',
              fontSize: '11.5px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
            title="Undo last task operation"
          >
            <RotateCcw size={13} />
            <span>Undo</span>
          </button>
        )}

        {/* Room Context Indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: 'var(--surface-subtle)',
            padding: '4px 8px',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <Shield size={13} color="var(--grey-olive)" />
          <RoomBadge room={activeRoom} size="small" />
        </div>

        {/* Persona Context Indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: 'var(--surface-subtle)',
            padding: '4px 8px',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle)',
            fontSize: '11.5px',
            color: 'var(--text-secondary)',
          }}
        >
          <User size={13} color="var(--cerulean)" />
          <span style={{ fontWeight: 500 }}>{currentPersona?.name || 'Task Manager'}</span>
        </div>

        {/* Quick Capture Button */}
        <button
          onClick={() => setIsQuickCaptureOpen(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            backgroundColor: 'var(--cerulean)',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: 'var(--shadow-sm)',
          }}
          title="Quick Capture Task"
        >
          <Plus size={14} />
          <span>New Task</span>
        </button>
      </div>
    </header>
  );
};
