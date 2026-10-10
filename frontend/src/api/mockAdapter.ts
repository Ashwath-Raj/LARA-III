/**
 * LARA IV, in-memory + local storage mock API adapter
 * Strictly offline local simulation for testing the interactive desktop workspace.
 * Explicitly marks all operations as local simulations and persists state across page reloads.
 */

import {
  Task,
  TaskStatus,
  Reminder,
  ApprovalRequest,
  AgentJob,
  AuditEvent,
  SettingsState,
  Project,
  ConversationMessage,
} from '../types';

import {
  TaskCaptureCandidate,
  TaskFilterParams,
  CreateTaskPayload,
  UpdateTaskPayload,
  ApprovalDecisionPayload,
  CreateJobPayload,
} from './types';

import { UbuntuAgentApiAdapter, GraphData } from './adapter';
import {
  INITIAL_TASKS,
  INITIAL_REMINDERS,
  INITIAL_APPROVALS,
  INITIAL_JOBS,
  INITIAL_AUDIT_EVENTS,
  INITIAL_SETTINGS,
  INITIAL_PROJECTS,
  INITIAL_GRAPH_NODES,
  INITIAL_GRAPH_EDGES,
  INITIAL_CONVERSATION,
} from '../data/mockData';
import { ConversationSummary } from '../types';

const STORAGE_KEYS = {
  TASKS: 'ubuntu_agent_tasks_v2',
  REMINDERS: 'ubuntu_agent_reminders_v2',
  APPROVALS: 'ubuntu_agent_approvals_v2',
  JOBS: 'ubuntu_agent_jobs_v2',
  AUDIT: 'ubuntu_agent_audit_v2',
  SETTINGS: 'ubuntu_agent_settings_v2',
  PROJECTS: 'ubuntu_agent_projects_v2',
  MESSAGES: 'ubuntu_agent_messages_v2',
  ACTIVE_CONVERSATION: 'lara_iv_active_conversation_v1',
};

const VALID_TASK_STATUSES: TaskStatus[] = ['inbox', 'next', 'in_progress', 'waiting', 'review', 'ready_to_submit', 'done', 'archived'];

