import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Bell, CalendarClock, ShieldCheck } from 'lucide-react';
import { useAgent } from '../../context/AgentContext';
import { ApprovalRequest, Reminder } from '../../types';

const STORAGE_KEY = 'lara_iv_notifications_seen_v1';

type NotificationItem =
  | { id: string; kind: 'reminder'; title: string; detail: string; when: string; sortAt: number; reminder: Reminder }
  | { id: string; kind: 'approval'; title: string; detail: string; when: string; sortAt: number; approval: ApprovalRequest };

function readSeenIds(): string[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    return Array.isArray(parsed) && parsed.every((id) => typeof id === 'string') ? parsed : [];
  } catch {
    return [];
  }
}

export const NotificationPopover: React.FC = () => {
  const { reminders, approvals, setActiveScreen, openApprovalDetail } = useAgent();
  const [open, setOpen] = useState(false);
  const [seenIds, setSeenIds] = useState<string[]>(readSeenIds);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const items = useMemo<NotificationItem[]>(() => {
    const now = Date.now();
    const weekAhead = now + 7 * 24 * 60 * 60 * 1000;
    const reminderItems = reminders.flatMap((reminder): NotificationItem[] => {
      const date = Date.parse(reminder.status === 'snoozed' && reminder.snoozeUntil ? reminder.snoozeUntil : reminder.remindAt);
      const isMissed = reminder.status === 'missed';
      const isDueSoon = (reminder.status === 'scheduled' || reminder.status === 'snoozed')
        && Number.isFinite(date) && date <= weekAhead && date >= now - 3 * 24 * 60 * 60 * 1000;
      if (!isMissed && !isDueSoon) return [];
      return [{
        id: `reminder:${reminder.id}`,
        kind: 'reminder',
        title: reminder.title,
        detail: isMissed ? 'Missed reminder' : date < now ? 'Due now' : 'Upcoming reminder',
        when: Number.isFinite(date) ? new Date(date).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Time unavailable',
        sortAt: Number.isFinite(date) ? date : Number.MAX_SAFE_INTEGER,
        reminder,
      }];
    });
    const approvalItems = approvals.filter((approval) => approval.status === 'pending').map((approval): NotificationItem => ({
      id: `approval:${approval.id}`,
      kind: 'approval',
      title: approval.title,
      detail: 'Waiting for your review',
      when: `Expires ${new Date(approval.expiresAt).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}`,
      sortAt: Date.parse(approval.expiresAt) || Number.MAX_SAFE_INTEGER,
      approval,
    }));
    return [...approvalItems, ...reminderItems].sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'approval' ? -1 : 1;
      return a.sortAt - b.sortAt;
    });
  }, [approvals, reminders]);

  const unreadCount = items.reduce((count, item) => count + (seenIds.includes(item.id) ? 0 : 1), 0);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    popoverRef.current?.focus();
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const toggle = () => {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (!nextOpen) return;
    const nextSeen = Array.from(new Set([...seenIds, ...items.map((item) => item.id)]));
    setSeenIds(nextSeen);
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextSeen)); } catch { /* unread count remains available in memory */ }
  };

  const openItem = (item: NotificationItem) => {
    setOpen(false);
    if (item.kind === 'approval') {
      setActiveScreen('approvals');
      openApprovalDetail(item.approval);
    } else {
      setActiveScreen('reminders');
    }
  };

  return <div className="notification-popover-root" ref={rootRef}>
    <button ref={triggerRef} className="notification-trigger" type="button" onClick={toggle}
      aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ''}`} aria-haspopup="dialog" aria-expanded={open}>
      <Bell size={17} aria-hidden="true" />
      {unreadCount > 0 && <span className="notification-count" aria-hidden="true">{unreadCount > 99 ? '99+' : unreadCount}</span>}
    </button>
    {open && <section className="notification-panel" role="dialog" aria-label="Notifications" aria-modal="false" tabIndex={-1} ref={popoverRef}>
      <header className="notification-panel-header"><div><strong>Notifications</strong><span>{items.length} current items</span></div>
        <button type="button" onClick={() => setOpen(false)} aria-label="Close notifications">×</button></header>
      {items.length === 0 ? <p className="notification-empty">No upcoming reminders or approvals need attention.</p>
        : <ul className="notification-list">{items.map((item) => <li key={item.id}>
          <button type="button" className="notification-item" onClick={() => openItem(item)}>
            <span className="notification-item-icon">{item.kind === 'approval' ? <ShieldCheck size={16} /> : <CalendarClock size={16} />}</span>
            <span className="notification-item-copy"><strong>{item.title}</strong><small>{item.detail} · {item.when}</small></span>
            {!seenIds.includes(item.id) && <span className="notification-unread" aria-label="Unread" />}
          </button>
        </li>)}</ul>}
      <p className="notification-local-note">These entries reflect scheduled local reminders. This screen does not confirm delivery or send push notifications.</p>
    </section>}
  </div>;
};
