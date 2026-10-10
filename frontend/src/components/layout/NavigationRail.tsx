import React, { useEffect, useState } from 'react';
import {
  Activity, Bell, CalendarDays, CalendarRange, ChevronDown, ChevronLeft,
  ChevronRight, FolderKanban, Inbox, LayoutGrid, LockKeyhole, Menu, Plus,
  Settings, Shield, Sparkles, X,
} from 'lucide-react';
import { useAgent } from '../../context/AgentContext';
import { ActiveScreen } from '../../types';
import { INITIAL_PERSONAS, INITIAL_ROOMS } from '../../data/mockData';

type NavItem = { id: ActiveScreen; label: string; icon: React.ReactNode };
const daily: NavItem[] = [
  { id: 'workbench', label: 'Ask LARA', icon: <Sparkles size={17} /> },
  { id: 'today', label: 'Today', icon: <CalendarRange size={17} /> },
  { id: 'inbox', label: 'Inbox', icon: <Inbox size={17} /> },
  { id: 'kanban', label: 'Kanban', icon: <LayoutGrid size={17} /> },
  { id: 'calendar', label: 'Calendar', icon: <CalendarDays size={17} /> },
  { id: 'reminders', label: 'Reminders', icon: <Bell size={17} /> },
];
const groups: { title: string; items: NavItem[] }[] = [
  { title: 'Projects & Memory', items: [
    { id: 'projects', label: 'Projects', icon: <FolderKanban size={16} /> },
    { id: 'graph', label: 'Knowledge graph', icon: <Activity size={16} /> },
  ] },
  { title: 'Operations & Governance', items: [
    { id: 'activity', label: 'Activity & runs', icon: <Activity size={16} /> },
    { id: 'approvals', label: 'Approvals', icon: <Shield size={16} /> },
    { id: 'rooms', label: 'Rooms & policy', icon: <LockKeyhole size={16} /> },
  ] },
  { title: 'System & Settings', items: [
    { id: 'settings', label: 'Settings', icon: <Settings size={16} /> },
  ] },
];

export const NavigationRail: React.FC = () => {
  const { activeScreen, setActiveScreen, activeRoom, setActiveRoom, activePersona,
    setActivePersona, isLeftRailCollapsed, setIsLeftRailCollapsed, tasks,
    setIsQuickCaptureOpen } = useAgent();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [roomMenu, setRoomMenu] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => {
    const closeTransient = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setRoomMenu(false); setMobileOpen(false); }
    };
    window.addEventListener('keydown', closeTransient);
    return () => window.removeEventListener('keydown', closeTransient);
  }, []);
  const currentRoom = INITIAL_ROOMS.find((room) => room.id === activeRoom);
  const inboxCount = tasks.filter((task) => task.status === 'inbox').length;
  const go = (id: ActiveScreen) => { setActiveScreen(id); setMobileOpen(false); };
  const navigateButton = (item: NavItem, compact = false) => {
    const selected = activeScreen === item.id;
    const label = item.label;
    return <button key={`${item.id}-${item.label}`} className={`nav-link${selected ? ' active' : ''}${item.id === 'workbench' ? ' ask-link' : ''}`}
      onClick={() => go(item.id)} title={compact ? label : undefined} aria-current={selected ? 'page' : undefined}>
      <span className="nav-icon">{item.icon}</span><span className="nav-label">{label}</span>
      {item.id === 'inbox' && inboxCount > 0 && <span className="nav-count">{inboxCount}</span>}
    </button>;
  };
  return <>
    <button className="mobile-nav-trigger" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={19} /></button>
    {mobileOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <nav className={`u-sidebar${isLeftRailCollapsed ? ' collapsed' : ''}${mobileOpen ? ' mobile-open' : ''}`} aria-label="Primary navigation">
      <div className="sidebar-brand">
        <button className="brand-lockup" onClick={() => go('workbench')} aria-label="LARA IV home"><span className="brand-mark">L</span>
          {!isLeftRailCollapsed && <span><strong>LARA IV</strong><small>Personal workspace</small></span>}
        </button>
        <button className="rail-collapse" onClick={() => mobileOpen ? setMobileOpen(false) : setIsLeftRailCollapsed((value) => !value)} aria-label={mobileOpen ? 'Close navigation' : isLeftRailCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={mobileOpen ? 'Close navigation' : isLeftRailCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          {mobileOpen ? <X size={17} /> : isLeftRailCollapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}
        </button>
      </div>
      <div className="nav-scroll">
        <div className="nav-primary">{daily.map((item) => navigateButton(item, isLeftRailCollapsed))}</div>
        <div className="nav-groups">{groups.map((group) => <section className="nav-group" key={group.title}>
          {!isLeftRailCollapsed && <button className="nav-group-toggle" title={group.title} aria-expanded={!!expanded[group.title]} onClick={() => setExpanded((value) => ({ ...value, [group.title]: !value[group.title] }))}>
            <span>{group.title}</span><ChevronDown size={14} className={expanded[group.title] ? 'rotated' : ''} />
          </button>}
          {(expanded[group.title] || isLeftRailCollapsed) && <div className="nav-group-items">{group.items.map((item) => navigateButton(item, isLeftRailCollapsed))}</div>}
        </section>)}</div>
      </div>
      <div className="sidebar-context">
        <button className="context-selector" onClick={() => setRoomMenu((value) => !value)} aria-expanded={roomMenu} title={isLeftRailCollapsed ? `Current room: ${currentRoom?.name}` : undefined}>
          <LockKeyhole size={15} /><span className="context-copy"><strong>{currentRoom?.name || 'Operations'}</strong><small>{currentRoom?.sensitivity.replace('_', ' ')}</small></span><ChevronDown size={14} />
        </button>
        {roomMenu && <div className="room-popover" role="group" aria-label="Choose knowledge room">{INITIAL_ROOMS.map((room) => <button key={room.id} className={room.id === activeRoom ? 'selected' : ''} onClick={() => { setActiveRoom(room.id); setRoomMenu(false); }}>
          <span><strong>{room.name}</strong><small>{room.description}</small></span><span className="room-lock"><LockKeyhole size={12} />{room.sensitivity.replace('_', ' ')}</span>
        </button>)}<p>Room selection sets context only. Persona and room choices do not bypass authorization.</p></div>}
        <label className="persona-select"><span className="context-copy"><strong>Persona</strong><small>Context only</small></span><select value={activePersona} onChange={(event) => setActivePersona(event.target.value as typeof activePersona)} aria-label="Choose persona">{INITIAL_PERSONAS.map((persona) => <option key={persona.id} value={persona.id}>{persona.name}</option>)}</select></label>
        <button className="capture-shortcut" onClick={() => setIsQuickCaptureOpen(true)} title="Quick capture a task"><Plus size={15} /><span>Quick capture</span></button>
      </div>
    </nav>
  </>;
};
