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
