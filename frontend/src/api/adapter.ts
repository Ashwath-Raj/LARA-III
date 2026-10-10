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
} from '../types';

import {
  TaskCaptureCandidate,
  TaskFilterParams,
  CreateTaskPayload,
  UpdateTaskPayload,
  ApprovalDecisionPayload,
  CreateJobPayload,
} from './types';

export interface GraphData {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
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

  // Project operations
  listProjects(): Promise<Project[]>;
  getProject(projectId: string): Promise<Project | null>;
  updateProject(projectId: string, patch: Partial<Project>): Promise<Project>;

  // Knowledge Graph operations
  getGraph(): Promise<GraphData>;

  // Conversation & Workbench
  listMessages(conversationId?: string): Promise<ConversationMessage[]>;
  listConversations(): Promise<ConversationSummary[]>;
  createConversation(): Promise<string>;
  selectConversation(conversationId: string): Promise<void>;
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
