import React, { useMemo, useState } from 'react';
import { ArrowRight, Bell, Check, Circle, Plus, ShieldCheck } from 'lucide-react';
import { useAgent } from '../context/AgentContext';
import { Task } from '../types';

const dateKey = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const shortDate = (value?: string) => {
  if (!value) return 'No deadline';
  const parsed = new Date(`${value}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

export const TodayWorkspace: React.FC = () => {
  const {
    tasks, reminders, approvals, openTaskDetail,
    transitionTask, createTask, setIsQuickCaptureOpen, setActiveScreen,
  } = useAgent();
  const [capture, setCapture] = useState('');
  const [saving, setSaving] = useState(false);
  const today = dateKey(new Date());
  const openTasks = useMemo(() => tasks.filter((task) => !['done', 'archived'].includes(task.status)), [tasks]);
  const dueNow = useMemo(() => openTasks
    .filter((task) => task.dueDate && task.dueDate <= today)
    .sort((a, b) => (a.dueDate || '').localeCompare(b.dueDate || '')),
  [openTasks, today]);
  const upcoming = useMemo(() => openTasks
    .filter((task) => task.dueDate && task.dueDate > today)
    .sort((a, b) => (a.dueDate || '').localeCompare(b.dueDate || ''))
    .slice(0, 5), [openTasks, today]);
  const nextReminders = reminders
    .filter((reminder) => ['scheduled', 'snoozed', 'missed'].includes(reminder.status))
    .sort((a, b) => (a.snoozeUntil || a.remindAt).localeCompare(b.snoozeUntil || b.remindAt))
    .slice(0, 3);
  const pendingApprovals = approvals.filter((approval) => approval.status === 'pending');
  const dateLabel = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

  const submitCapture = async (event: React.FormEvent) => {
    event.preventDefault();
    const title = capture.trim();
    if (!title || saving) return;
    setSaving(true);
    try {
      await createTask({ title, category: 'Personal/Admin', room: 'operations', priority: 'medium', nextAction: 'Triage this capture.' });
      setCapture('');
    } finally {
      setSaving(false);
    }
  };

  const finish = async (event: React.MouseEvent, task: Task) => {
    event.stopPropagation();
    await transitionTask(task.id, 'done');
  };

  return (
    <div className="today-page u-workspace-scroll">
      <header className="today-intro">
        <div>
          <p className="eyebrow">YOUR WORKSPACE · {dateLabel.toUpperCase()}</p>
          <h1>Good work starts here.</h1>
          <p className="today-summary">
            {dueNow.length
              ? `${dueNow.length} ${dueNow.length === 1 ? 'item needs' : 'items need'} attention today.`
              : 'Nothing is overdue. Choose the next useful thing, or capture it while it is fresh.'}
          </p>
        </div>
        <button className="u-btn u-btn-secondary today-all-tasks" onClick={() => setActiveScreen('inbox')}>
          Open inbox <ArrowRight size={15} />
        </button>
      </header>

      <form className="today-capture" onSubmit={submitCapture}>
        <div className="capture-mark"><Plus size={18} /></div>
        <input aria-label="Quick capture" value={capture} onChange={(event) => setCapture(event.target.value)} placeholder="Capture a task or thought…" maxLength={240} />
        <button type="submit" className="u-btn u-btn-primary" disabled={!capture.trim() || saving}>{saving ? 'Adding…' : 'Add to inbox'}</button>
        <button type="button" className="u-btn u-btn-ghost capture-details" onClick={() => setIsQuickCaptureOpen(true)}>Details</button>
      </form>

      {pendingApprovals.length > 0 && <section className="today-approval-note" aria-label="Pending approvals">
        <ShieldCheck size={17} />
        <span><strong>{pendingApprovals.length} action{pendingApprovals.length === 1 ? '' : 's'} need your review.</strong> These are simulated approvals; no external action will run.</span>
        <button className="text-action" onClick={() => setActiveScreen('approvals')}>Review queue <ArrowRight size={14} /></button>
      </section>}

      <div className="today-columns">
        <section className="today-section today-priority">
          <div className="section-heading">
            <div><p className="eyebrow">FOCUS</p><h2>Due or overdue</h2></div>
            <span className="section-count">{dueNow.length}</span>
          </div>
          {dueNow.length ? <div className="today-task-list">{dueNow.map((task) => <article className="today-task" key={task.id} onClick={() => openTaskDetail(task)}>
            <button className="task-complete" aria-label={`Complete ${task.title}`} title="Mark complete" onClick={(event) => finish(event, task)}><Circle size={18} /></button>
            <div className="today-task-copy"><button className="task-title" onClick={(event) => { event.stopPropagation(); openTaskDetail(task); }}>{task.title}</button>
              <div className="task-meta"><span>{task.category}</span>{task.course && <><span aria-hidden="true">·</span><span>{task.course}</span></>}<span className={task.dueDate! < today ? 'overdue-label' : 'due-label'}>{task.dueDate! < today ? `Overdue · ${shortDate(task.dueDate)}` : `Due today · ${task.dueTime || ''}`}</span></div>
              {task.nextAction && <p className="task-next-action">Next: {task.nextAction}</p>}
            </div>
            <button className="task-open" aria-label={`Open ${task.title}`} onClick={(event) => { event.stopPropagation(); openTaskDetail(task); }}><ArrowRight size={16} /></button>
          </article>)}</div> : <div className="today-empty"><Check size={17} /><span>No deadlines need attention today.</span></div>}

          <div className="section-heading upcoming-heading"><div><p className="eyebrow">ON THE HORIZON</p><h2>Coming up</h2></div><button className="text-action" onClick={() => setActiveScreen('calendar')}>Calendar <ArrowRight size={14} /></button></div>
          {upcoming.length ? <div className="upcoming-list">{upcoming.map((task) => <button className="upcoming-row" key={task.id} onClick={() => openTaskDetail(task)}><span className="upcoming-date">{shortDate(task.dueDate)}</span><span className="upcoming-title">{task.title}</span><span className="upcoming-category">{task.category}</span><ArrowRight size={14} /></button>)}</div> : <div className="today-empty compact">No future deadlines recorded. <button className="text-action" onClick={() => setActiveScreen('inbox')}>Add a task</button></div>}
        </section>

        <aside className="today-aside">
          <section className="today-section">
            <div className="section-heading"><div><p className="eyebrow">SCHEDULED LOCALLY</p><h2>Reminders</h2></div><Bell size={16} className="heading-icon" /></div>
            {nextReminders.length ? <div className="reminder-list">{nextReminders.map((reminder) => <button className="reminder-row" key={reminder.id} onClick={() => { const task = tasks.find((item) => item.id === reminder.taskId); if (task) openTaskDetail(task); else setActiveScreen('reminders'); }}>
              <span className={`reminder-dot reminder-${reminder.status}`} /><span className="reminder-copy"><strong>{reminder.title}</strong><small>{reminder.taskTitle || 'General reminder'}</small></span><time>{new Date(reminder.snoozeUntil || reminder.remindAt).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}</time>
            </button>)}</div> : <div className="today-empty compact">No scheduled reminders.</div>}
            <button className="section-footer" onClick={() => setActiveScreen('reminders')}>Manage reminders <ArrowRight size={14} /></button>
          </section>

          <p className="prototype-note"><span className="status-pip" /> Local demo data · no provider or notification service connected</p>
        </aside>
      </div>
    </div>
  );
};
