/**
 * API Request & Response Shapes
 * Derived from Docs/06_API_CONTRACT.md
 */

import {
  Task,
  TaskStatus,
  KnowledgeRoom,
} from '../types';

export interface StandardErrorEnvelope {
  error: {
    code:
      | 'VALIDATION_ERROR'
      | 'NOT_FOUND'
      | 'POLICY_DENIED'
      | 'APPROVAL_REQUIRED'
      | 'APPROVAL_EXPIRED'
      | 'CONFLICT'
      | 'RATE_LIMITED'
      | 'PROVIDER_UNAVAILABLE'
      | 'BUDGET_EXCEEDED'
      | 'VERIFICATION_NEEDED'
      | 'INTERNAL_ERROR';
    message: string;
    details?: Record<string, unknown>;
    requestId: string;
  };
}

export interface TaskCaptureCandidate {
  rawText: string;
  suggestedTitle: string;
  suggestedCategory?: string;
  suggestedDueDate?: string;
  suggestedCourse?: string;
  suggestedFile?: string;
  suggestedReminderCadence?: string;
  missingFields: string[];
  clarificationQuestions: string[];
  requiresConfirmation: boolean;
}

export interface TaskFilterParams {
  status?: TaskStatus;
  category?: string;
  room?: KnowledgeRoom;
  searchQuery?: string;
}

export interface CreateTaskPayload {
  title: string;
  description?: string;
  category: Task['category'];
  room: KnowledgeRoom;
  priority: Task['priority'];
  dueDate?: string;
  dueTime?: string;
  course?: string;
  project?: string;
  nextAction?: string;
  isSticky?: boolean;
  stickyColor?: 'beige' | 'white' | 'ash';
}

export interface UpdateTaskPayload {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: Task['priority'];
  category?: Task['category'];
  room?: KnowledgeRoom;
  dueDate?: string;
  dueTime?: string;
  nextAction?: string;
  personalTargetDate?: string;
}

export interface ApprovalDecisionPayload {
  decision: 'approve' | 'reject';
  reason?: string;
}

export interface CreateJobPayload {
  goal: string;
  room: KnowledgeRoom;
  persona: string;
  budgetTokens?: number;
  parameters?: Record<string, unknown>;
}

export type CalendarConnectorStatus =
  | 'not_configured'
  | 'not_connected'
  | 'connecting'
  | 'connected'
  | 'reauthorization_required'
  | 'error';

export interface CalendarIntegrationState {
  provider: 'google_calendar';
  status: CalendarConnectorStatus;
  available: boolean;
  accountEmail?: string;
  lastSuccessfulSyncAt?: string;
  lastError?: string;
}

/** Implemented by a trusted backend adapter; OAuth tokens never belong in the browser. */
export interface GoogleCalendarIntegrationAdapter {
  getState(): Promise<CalendarIntegrationState>;
  connect(): Promise<CalendarIntegrationState>;
  disconnect(): Promise<CalendarIntegrationState>;
  sync(): Promise<{ completedAt: string; importedCount: number; updatedCount: number }>;
}

export const UNAVAILABLE_GOOGLE_CALENDAR: CalendarIntegrationState = {
  provider: 'google_calendar',
  status: 'not_configured',
  available: false,
};

export interface CreateAILoopPayload {
  name: string;
  objective: string;
  constraints: string[];
}

export interface PostLoopMessagePayload {
  role: 'red_team' | 'blue_team' | 'judge' | 'reviewer';
  content: string;
  contributionType:
    | 'proposal'
    | 'critique'
    | 'counterargument'
    | 'evidence'
    | 'revision'
    | 'review_finding'
    | 'judge_decision'
    | 'final_synthesis';
  replyToMessageId?: string;
}
