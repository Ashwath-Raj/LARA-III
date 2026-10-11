/**
 * LARA IV API adapter interface
 * Aligned with Docs/05_ARCHITECTURE.md, Docs/06_API_CONTRACT.md, and Docs/03_DATA_AND_CHUNKING.md
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
  KnowledgeGraphNode,
  KnowledgeGraphEdge,
  ConversationMessage,
  ConversationSummary,
  AILoopSession,
  KnowledgeRoom,
} from '../types';

import {
  TaskCaptureCandidate,
  TaskFilterParams,
  CreateTaskPayload,
  UpdateTaskPayload,
  ApprovalDecisionPayload,
  CreateJobPayload,
  CreateAILoopPayload,
  PostLoopMessagePayload,
} from './types';

export interface GraphData {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
}

export interface CalendarEventRecord {
  id: string; title: string; description: string; room_id: string; starts_at: string;
  ends_at?: string | null; timezone: string; status: 'scheduled' | 'cancelled';
}

export interface UbuntuAgentApiAdapter {
  // Task operations
  captureTask(inputText: string): Promise<TaskCaptureCandidate>;
  createTask(payload: CreateTaskPayload): Promise<Task>;
  listTasks(filters?: TaskFilterParams): Promise<Task[]>;
  getTask(taskId: string): Promise<Task | null>;
  updateTask(taskId: string, patch: UpdateTaskPayload): Promise<Task>;
  transitionTask(taskId: string, targetStatus: TaskStatus): Promise<Task>;
  deleteTask(taskId: string): Promise<boolean>;
  reorderTasks(sourceIndex: number, destinationIndex: number, status: TaskStatus): Promise<Task[]>;

  // Reminder operations
  listReminders(): Promise<Reminder[]>;
  snoozeReminder(reminderId: string, minutes: number): Promise<Reminder>;
  dismissReminder(reminderId: string): Promise<Reminder>;
  cancelReminder(reminderId: string): Promise<Reminder>;
  createReminder(taskId: string, title: string, remindAt: string): Promise<Reminder>;
  listCalendarEvents(): Promise<CalendarEventRecord[]>;
  createCalendarEvent(event: Omit<CalendarEventRecord, 'id' | 'status'>): Promise<CalendarEventRecord>;
  cancelCalendarEvent(eventId: string): Promise<CalendarEventRecord>;

  // Project operations
  listProjects(): Promise<Project[]>;
  createProject(name: string, roomId?: KnowledgeRoom): Promise<Project>;
  deleteProject(projectId: string): Promise<void>;
  getProject(projectId: string): Promise<Project | null>;
  updateProject(projectId: string, patch: Partial<Project>): Promise<Project>;

  // Knowledge Graph operations
  getGraph(): Promise<GraphData>;

  // AI Loop operations
  listLoops(): Promise<AILoopSession[]>;
  getLoop(loopId: string): Promise<AILoopSession | null>;
  createLoop(payload: CreateAILoopPayload): Promise<AILoopSession>;
  postLoopMessage(loopId: string, payload: PostLoopMessagePayload): Promise<AILoopSession>;

  // Conversation & Workbench
  listMessages(conversationId?: string): Promise<ConversationMessage[]>;
  listConversations(): Promise<ConversationSummary[]>;
  createConversation(): Promise<string>;
  selectConversation(conversationId: string): Promise<void>;
  renameConversation(conversationId: string, title: string): Promise<void>;
  deleteConversation(conversationId: string): Promise<void>;
  setConversationMemory(conversationId: string, enabled: boolean): Promise<void>;
  excludeConversationMemory(conversationId: string, messageId: string): Promise<void>;
  sendMessage(content: string, roomId?: string, conversationId?: string): Promise<ConversationMessage>;

  // Approval operations
  listApprovals(): Promise<ApprovalRequest[]>;
  decideApproval(approvalId: string, payload: ApprovalDecisionPayload): Promise<ApprovalRequest>;

  // Job / Agent operations
  listJobs(): Promise<AgentJob[]>;
  createJob(payload: CreateJobPayload): Promise<AgentJob>;
  pauseJob(jobId: string): Promise<AgentJob>;
  resumeJob(jobId: string): Promise<AgentJob>;
  cancelJob(jobId: string): Promise<AgentJob>;

  // Audit events
  listAuditEvents(): Promise<AuditEvent[]>;

  // Settings
  getSettings(): Promise<SettingsState>;
  updateSettings(patch: Partial<SettingsState>): Promise<SettingsState>;

  // Undo support
  canUndo(): boolean;
  undo(): Promise<boolean>;
}
