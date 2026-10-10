import React, { useMemo, useState } from 'react';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAgent } from '../context/AgentContext';
import { KnowledgeRoom } from '../types';

const roomOptions: Array<{ id: KnowledgeRoom | 'all'; label: string }> = [
  { id: 'all', label: 'All rooms' }, { id: 'academic', label: 'Academic' }, { id: 'projects', label: 'Projects' },
  { id: 'operations', label: 'Operations' }, { id: 'opportunities', label: 'Opportunities' },
  { id: 'public_research', label: 'Public research' }, { id: 'personal_vault', label: 'Personal vault' }, { id: 'health', label: 'Health' },
];

const keyFor = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

export const CalendarWorkspace: React.FC = () => {
  const { tasks, reminders, openTaskDetail, setActiveScreen } = useAgent();
  const [view, setView] = useState<'agenda' | 'month'>('agenda');
  const [room, setRoom] = useState<KnowledgeRoom | 'all'>('all');
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [selectedDate, setSelectedDate] = useState(keyFor(new Date()));
  const monthKey = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}`;
  const today = keyFor(new Date());
  const monthTasks = useMemo(() => tasks.filter((task) => task.dueDate?.startsWith(monthKey) && (room === 'all' || task.room === room)), [tasks, monthKey, room]);
  const monthReminders = useMemo(() => reminders.filter((reminder) => {
    const task = tasks.find((item) => item.id === reminder.taskId);
    return (room === 'all' || !reminder.taskId || task?.room === room)
      && (reminder.snoozeUntil || reminder.remindAt).startsWith(monthKey)
      && !['dismissed', 'cancelled'].includes(reminder.status);
  }), [reminders, tasks, monthKey, room]);
  const dates = Array.from(new Set([
    ...monthTasks.map((task) => task.dueDate!),
    ...monthReminders.map((reminder) => (reminder.snoozeUntil || reminder.remindAt).slice(0, 10)),
  ])).sort();
  const dayCount = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const blankDays = (new Date(month.getFullYear(), month.getMonth(), 1).getDay() + 6) % 7;
  const selectedTasks = monthTasks.filter((task) => task.dueDate === selectedDate);
  const selectedReminders = monthReminders.filter((reminder) => (reminder.snoozeUntil || reminder.remindAt).slice(0, 10) === selectedDate);
  const shiftMonth = (offset: number) => setMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1));

  return <div className="calendar-workspace u-workspace-scroll">
    <div className="calendar-toolbar">
      <div className="calendar-month-controls">
        <button aria-label="Previous month" onClick={() => shiftMonth(-1)}><ChevronLeft size={17} /></button>
        <h2>{month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}</h2>
        <button aria-label="Next month" onClick={() => shiftMonth(1)}><ChevronRight size={17} /></button>
        <button className="calendar-today-button" onClick={() => { const now = new Date(); setMonth(new Date(now.getFullYear(), now.getMonth(), 1)); setSelectedDate(keyFor(now)); }}>Today</button>
      </div>
      <div className="calendar-filters">
        <label htmlFor="calendar-room">Room</label>
        <select id="calendar-room" value={room} onChange={(event) => setRoom(event.target.value as KnowledgeRoom | 'all')}>
          {roomOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
        </select>
        <div className="calendar-view-toggle" aria-label="Calendar view">
          {(['agenda', 'month'] as const).map((option) => <button key={option} aria-pressed={view === option} className={view === option ? 'selected' : ''} onClick={() => setView(option)}>{option === 'agenda' ? 'Agenda' : 'Month'}</button>)}
        </div>
      </div>
    </div>
    <p className="calendar-prototype-hint"><CalendarIcon size={14} /> Dates and reminders shown here are local prototype records. Notification delivery is not connected.</p>

    {view === 'agenda' ? <div className="calendar-agenda">
      {dates.length ? dates.map((date) => {
        const dayTasks = monthTasks.filter((task) => task.dueDate === date);
        const dayReminders = monthReminders.filter((reminder) => (reminder.snoozeUntil || reminder.remindAt).slice(0, 10) === date);
        return <section className={`agenda-day ${date === today ? 'is-today' : ''}`} key={date}>
          <header><div><span className="agenda-date">{new Date(`${date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span>{date === today && <span className="agenda-today-label">Today</span>}</div><span className="agenda-count">{dayTasks.length + dayReminders.length} items</span></header>
          {dayTasks.map((task) => <button className="agenda-entry" key={task.id} onClick={() => openTaskDetail(task)}><span className={`priority-mark priority-${task.priority}`} /><span className="agenda-entry-title">{task.title}</span><span className="agenda-entry-meta">{task.course || task.category} · {task.status.replace(/_/g, ' ')}</span></button>)}
          {dayReminders.map((reminder) => <button className="agenda-entry agenda-reminder" key={reminder.id} onClick={() => setActiveScreen('reminders')}><span className="priority-mark reminder-mark" /><span className="agenda-entry-title">{reminder.title}</span><span className="agenda-entry-meta">Simulated reminder · {reminder.status}</span></button>)}
        </section>;
      }) : <div className="calendar-empty"><CalendarIcon size={20} /><h3>No dates in this month</h3><p>Tasks with due dates and reminders will appear here.</p></div>}
    </div> : <>
      <div className="calendar-month-grid">
        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => <div className="calendar-weekday" key={day}>{day}</div>)}
        {Array.from({ length: blankDays }, (_, index) => <div className="calendar-blank" key={`blank-${index}`} />)}
        {Array.from({ length: dayCount }, (_, index) => {
          const date = `${monthKey}-${String(index + 1).padStart(2, '0')}`;
          const count = monthTasks.filter((task) => task.dueDate === date).length + monthReminders.filter((reminder) => (reminder.snoozeUntil || reminder.remindAt).slice(0, 10) === date).length;
          return <button key={date} className={`calendar-day ${date === today ? 'is-today' : ''} ${date === selectedDate ? 'is-selected' : ''}`} aria-pressed={date === selectedDate} onClick={() => setSelectedDate(date)}>
            <span>{index + 1}</span>{count > 0 && <small>{count} {count === 1 ? 'item' : 'items'}</small>}
          </button>;
        })}
      </div>
      <section className="calendar-selected-day"><header><div><p className="eyebrow">SELECTED DATE</p><h3>{new Date(`${selectedDate}T12:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</h3></div><span className="section-count">{selectedTasks.length + selectedReminders.length}</span></header>
        {selectedTasks.map((task) => <button className="calendar-selected-entry" key={task.id} onClick={() => openTaskDetail(task)}><span>{task.title}</span><small>{task.status.replace(/_/g, ' ')} · {task.priority} priority</small></button>)}
        {selectedReminders.map((reminder) => <button className="calendar-selected-entry" key={reminder.id} onClick={() => setActiveScreen('reminders')}><span>{reminder.title}</span><small>Simulated reminder · {reminder.status}</small></button>)}
        {!selectedTasks.length && !selectedReminders.length && <p className="calendar-no-items">No tasks or reminders on this date.</p>}
      </section>
    </>}
  </div>;
};
