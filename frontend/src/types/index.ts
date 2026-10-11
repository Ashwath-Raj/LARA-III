/**
 * LARA IV core domain models
 * Aligned with Docs/01_FEATURES_EXECUTIVE_OVERVIEW.md, Docs/03_DATA_AND_CHUNKING.md,
 * Docs/06_API_CONTRACT.md, Docs/07_UI_UX_SPEC.md, and Docs/09_AUTONOMY_POLICY_MATRIX.md.
 */

export type KnowledgeRoom =
  | 'public_research'
  | 'academic'
  | 'projects'
  | 'opportunities'
  | 'operations'
  | 'personal_vault'
  | 'health';

export type RoomSensitivity = 'local_only' | 'restricted' | 'cloud_allowed';

export interface RoomDefinition {
  id: KnowledgeRoom;
  name: string;
  description: string;
  sensitivity: RoomSensitivity;
  typicalContent: string;
  defaultCloudPolicy: string;
  itemCount: number;
  bridgesCount: number;
}

export type PersonaId =
  | 'task_manager'
  | 'exam_coach'
  | 'researcher'
  | 'desktop_operator';

export interface PersonaDefinition {
  id: PersonaId;
  name: string;
  role: string;
  description: string;
  accessMatrix: Record<KnowledgeRoom, 'R/W' | 'R' | 'P' | 'A' | 'none'>;
  suggestedActions: string[];
}

export type TaskStatus =
  | 'inbox'
  | 'next'
  | 'in_progress'
  | 'waiting'
  | 'review'
  | 'ready_to_submit'
  | 'done'
  | 'archived';

export type TaskPriority = 'high' | 'medium' | 'low';

export type TaskCategory =
  | 'Academics'
  | 'Projects'
  | 'Hackathons'
  | 'AI/ML'
  | 'Robotics'
  | 'Quantum'
  | 'Opportunities'
  | 'Personal/Admin';

export interface TaskAttachment {
  name: string;
  size: string;
  path: string;
  verified: boolean;
  mimeType?: string;
}

export interface ClassroomMetadata {
  courseName: string;
  assignmentName: string;
  submissionState: 'prepared' | 'submitted' | 'submission_verified' | 'unverified';
  targetDueDate?: string;
  classroomUrl?: string;
}

export interface Task {
  id: string;
  title: string;
  description?: string;
  status: TaskStatus;
  priority: TaskPriority;
  category: TaskCategory;
  room: KnowledgeRoom;
  dueDate?: string; // YYYY-MM-DD
  dueTime?: string; // HH:mm
  personalTargetDate?: string; // YYYY-MM-DD
  workSessionScheduledAt?: string; // ISO datetime for personal work session
  nextAction?: string;
  course?: string;
  project?: string;
  projectId?: string;
  attachments: TaskAttachment[];
  classroomMetadata?: ClassroomMetadata;
  createdAt: string;
  updatedAt: string;
  isSticky?: boolean;
  stickyColor?: 'beige' | 'white' | 'ash';
  remindersCount: number;
  tags: string[];
  dependsOn?: string[]; // array of Task IDs that block this task
}

export type ReminderStatus =
  | 'scheduled'
  | 'delivered'
  | 'snoozed'
  | 'missed'
  | 'dismissed'
  | 'cancelled';

export interface Reminder {
  id: string;
  taskId?: string;
  taskTitle?: string;
  title: string;
  remindAt: string; // ISO string
  status: ReminderStatus;
  type: 'due_date_warning' | 'study_checkpoint' | 'submission_prep' | 'custom';
  snoozeUntil?: string;
  deliveredAt?: string;
}

export interface ProjectMilestone {
  id: string;
  title: string;
  dueDate: string;
  completed: boolean;
}

export interface ProjectDependency {
  fromTaskId: string;
  toTaskId: string;
  reason: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  roomId: KnowledgeRoom;
  status: 'active' | 'planning' | 'completed' | 'on_hold';
  milestones: ProjectMilestone[];
  taskIds: string[];
  fileAttachments: TaskAttachment[];
  dependencies: ProjectDependency[];
  createdAt: string;
  updatedAt: string;
}

export type JobStatus =
  | 'queued'
  | 'planning'
  | 'researching'
  | 'reviewing'
  | 'awaiting_approval'
  | 'executing'
  | 'verifying'
  | 'completed'
  | 'blocked'
  | 'failed'
  | 'paused'
  | 'cancelled';

export interface ToolTrace {
  id: string;
  tool: string;
  status: 'completed' | 'in_progress' | 'blocked' | 'verified';
  summary: string;
  timestamp: string;
  outputExcerpt?: string;
}