function uniqueLocalId(prefix: string) {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${random}`;
}

interface UndoRecord {
  type: 'task_transition' | 'task_delete' | 'task_create' | 'task_reorder';
  description: string;
  previousTasks: Task[];
}

export class MockUbuntuAgentApi implements UbuntuAgentApiAdapter {
  private tasks: Task[];
  private reminders: Reminder[];
  private approvals: ApprovalRequest[];
  private jobs: AgentJob[];
  private auditEvents: AuditEvent[];
  private settings: SettingsState;
  private projects: Project[];
  private messages: ConversationMessage[];
  private activeConversationId: string;
  private undoStack: UndoRecord[] = [];

  constructor() {
    this.tasks = this.loadFromStorage(STORAGE_KEYS.TASKS, INITIAL_TASKS);
    this.reminders = this.loadFromStorage(STORAGE_KEYS.REMINDERS, INITIAL_REMINDERS);
    this.approvals = this.loadFromStorage(STORAGE_KEYS.APPROVALS, INITIAL_APPROVALS);
    this.jobs = this.loadFromStorage(STORAGE_KEYS.JOBS, INITIAL_JOBS);
    this.auditEvents = this.loadFromStorage(STORAGE_KEYS.AUDIT, INITIAL_AUDIT_EVENTS);
    this.settings = this.loadFromStorage(STORAGE_KEYS.SETTINGS, INITIAL_SETTINGS);
    this.projects = this.loadFromStorage(STORAGE_KEYS.PROJECTS, INITIAL_PROJECTS);
    const storedMessages = this.loadFromStorage<ConversationMessage[]>(STORAGE_KEYS.MESSAGES, INITIAL_CONVERSATION);
    this.messages = storedMessages.filter((message) => !['msg-01', 'msg-02'].includes(message.id));
    this.messages = this.messages.map((message) => ({
      ...message,
      conversationId: message.conversationId || 'conversation-legacy',
      simulated: message.simulated ?? message.sender === 'agent',
    }));
    this.activeConversationId = this.loadFromStorage(STORAGE_KEYS.ACTIVE_CONVERSATION,
      this.messages.at(-1)?.conversationId || uniqueLocalId('conversation'));
    if (!this.messages.some((message) => message.conversationId === this.activeConversationId)
      && !this.activeConversationId.startsWith('conversation-')) {
      this.activeConversationId = this.messages.at(-1)?.conversationId || uniqueLocalId('conversation');
    }
    this.saveToStorage(STORAGE_KEYS.ACTIVE_CONVERSATION, this.activeConversationId);
    if (this.messages.length !== storedMessages.length) {
      this.saveToStorage(STORAGE_KEYS.MESSAGES, this.messages);
    }
  }

  resetDemoData(): void {
    this.tasks = [...INITIAL_TASKS];
    this.reminders = [...INITIAL_REMINDERS];
    this.approvals = [...INITIAL_APPROVALS];
    this.jobs = [...INITIAL_JOBS];
    this.auditEvents = [...INITIAL_AUDIT_EVENTS];
    this.settings = { ...INITIAL_SETTINGS };
    this.projects = [...INITIAL_PROJECTS];
    this.messages = [...INITIAL_CONVERSATION];
    this.activeConversationId = uniqueLocalId('conversation');
    this.undoStack = [];
    this.saveToStorage(STORAGE_KEYS.TASKS, this.tasks);
    this.saveToStorage(STORAGE_KEYS.REMINDERS, this.reminders);
    this.saveToStorage(STORAGE_KEYS.APPROVALS, this.approvals);
    this.saveToStorage(STORAGE_KEYS.JOBS, this.jobs);
    this.saveToStorage(STORAGE_KEYS.AUDIT, this.auditEvents);
    this.saveToStorage(STORAGE_KEYS.SETTINGS, this.settings);
    this.saveToStorage(STORAGE_KEYS.PROJECTS, this.projects);
    this.saveToStorage(STORAGE_KEYS.MESSAGES, this.messages);
    this.saveToStorage(STORAGE_KEYS.ACTIVE_CONVERSATION, this.activeConversationId);
  }

  private loadFromStorage<T>(key: string, fallback: T): T {
    try {
      const data = localStorage.getItem(key);
      if (data) return JSON.parse(data);
    } catch {
      // ignore
    }
    return fallback;
  }

  private saveToStorage(key: string, data: unknown): boolean {
    try {
      localStorage.setItem(key, JSON.stringify(data));
      return true;
    } catch {
      return false;
    }
  }

  canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  async undo(): Promise<boolean> {
    const record = this.undoStack.pop();
    if (!record) return false;

    this.tasks = [...record.previousTasks];
    this.saveToStorage(STORAGE_KEYS.TASKS, this.tasks);

    this.recordAuditEvent({
      eventType: 'undo.executed',
      aggregateType: 'task',
      aggregateId: 'system',
      actor: 'user',
      safePayload: { description: record.description },
    });
    return true;
  }

  // Task Operations
  async captureTask(inputText: string): Promise<TaskCaptureCandidate> {
    const text = inputText.trim();
    const lower = text.toLowerCase();

    let suggestedTitle = text;
    let suggestedCategory = 'Personal/Admin';
    let suggestedCourse: string | undefined;
    let suggestedFile: string | undefined;
    let suggestedDueDate: string | undefined;
    const missingFields: string[] = [];
    const clarificationQuestions: string[] = [];

    if (lower.includes('algorithm') || lower.includes('cs401')) {
      suggestedCategory = 'Academics';
      suggestedCourse = 'CS401: Advanced Algorithms';
    } else if (lower.includes('operating system') || lower.includes('os') || lower.includes('cs420')) {
      suggestedCategory = 'Academics';
      suggestedCourse = 'CS420: Operating Systems';
    } else if (lower.includes('quantum') || lower.includes('qiskit')) {
      suggestedCategory = 'Quantum';
    } else if (lower.includes('ros') || lower.includes('robot')) {
      suggestedCategory = 'Robotics';
    } else if (lower.includes('hack') || lower.includes('competition')) {
      suggestedCategory = 'Hackathons';
    } else if (lower.includes('fellowship') || lower.includes('internship') || lower.includes('scholarship')) {
      suggestedCategory = 'Opportunities';
    } else if (lower.includes('model') || lower.includes('train') || lower.includes('paper') || lower.includes('arxiv')) {
      suggestedCategory = 'AI/ML';
    } else if (lower.includes('code') || lower.includes('frontend') || lower.includes('backend') || lower.includes('git')) {
      suggestedCategory = 'Projects';
    }

    const fileMatch = text.match(/([a-zA-Z0-9_\-.]+\.(pdf|c|py|ipynb|tex|md|json))/i);
    if (fileMatch) {
      suggestedFile = fileMatch[1];
    }

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const isoDate = text.match(/\b(\d{4})-(\d{2})-(\d{2})\b/);
    if (/\btoday\b/i.test(text)) {
      suggestedDueDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    } else if (/\btomorrow\b/i.test(text)) {
      const tomorrow = new Date(today);
      tomorrow.setDate(tomorrow.getDate() + 1);
      suggestedDueDate = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;
    } else if (isoDate) {
      const [, year, month, day] = isoDate;
      const parsed = new Date(Number(year), Number(month) - 1, Number(day));
      if (parsed.getFullYear() === Number(year) && parsed.getMonth() === Number(month) - 1 && parsed.getDate() === Number(day)) {
        suggestedDueDate = `${year}-${month}-${day}`;
      } else {
        clarificationQuestions.push('That date is not valid. Please enter a real date as YYYY-MM-DD.');
      }
    } else {
      const monthNames: Record<string, number> = { jan: 0, january: 0, feb: 1, february: 1, mar: 2, march: 2, apr: 3, april: 3, may: 4, jun: 5, june: 5, jul: 6, july: 6, aug: 7, august: 7, sep: 8, sept: 8, september: 8, oct: 9, october: 9, nov: 10, november: 10, dec: 11, december: 11 };
      const namedDate = text.match(/\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+(\d{4}))?\b/i)
        || text.match(/\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:,?\s+(\d{4}))?\b/i);
      if (namedDate) {
        const monthFirst = Number.isNaN(Number(namedDate[1]));
        const day = Number(monthFirst ? namedDate[2] : namedDate[1]);
        const month = monthNames[(monthFirst ? namedDate[1] : namedDate[2]).toLowerCase()] ?? -1;
        const year = Number((monthFirst ? namedDate[3] : namedDate[3]) || now.getFullYear());
        const parsed = new Date(year, month, day);
        if (parsed.getFullYear() === year && parsed.getMonth() === month && parsed.getDate() === day) {
          const dateOnly = new Date(year, month, day);
          if (!namedDate[3] && dateOnly < today) {
            clarificationQuestions.push('That day has already passed this year. Which year should I use?');
          } else {
            suggestedDueDate = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          }
        } else {
          clarificationQuestions.push('That date is not valid. Please confirm the day and month.');
        }
      }
    }

    if (!suggestedDueDate) {
      missingFields.push('due_date');
      if (clarificationQuestions.length === 0) clarificationQuestions.push('What is the exact target due date? (e.g. 2026-11-07)');
    }

    return {
      rawText: text,
      suggestedTitle,
      suggestedCategory,
      suggestedCourse,
      suggestedFile,
      suggestedDueDate,
      suggestedReminderCadence: '3 days before, 1 day before, and due-day morning',
      missingFields,
      clarificationQuestions,
      requiresConfirmation: missingFields.length > 0,
    };
  }

  async createTask(payload: CreateTaskPayload): Promise<Task> {
    const previous = [...this.tasks];
    const newTask: Task = {
      id: `task-${Date.now().toString(36)}`,
      title: payload.title,
      description: payload.description,
      status: 'inbox',
      priority: payload.priority || 'medium',
      category: payload.category || 'Personal/Admin',
      room: payload.room || 'operations',
      dueDate: payload.dueDate,
      dueTime: payload.dueTime,
      course: payload.course,
      project: payload.project,
      nextAction: payload.nextAction || 'Clarify scope or triage to Kanban lane.',
      attachments: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      isSticky: payload.isSticky ?? false,
      stickyColor: payload.stickyColor || 'beige',
      remindersCount: 0,
      tags: [],
    };

    this.undoStack.push({
      type: 'task_create',
      description: `Created task "${newTask.title}"`,
      previousTasks: previous,
    });

    this.tasks = [newTask, ...this.tasks];
    this.saveToStorage(STORAGE_KEYS.TASKS, this.tasks);

    this.recordAuditEvent({
      eventType: 'task.created',
      aggregateType: 'task',
      aggregateId: newTask.id,
      actor: 'user',
      safePayload: {
        title: newTask.title,
        category: newTask.category,
        room: newTask.room,
      },
    });

    return newTask;
  }

  async listTasks(filters?: TaskFilterParams): Promise<Task[]> {
    let result = [...this.tasks];
    if (filters?.status) {
      result = result.filter((t) => t.status === filters.status);
    }
    if (filters?.category) {
      result = result.filter((t) => t.category === filters.category);
    }
    if (filters?.room) {
      result = result.filter((t) => t.room === filters.room);
    }
    if (filters?.searchQuery) {
      const q = filters.searchQuery.toLowerCase();
      result = result.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.description?.toLowerCase().includes(q) ||
          t.course?.toLowerCase().includes(q) ||
          t.tags.some((tag) => tag.toLowerCase().includes(q))
      );
    }
    return result;
  }

  async getTask(taskId: string): Promise<Task | null> {
    return this.tasks.find((t) => t.id === taskId) || null;
  }

  async updateTask(taskId: string, patch: UpdateTaskPayload): Promise<Task> {
    const index = this.tasks.findIndex((t) => t.id === taskId);
    if (index === -1) {
      throw new Error(`Task with id ${taskId} not found`);
    }

    const updated: Task = {
      ...this.tasks[index],
      ...patch,
      updatedAt: new Date().toISOString(),
    };

    this.tasks[index] = updated;
    this.saveToStorage(STORAGE_KEYS.TASKS, this.tasks);

    this.recordAuditEvent({
      eventType: 'task.updated',
      aggregateType: 'task',
      aggregateId: taskId,
      actor: 'user',
      safePayload: { patchKeys: Object.keys(patch) },
    });

    return updated;
  }

  async transitionTask(taskId: string, targetStatus: TaskStatus): Promise<Task> {
    if (!VALID_TASK_STATUSES.includes(targetStatus)) {
      throw new Error(`Invalid task status: ${String(targetStatus)}`);
    }
    const index = this.tasks.findIndex((t) => t.id === taskId);
    if (index === -1) {
      throw new Error(`Task ${taskId} not found`);
    }

    const previous = [...this.tasks];
    const prevStatus = this.tasks[index].status;
    if (prevStatus === targetStatus) return this.tasks[index];
    this.tasks[index] = {
      ...this.tasks[index],
      status: targetStatus,
      updatedAt: new Date().toISOString(),
    };

    this.undoStack.push({
      type: 'task_transition',
      description: `Moved "${this.tasks[index].title}" from ${prevStatus} to ${targetStatus}`,
      previousTasks: previous,
    });

    if (!this.saveToStorage(STORAGE_KEYS.TASKS, this.tasks)) {
      this.tasks = previous;
      this.undoStack.pop();
      throw new Error('Task status could not be persisted to browser storage');
    }

    this.recordAuditEvent({
      eventType: 'task.transitioned',
      aggregateType: 'task',
      aggregateId: taskId,
      actor: 'user',
      safePayload: { fromStatus: prevStatus, toStatus: targetStatus },
    });

    return this.tasks[index];
  }

  async reorderTasks(sourceIndex: number, destinationIndex: number, status: TaskStatus): Promise<Task[]> {
    if (!VALID_TASK_STATUSES.includes(status)) throw new Error(`Invalid task status: ${String(status)}`);
    const previous = [...this.tasks];
    const laneTasks = this.tasks.filter((t) => t.status === status);
    const otherTasks = this.tasks.filter((t) => t.status !== status);
    if (!Number.isInteger(sourceIndex) || !Number.isInteger(destinationIndex)
      || sourceIndex < 0 || sourceIndex >= laneTasks.length
      || destinationIndex < 0 || destinationIndex >= laneTasks.length) {
      throw new Error('Task reorder indexes are outside the selected lane');
    }
    if (sourceIndex === destinationIndex) return [...this.tasks];

    const [moved] = laneTasks.splice(sourceIndex, 1);
    if (!moved) throw new Error('Task could not be found in the selected lane');
    laneTasks.splice(destinationIndex, 0, moved);

    this.undoStack.push({
      type: 'task_reorder',
      description: `Reordered lane "${status}"`,
      previousTasks: previous,
    });

    this.tasks = [...laneTasks, ...otherTasks];
    if (!this.saveToStorage(STORAGE_KEYS.TASKS, this.tasks)) {
      this.tasks = previous;
      this.undoStack.pop();
      throw new Error('Task order could not be persisted to browser storage');
    }
    return [...this.tasks];
  }

  async deleteTask(taskId: string): Promise<boolean> {
    const previous = [...this.tasks];
    const target = this.tasks.find((t) => t.id === taskId);
    this.tasks = this.tasks.filter((t) => t.id !== taskId);

    if (target) {
      this.undoStack.push({
        type: 'task_delete',
        description: `Deleted task "${target.title}"`,
        previousTasks: previous,
      });
    }

    this.saveToStorage(STORAGE_KEYS.TASKS, this.tasks);
    return true;
  }

  // Reminder Operations
  async listReminders(): Promise<Reminder[]> {
    return [...this.reminders];
  }

  async snoozeReminder(reminderId: string, minutes = 30): Promise<Reminder> {
    const index = this.reminders.findIndex((r) => r.id === reminderId);
    if (index === -1) {
      throw new Error(`Reminder ${reminderId} not found`);
    }

    const snoozeUntil = new Date(Date.now() + minutes * 60 * 1000).toISOString();
    this.reminders[index] = {
      ...this.reminders[index],
      status: 'snoozed',
      snoozeUntil,
    };

    this.saveToStorage(STORAGE_KEYS.REMINDERS, this.reminders);

    this.recordAuditEvent({
      eventType: 'reminder.snoozed',
      aggregateType: 'reminder',
      aggregateId: reminderId,
      actor: 'user',
      safePayload: { snoozeUntil, minutes },
    });

    return this.reminders[index];
  }

  async dismissReminder(reminderId: string): Promise<Reminder> {
    const index = this.reminders.findIndex((r) => r.id === reminderId);
    if (index === -1) {
      throw new Error(`Reminder ${reminderId} not found`);
    }

    this.reminders[index] = {
      ...this.reminders[index],
      status: 'dismissed',
    };

    this.saveToStorage(STORAGE_KEYS.REMINDERS, this.reminders);

    this.recordAuditEvent({
      eventType: 'reminder.dismissed',
      aggregateType: 'reminder',
      aggregateId: reminderId,
      actor: 'user',
      safePayload: {},
    });

    return this.reminders[index];
  }

  async cancelReminder(reminderId: string): Promise<Reminder> {
    const index = this.reminders.findIndex((reminder) => reminder.id === reminderId);
    if (index === -1) throw new Error(`Reminder ${reminderId} not found`);
    this.reminders[index] = { ...this.reminders[index], status: 'cancelled' };
    this.saveToStorage(STORAGE_KEYS.REMINDERS, this.reminders);
    this.recordAuditEvent({
      eventType: 'reminder.cancelled',
      aggregateType: 'reminder',
      aggregateId: reminderId,
      actor: 'user',
      safePayload: {},
    });
    return this.reminders[index];
  }

  async createReminder(taskId: string, title: string, remindAt: string): Promise<Reminder> {
    const parentTask = this.tasks.find((t) => t.id === taskId);
    const newReminder: Reminder = {
      id: `rem-${Date.now().toString(36)}`,
      taskId,
      taskTitle: parentTask?.title || 'Standalone reminder',
      title,
      remindAt,
      status: 'scheduled',
      type: 'custom',
    };

    this.reminders = [newReminder, ...this.reminders];
    this.saveToStorage(STORAGE_KEYS.REMINDERS, this.reminders);

    if (parentTask) {
      const idx = this.tasks.findIndex((t) => t.id === taskId);
      if (idx !== -1) {
        this.tasks[idx].remindersCount += 1;
        this.saveToStorage(STORAGE_KEYS.TASKS, this.tasks);
      }
    }

    this.recordAuditEvent({
      eventType: 'reminder.scheduled',
      aggregateType: 'reminder',
      aggregateId: newReminder.id,
      actor: 'user',
      safePayload: { taskId, remindAt },
    });

    return newReminder;
  }

  // Project Operations
  async listProjects(): Promise<Project[]> {
    return [...this.projects];
  }

  async getProject(projectId: string): Promise<Project | null> {
    return this.projects.find((p) => p.id === projectId) || null;
  }

  async updateProject(projectId: string, patch: Partial<Project>): Promise<Project> {
    const index = this.projects.findIndex((p) => p.id === projectId);
    if (index === -1) throw new Error(`Project ${projectId} not found`);

    this.projects[index] = {
      ...this.projects[index],
      ...patch,
      updatedAt: new Date().toISOString(),
    };
    this.saveToStorage(STORAGE_KEYS.PROJECTS, this.projects);
    return this.projects[index];
  }

  // Knowledge Graph
  async getGraph(): Promise<GraphData> {
    return {
      nodes: INITIAL_GRAPH_NODES,
      edges: INITIAL_GRAPH_EDGES,
    };
  }

  // Conversation & Workbench
  async listMessages(conversationId = this.activeConversationId): Promise<ConversationMessage[]> {
    return this.messages.filter((message) => message.conversationId === conversationId).sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  }

  async listConversations(): Promise<ConversationSummary[]> {
    const groups = new Map<string, ConversationMessage[]>();
    this.messages.forEach((message) => groups.set(message.conversationId, [...(groups.get(message.conversationId) || []), message]));
    return [...groups.entries()].map(([id, messages]) => {
      const firstUser = messages.find((message) => message.sender === 'user');
      const latest = messages.at(-1)!;
      return {
        id,
        title: firstUser?.content.trim().slice(0, 56) || 'Conversation',
        updatedAt: latest.timestamp,
        preview: latest.content.replace(/\s+/g, ' ').slice(0, 100),
        messageCount: messages.length,
      };
    }).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }

  async createConversation(): Promise<string> {
    const previous = this.activeConversationId;
    this.activeConversationId = uniqueLocalId('conversation');
    if (!this.saveToStorage(STORAGE_KEYS.ACTIVE_CONVERSATION, this.activeConversationId)) {
      this.activeConversationId = previous;
      throw new Error('Conversation storage is unavailable.');
    }
    return this.activeConversationId;
  }

  async selectConversation(conversationId: string): Promise<void> {
    if (!this.messages.some((message) => message.conversationId === conversationId)) throw new Error('Conversation was not found.');
    const previous = this.activeConversationId;
    this.activeConversationId = conversationId;
    if (!this.saveToStorage(STORAGE_KEYS.ACTIVE_CONVERSATION, conversationId)) {
      this.activeConversationId = previous;
      throw new Error('Conversation storage is unavailable.');
    }
  }

  async sendMessage(content: string, roomId = 'operations', conversationId = this.activeConversationId): Promise<ConversationMessage> {
    if (conversationId !== this.activeConversationId) throw new Error('The active conversation changed. Select it again before sending.');
    const makeId = () => uniqueLocalId('msg');
    const userMsg: ConversationMessage = {
      id: makeId(),
      conversationId,
      sender: 'user',
      content,
      timestamp: new Date().toISOString(),
      roomId: roomId as any,
      route: 'Local only',
    };

    this.messages = [...this.messages, userMsg];

    // Static prototype copy. No inference, provider, or tool execution occurs.
    const agentMsg: ConversationMessage = {
      id: makeId(),
      conversationId,
      sender: 'agent',
      content: `This browser demo stored your prompt in the **${roomId}** conversation. No model analyzed it, no local notes were searched, and no task or external action was performed. Use the task screens to make changes to the browser-local demo data.`,
      timestamp: new Date().toISOString(),
      roomId: roomId as any,
      route: 'Local only',
      simulated: true,
    };

    this.messages = [...this.messages, agentMsg];
    if (!this.saveToStorage(STORAGE_KEYS.MESSAGES, this.messages)) {
      this.messages = this.messages.filter((message) => message.id !== userMsg.id && message.id !== agentMsg.id);
      throw new Error('Conversation storage is unavailable.');
    }
    return agentMsg;
  }

  // Approval Operations
  async listApprovals(): Promise<ApprovalRequest[]> {
    return [...this.approvals];
  }

  async decideApproval(approvalId: string, payload: ApprovalDecisionPayload): Promise<ApprovalRequest> {
    const index = this.approvals.findIndex((a) => a.id === approvalId);
    if (index === -1) {
      throw new Error(`Approval ${approvalId} not found`);
    }

    const app = this.approvals[index];
    const newStatus = payload.decision === 'approve' ? 'approved' : 'rejected';

    this.approvals[index] = {
      ...app,
      status: newStatus,
      decidedAt: new Date().toISOString(),
    };
    this.saveToStorage(STORAGE_KEYS.APPROVALS, this.approvals);

    this.recordAuditEvent({
      eventType: 'approval.decided',
      aggregateType: 'approval',
      aggregateId: approvalId,
      actor: 'user',
      safePayload: {
        decision: payload.decision,
        targetResource: app.targetResource,
        riskTier: app.riskTier,
      },
    });

    if (app.jobId) {
      const jobIdx = this.jobs.findIndex((j) => j.id === app.jobId);
      if (jobIdx !== -1) {
        if (payload.decision === 'approve') {
          this.jobs[jobIdx] = {
            ...this.jobs[jobIdx],
            status: 'verifying',
            currentStage: 'Verifying outcome in target environment',
            toolTraces: [
              ...this.jobs[jobIdx].toolTraces,
              {
                id: `trace-${Date.now()}`,
                tool: 'action.executor',
                status: 'verified',
                summary: `Simulated approved execution of: ${app.plainLanguageAction}`,
                timestamp: new Date().toISOString(),
              },
            ],
          };
        } else {
          this.jobs[jobIdx] = {
            ...this.jobs[jobIdx],
            status: 'blocked',
            currentStage: 'Action rejected by user approval gate',
          };
        }
        this.saveToStorage(STORAGE_KEYS.JOBS, this.jobs);
      }
    }

    return this.approvals[index];
  }

  // Agent / Job Operations
  async listJobs(): Promise<AgentJob[]> {
    return [...this.jobs];
  }

  async createJob(payload: CreateJobPayload): Promise<AgentJob> {
    const newJob: AgentJob = {
      id: `job-${Date.now().toString(36)}`,
      goal: payload.goal,
      status: 'planning',
      currentStage: 'Planning bounded steps & checking policy rules',
      scope: 'Local research & workspace analysis',
      room: payload.room,
      modelUsed: 'Gemma 2B (Local via Ollama)',
      route: 'Local (Ollama · Gemma 2B)',
      startedAt: new Date().toISOString(),
      budgetTokensUsed: 120,
      budgetMaxTokens: payload.budgetTokens || 6000,
      toolTraces: [
        {
          id: `trace-init-${Date.now()}`,
          tool: 'policy.evaluate',
          status: 'completed',
          summary: `Policy check passed for Room: ${payload.room}`,
          timestamp: new Date().toISOString(),
        },
      ],
      executiveSummary: 'Task initialized. Bounded steps are running in simulated environment.',
      evidence: [],
    };

    this.jobs = [newJob, ...this.jobs];
    this.saveToStorage(STORAGE_KEYS.JOBS, this.jobs);

    this.recordAuditEvent({
      eventType: 'job.started',
      aggregateType: 'job',
      aggregateId: newJob.id,
      actor: 'user',
      safePayload: { goal: payload.goal, room: payload.room },
    });

    return newJob;
  }

  async pauseJob(jobId: string): Promise<AgentJob> {
    const index = this.jobs.findIndex((j) => j.id === jobId);
    if (index === -1) throw new Error(`Job ${jobId} not found`);

    this.jobs[index] = {
      ...this.jobs[index],
      status: 'paused',
      currentStage: 'Paused by user',
    };
    this.saveToStorage(STORAGE_KEYS.JOBS, this.jobs);
    return this.jobs[index];
  }

  async resumeJob(jobId: string): Promise<AgentJob> {
    const index = this.jobs.findIndex((j) => j.id === jobId);
    if (index === -1) throw new Error(`Job ${jobId} not found`);

    this.jobs[index] = {
      ...this.jobs[index],
      status: 'executing',
      currentStage: 'Executing next bounded step',
    };
    this.saveToStorage(STORAGE_KEYS.JOBS, this.jobs);
    return this.jobs[index];
  }

  async cancelJob(jobId: string): Promise<AgentJob> {
    const index = this.jobs.findIndex((j) => j.id === jobId);
    if (index === -1) throw new Error(`Job ${jobId} not found`);

    this.jobs[index] = {
      ...this.jobs[index],
      status: 'cancelled',
      currentStage: 'Cancelled by user',
      completedAt: new Date().toISOString(),
    };
    this.saveToStorage(STORAGE_KEYS.JOBS, this.jobs);
    return this.jobs[index];
  }

  // Audit Events
  async listAuditEvents(): Promise<AuditEvent[]> {
    return [...this.auditEvents];
  }

  private recordAuditEvent(event: Omit<AuditEvent, 'id' | 'occurredAt'>) {
    const newEvent: AuditEvent = {
      id: `audit-${Date.now().toString(36)}`,
      occurredAt: new Date().toISOString(),
      ...event,
    };
    this.auditEvents = [newEvent, ...this.auditEvents];
    this.saveToStorage(STORAGE_KEYS.AUDIT, this.auditEvents);
  }

  // Settings
  async getSettings(): Promise<SettingsState> {
    return { ...this.settings };
  }

  async updateSettings(patch: Partial<SettingsState>): Promise<SettingsState> {
    this.settings = {
      ...this.settings,
      ...patch,
    };
    this.saveToStorage(STORAGE_KEYS.SETTINGS, this.settings);
    return { ...this.settings };
  }
}