export interface AgentJob {
  id: string;
  goal: string;
  status: JobStatus;
  currentStage: string;
  scope: string;
  room: KnowledgeRoom;
  modelUsed: string;
  route: 'Local (Ollama · Gemma 2B)' | 'Cloud (Hosted Reasoner)';
  startedAt: string;
  completedAt?: string;
  budgetTokensUsed: number;
  budgetMaxTokens: number;
  toolTraces: ToolTrace[];
  executiveSummary?: string;
  evidence: string[];
  pendingApprovalId?: string;
  uncertainties?: string[];
  nextRecommendedActions?: string[];
}

export type RiskTier =
  | 'read'
  | 'prepare'
  | 'reversible_write'
  | 'external_destructive'
  | 'privileged_system';

export interface ApprovalRequest {
  id: string;
  jobId?: string;
  title: string;
  plainLanguageAction: string;
  reason: string;
  targetResource: string;
  normalizedArguments: Record<string, unknown>;
  sourceRoom: KnowledgeRoom;
  destination: string;
  leavesMachine: boolean;
  riskTier: RiskTier;
  policyBasis: string;
  reversibility: 'Reversible' | 'Irreversible' | 'External submission';
  specificButtonLabel: string;
  status: 'pending' | 'approved' | 'rejected' | 'executed';
  createdAt: string;
  expiresAt: string;
  decidedAt?: string;
}

export interface AuditEvent {
  id: string;
  eventType: string;
  occurredAt: string;
  aggregateType: 'task' | 'job' | 'approval' | 'reminder' | 'system' | 'project';
  aggregateId: string;
  actor: string;
  safePayload: Record<string, unknown>;
}

export interface CrossRoomBridge {
  id: string;
  sourceRoom: KnowledgeRoom;
  destinationRoom: KnowledgeRoom;
  purpose: string;
  sharedFields: string[];
  downstreamCloudAllowed: boolean;
  status: 'active' | 'revoked';
  createdAt: string;
}

export interface ProviderStatus {
  ollamaLocal: {
    status: 'online' | 'offline' | 'simulated';
    model: string;
    vramUsed: string;
    contextLimit: number;
  };
  cloudReasoner: {
    status: 'standby' | 'restricted' | 'online' | 'disconnected';
    provider: string;
    policyStatus: string;
  };
}

export interface SettingsState {
  providerStatus: ProviderStatus;
  activeModel: string;
  temperature: number;
  routingPolicy: 'local_first' | 'local_only' | 'cloud_permitted';
  autonomyTier: 'strict_approval' | 'cautious' | 'autonomous_routine';
  requireApprovalForExternal: boolean;
  requireApprovalForFileDelete: boolean;
  quietHours: {
    enabled: boolean;
    start: string; // HH:mm
    end: string; // HH:mm
  };
  desktopNotifications: boolean;
  reducedMotion: boolean;
}

// Knowledge Graph domain types
export type GraphNodeType =
  | 'task'
  | 'course'
  | 'file'
  | 'project'
  | 'person'
  | 'source'
  | 'observation'
  | 'claim'
  | 'argument'
  | 'contradiction'
  | 'revision'
  | 'decision'
  | 'conclusion'
  | 'deadline'
  | 'job';

export interface KnowledgeGraphNode {
  id: string;
  nodeType: GraphNodeType;
  displayName: string;
  roomId: KnowledgeRoom;
  sensitivityLabel: RoomSensitivity;
  sourceRef: string;
  confidence?: number;
  lastUpdated: string;
  metadata: Record<string, unknown>;
  x?: number;
  y?: number;
}

export interface KnowledgeGraphEdge {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  relationType: string;
  roomId: KnowledgeRoom;
  whyConnected: string;
  provenance: string;
}

// Conversation / Chat messages
export interface ConversationMessage {
  id: string;
  conversationId: string;
  sender: 'user' | 'agent';
  content: string;
  timestamp: string;
  simulated?: boolean;
  roomId: KnowledgeRoom;
  route: 'Local only' | 'Cloud allowed';
  jobId?: string;
  attachments?: string[];
  sources?: Array<{ title: string; url?: string; excerpt: string }>;
  memoryStatus?: 'indexed' | 'excluded' | 'failed' | 'pending' | 'disabled' | 'not_indexed';
  retrievedMemories?: Array<{ title?: string; conversation_id?: string | null; message_id?: string | null; document_id?: string; chunk_id?: string; version?: number }>;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updatedAt: string;
  preview: string;
  messageCount: number;
  memoryEnabled?: boolean;
}

export interface MemoryReadiness {
  status: 'checking' | 'ready' | 'degraded' | 'unavailable';
  reason?: string | null;
  embedding_model?: string;
  embedding_model_status?: string;
  vector_store_status?: string;
}

// AI Loop Domain Models
export type AILoopRole = 'red_team' | 'blue_team' | 'judge' | 'reviewer';

export type AILoopContributionType =
  | 'proposal'
  | 'critique'
  | 'counterargument'
  | 'evidence'
  | 'revision'
  | 'review_finding'
  | 'judge_decision'
  | 'final_synthesis';

export interface AILoopParticipant {
  role: AILoopRole;
  name: string;
  title: string;
  description: string;
  configuredPrompt: string;
  constraints: string[];
  permissions?: string[];
  providerModel: string;
  isSimulated: boolean;
  activityState: 'idle' | 'thinking' | 'proposing' | 'critiquing' | 'reviewing' | 'deciding';
  latestContributionTime?: string;
  latestPreview?: string;
  executionStatus?: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  errorClass?: string;
}

export interface AILoopMessage {
  id: string;
  loopId: string;
  roundNumber: number;
  role: AILoopRole;
  timestamp: string;
  contributionType: AILoopContributionType;
  content: string;
  replyToMessageId?: string;
  evidenceReferences?: Array<{
    id: string;
    title: string;
    sourceType: 'benchmark' | 'log' | 'paper' | 'file' | 'code';
    provenance: string;
    excerpt: string;
    url?: string;
  }>;
  simulated: boolean;
}

export interface DesktopOperatorWindow {
  windowId: string;
  title: string;
  role: string;
  status: 'idle' | 'inspecting' | 'active' | 'blocked';
  currentObservation: string;
  lastAction?: string;
}

export interface DesktopOperatorMacroStep {
  id: string;
  stepNumber: number;
  action: 'click' | 'keypress' | 'navigate' | 'capture_screenshot' | 'read_dom';
  target: string;
  result: 'verified' | 'completed' | 'pending' | 'blocked';
  timestamp: string;
  screenshotRef?: string;
}

export interface DesktopOperatorContext {
  state: 'idle' | 'running' | 'awaiting_approval' | 'completed' | 'error';
  configuredPrompt?: string;
  cancellationState?: 'not_requested' | 'requested' | 'confirmed' | 'unconfirmed';
  errorMessage?: string;
  windows: DesktopOperatorWindow[];
  macroSteps: DesktopOperatorMacroStep[];
  gatheredArtifacts: Array<{
    id: string;
    name: string;
    type: string;
    size: string;
    provenance: string;
    excerpt: string;
  }>;
  approvalRequired?: {
    action: string;
    target: string;
    risk: string;
    policyBasis: string;
  };
}

export interface AILoopGraphNode extends KnowledgeGraphNode {
  loopId: string;
  roleScope: AILoopRole | 'shared';
  claimSummary: string;
  originatingRound?: number;
  relatedMessageIds: string[];
  linkedSourceIds: string[];
  disposition?: 'accepted' | 'challenged' | 'refuted' | 'resolved' | 'open';
}

export interface AILoopGraphEdge extends KnowledgeGraphEdge {
  loopId: string;
  roleScope: AILoopRole | 'shared';
}

export interface AILoopSynthesis {
  consolidatedConclusion: string;
  reviewVerdict?: 'pass' | 'revise' | 'insufficient_evidence';
  reviewerSummary?: string[];
  acceptedRecommendations: Array<{
    id: string;
    summary: string;
    supportingEvidence: string;
  }>;
  redTeamDispositions: Array<{
    objection: string;
    disposition: 'resolved' | 'accepted_risk' | 'mitigated' | 'open';
    resolutionDetails: string;
  }>;
  reviewerFindings: Array<{
    finding: string;
    status: 'addressed' | 'rejected_with_justification' | 'open';
    details: string;
  }>;
  judgeCriteria: Array<{
    criterion: string;
    weight: string;
    assessment: string;
  }>;
  outstandingDisagreements: string[];
  assumptionsAndUncertainties: string[];
  sourceArtifacts: Array<{
    id: string;
    title: string;
    ref: string;
    url?: string;
  }>;
}

export type AILoopStatus =
  | 'Created'
  | 'Gathering'
  | 'Debating'
  | 'Awaiting Approval'
  | 'Awaiting User'
  | 'Verifying'
  | 'Synthesized'
  | 'Failed'
  | 'Cancelled';

export interface AILoopSession {
  id: string;
  name: string;
  objective: string;
  constraints: string[];
  status: AILoopStatus;
  roundCount: number;
  currentRound: number;
  createdAt: string;
  updatedAt: string;
  participants: Record<AILoopRole, AILoopParticipant>;
  messages: AILoopMessage[];
  desktopContext: DesktopOperatorContext;
  graphNodes: AILoopGraphNode[];
  graphEdges: AILoopGraphEdge[];
  synthesis?: AILoopSynthesis;
  isSimulated: boolean;
}

export type ActiveScreen =
  | 'workbench'
  | 'loops'
  | 'today'
  | 'inbox'
  | 'kanban'
  | 'calendar'
  | 'projects'
  | 'graph'
  | 'run_console'
  | 'reminders'
  | 'rooms'
  | 'activity'
  | 'approvals'
  | 'settings';
