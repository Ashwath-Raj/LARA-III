/**
 * LARA IV global reactive context
 * Provides shared state across the 3-region workspace:
 * Left Navigation Rail, Context-sensitive Canvas, and Inspectable Context Drawer.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from 'react';

import {
  ActiveScreen,
  KnowledgeRoom,
  PersonaId,
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
  CreateTaskPayload,
  UpdateTaskPayload,
  TaskCaptureCandidate,
  CreateJobPayload,
} from '../api/types';

import { MockUbuntuAgentApi } from '../api/mockAdapter';

export type DrawerType = 'none' | 'task' | 'node' | 'job' | 'approval';

interface AgentContextType {
  // Navigation & Workspace Shell
  activeScreen: ActiveScreen;
  setActiveScreen: (screen: ActiveScreen) => void;
  runConsolePreviewGoal: string | null;
  openRunPreview: (goal: string) => void;
  clearRunPreview: () => void;
  activeRoom: KnowledgeRoom;
  setActiveRoom: (room: KnowledgeRoom) => void;
  activePersona: PersonaId;
  setActivePersona: (persona: PersonaId) => void;
  isLeftRailCollapsed: boolean;
  setIsLeftRailCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;

  // Search & Filtering
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  selectedCategory: string;
  setSelectedCategory: (cat: string) => void;

  // Context Drawer / Detail Inspections
  selectedTask: Task | null;
  setSelectedTask: (task: Task | null) => void;
  openTaskDetail: (task: Task) => void;
  closeTaskDetail: () => void;

  selectedGraphNode: KnowledgeGraphNode | null;
  setSelectedGraphNode: (node: KnowledgeGraphNode | null) => void;
  openNodeDetail: (node: KnowledgeGraphNode) => void;

  selectedJob: AgentJob | null;
  setSelectedJob: (job: AgentJob | null) => void;
  openJobDetail: (job: AgentJob) => void;

  selectedApproval: ApprovalRequest | null;
  setSelectedApproval: (app: ApprovalRequest | null) => void;
  openApprovalDetail: (app: ApprovalRequest) => void;

  activeDrawerType: DrawerType;
  closeAllDrawers: () => void;

  // Data Collections
  tasks: Task[];
  reminders: Reminder[];
  approvals: ApprovalRequest[];
  jobs: AgentJob[];
  auditEvents: AuditEvent[];
  settings: SettingsState;
  projects: Project[];
  graphNodes: KnowledgeGraphNode[];
  graphEdges: KnowledgeGraphEdge[];
  messages: ConversationMessage[];
  conversations: ConversationSummary[];
  activeConversationId: string;
  loading: boolean;
  graphLoadError: string | null;
  canUndo: boolean;

  // Actions
  captureTask: (text: string) => Promise<TaskCaptureCandidate>;
  createTask: (payload: CreateTaskPayload) => Promise<Task>;
  updateTask: (taskId: string, patch: UpdateTaskPayload) => Promise<Task>;
  transitionTask: (taskId: string, targetStatus: TaskStatus) => Promise<Task>;
  reorderTasks: (sourceIndex: number, destinationIndex: number, status: TaskStatus) => Promise<Task[]>;
  deleteTask: (taskId: string) => Promise<boolean>;
  undo: () => Promise<boolean>;

  snoozeReminder: (reminderId: string, minutes?: number) => Promise<Reminder>;
  dismissReminder: (reminderId: string) => Promise<Reminder>;
  cancelReminder: (reminderId: string) => Promise<Reminder>;
  createReminder: (taskId: string, title: string, remindAt: string) => Promise<Reminder>;

  updateProject: (projectId: string, patch: Partial<Project>) => Promise<Project>;
  sendMessage: (content: string, roomId?: string, conversationId?: string) => Promise<ConversationMessage>;
  createConversation: () => Promise<void>;
  selectConversation: (conversationId: string) => Promise<void>;

  decideApproval: (approvalId: string, decision: 'approve' | 'reject') => Promise<ApprovalRequest>;

  createJob: (payload: CreateJobPayload) => Promise<AgentJob>;
  pauseJob: (jobId: string) => Promise<AgentJob>;
  resumeJob: (jobId: string) => Promise<AgentJob>;
  cancelJob: (jobId: string) => Promise<AgentJob>;

  updateSettings: (patch: Partial<SettingsState>) => Promise<SettingsState>;

  // Quick Capture modal trigger
  isQuickCaptureOpen: boolean;
  setIsQuickCaptureOpen: (open: boolean) => void;

  refreshAll: () => Promise<void>;
  resetDemoData: () => Promise<void>;
}

const AgentContext = createContext<AgentContextType | undefined>(undefined);

export const AgentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const api = useMemo(() => new MockUbuntuAgentApi(), []);

  // Shell Layout
  const [activeScreen, setActiveScreen] = useState<ActiveScreen>('workbench');
  const [runConsolePreviewGoal, setRunConsolePreviewGoal] = useState<string | null>(null);
  const [activeRoom, setActiveRoom] = useState<KnowledgeRoom>('operations');
  const [activePersona, setActivePersona] = useState<PersonaId>('task_manager');
  const [isLeftRailCollapsed, setIsLeftRailCollapsed] = useState<boolean>(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState<boolean>(false);

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  // Inspection Drawer
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [selectedGraphNode, setSelectedGraphNode] = useState<KnowledgeGraphNode | null>(null);
  const [selectedJob, setSelectedJob] = useState<AgentJob | null>(null);
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRequest | null>(null);

  const [isQuickCaptureOpen, setIsQuickCaptureOpen] = useState<boolean>(false);

  // Core Data Collections
  const [tasks, setTasks] = useState<Task[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [jobs, setJobs] = useState<AgentJob[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [settings, setSettings] = useState<SettingsState>({} as SettingsState);
  const [projects, setProjects] = useState<Project[]>([]);
  const [graphNodes, setGraphNodes] = useState<KnowledgeGraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<KnowledgeGraphEdge[]>([]);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState('');
  const [loading, setLoading] = useState<boolean>(true);
  const [graphLoadError, setGraphLoadError] = useState<string | null>(null);
  const [canUndoState, setCanUndoState] = useState<boolean>(false);

  // Derive which drawer is currently active
  const activeDrawerType: DrawerType = useMemo(() => {
    if (selectedTask) return 'task';
    if (selectedGraphNode) return 'node';
    if (selectedJob && activeScreen !== 'run_console') return 'job';
    if (selectedApproval) return 'approval';
    return 'none';
  }, [activeScreen, selectedTask, selectedGraphNode, selectedJob, selectedApproval]);

  const closeAllDrawers = useCallback(() => {
    setSelectedTask(null);
    setSelectedGraphNode(null);
    setSelectedJob(null);
    setSelectedApproval(null);
  }, []);

  const openTaskDetail = useCallback((task: Task) => {
    closeAllDrawers();
    setSelectedTask(task);
  }, [closeAllDrawers]);

  const closeTaskDetail = useCallback(() => {
    setSelectedTask(null);
  }, []);

  const openNodeDetail = useCallback((node: KnowledgeGraphNode) => {
    closeAllDrawers();
    setSelectedGraphNode(node);
  }, [closeAllDrawers]);

  const openJobDetail = useCallback((job: AgentJob) => {
    closeAllDrawers();
    setSelectedJob(job);
  }, [closeAllDrawers]);

  const openRunPreview = useCallback((goal: string) => {
    const cleanGoal = goal.trim();
    if (!cleanGoal) return;
    closeAllDrawers();
    setRunConsolePreviewGoal(cleanGoal);
    setActiveScreen('run_console');
  }, [closeAllDrawers]);

  const clearRunPreview = useCallback(() => setRunConsolePreviewGoal(null), []);

  const openApprovalDetail = useCallback((app: ApprovalRequest) => {
    closeAllDrawers();
    setSelectedApproval(app);
  }, [closeAllDrawers]);

  // Initial load from mock API
  const refreshAll = useCallback(async () => {
    try {
      const [t, r, a, j, aud, s, p, g, m, conversationList] = await Promise.all([
        api.listTasks(),
        api.listReminders(),
        api.listApprovals(),
        api.listJobs(),
        api.listAuditEvents(),
        api.getSettings(),
        api.listProjects(),
        api.getGraph(),
        api.listMessages(),
        api.listConversations(),
      ]);
      setTasks(t);
      setReminders(r);
      setApprovals(a);
      setJobs(j);
      setAuditEvents(aud);
      setSettings(s);
      setProjects(p);
      setGraphNodes(g.nodes);
      setGraphEdges(g.edges);
      setGraphLoadError(null);
      setMessages(m);
      setConversations(conversationList);
      setActiveConversationId(m[0]?.conversationId || await api.createConversation());
      setCanUndoState(api.canUndo());
    } catch (err) {
      setGraphLoadError('The browser demo could not load graph records.');
      console.error('Error loading initial agent state', err);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Global Keyboard shortcuts: Ctrl+K / Cmd+K for command palette, Escape to close drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      } else if (e.key === 'Escape') {
        if (commandPaletteOpen) {
          setCommandPaletteOpen(false);
        } else if (activeDrawerType !== 'none') {
          closeAllDrawers();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, activeDrawerType, closeAllDrawers]);

  // Action wrappers that update local state
  const captureTask = useCallback(
    async (text: string) => {
      return api.captureTask(text);
    },
    [api]
  );

  const createTask = useCallback(
    async (payload: CreateTaskPayload) => {
      const created = await api.createTask(payload);
      setTasks((prev) => [created, ...prev]);
      setCanUndoState(api.canUndo());
      const updatedAudits = await api.listAuditEvents();
      setAuditEvents(updatedAudits);
      return created;
    },
    [api]
  );

  const updateTask = useCallback(
    async (taskId: string, patch: UpdateTaskPayload) => {
      const updated = await api.updateTask(taskId, patch);
      setTasks((prev) => prev.map((t) => (t.id === taskId ? updated : t)));
      if (selectedTask?.id === taskId) {
        setSelectedTask(updated);
      }
      const updatedAudits = await api.listAuditEvents();
      setAuditEvents(updatedAudits);
      return updated;
    },
    [api, selectedTask]
  );

  const transitionTask = useCallback(
    async (taskId: string, targetStatus: TaskStatus) => {
      const updated = await api.transitionTask(taskId, targetStatus);
      setTasks((prev) => prev.map((t) => (t.id === taskId ? updated : t)));
      setCanUndoState(api.canUndo());
      if (selectedTask?.id === taskId) {
        setSelectedTask(updated);
      }
      const updatedAudits = await api.listAuditEvents();
      setAuditEvents(updatedAudits);
      return updated;
    },
    [api, selectedTask]
  );

  const reorderTasks = useCallback(
    async (sourceIndex: number, destinationIndex: number, status: TaskStatus) => {
      const updatedTasks = await api.reorderTasks(sourceIndex, destinationIndex, status);
      setTasks(updatedTasks);
      setCanUndoState(api.canUndo());
      return updatedTasks;
    },
    [api]
  );

  const deleteTask = useCallback(
    async (taskId: string) => {
      const ok = await api.deleteTask(taskId);
      if (ok) {
        setTasks((prev) => prev.filter((t) => t.id !== taskId));
        setCanUndoState(api.canUndo());
        if (selectedTask?.id === taskId) {
          setSelectedTask(null);
        }
      }
      return ok;
    },
    [api, selectedTask]
  );

  const undo = useCallback(async () => {
    const ok = await api.undo();
    if (ok) {
      const refreshedTasks = await api.listTasks();
      setTasks(refreshedTasks);
      setCanUndoState(api.canUndo());
      const updatedAudits = await api.listAuditEvents();
      setAuditEvents(updatedAudits);
    }
    return ok;
  }, [api]);

  const snoozeReminder = useCallback(
    async (reminderId: string, minutes = 30) => {
      const updated = await api.snoozeReminder(reminderId, minutes);
      setReminders((prev) => prev.map((r) => (r.id === reminderId ? updated : r)));
      return updated;
    },
    [api]
  );

  const dismissReminder = useCallback(
    async (reminderId: string) => {
      const updated = await api.dismissReminder(reminderId);
      setReminders((prev) => prev.map((r) => (r.id === reminderId ? updated : r)));
      return updated;
    },
    [api]
  );

  const cancelReminder = useCallback(async (reminderId: string) => {
    const updated = await api.cancelReminder(reminderId);
    setReminders((previous) => previous.map((reminder) => reminder.id === reminderId ? updated : reminder));
    return updated;
  }, [api]);

  const createReminder = useCallback(
    async (taskId: string, title: string, remindAt: string) => {
      const created = await api.createReminder(taskId, title, remindAt);
      setReminders((prev) => [created, ...prev]);
      const updatedTasks = await api.listTasks();
      setTasks(updatedTasks);
      return created;
    },
    [api]
  );

  const updateProject = useCallback(
    async (projectId: string, patch: Partial<Project>) => {
      const updated = await api.updateProject(projectId, patch);
      setProjects((prev) => prev.map((p) => (p.id === projectId ? updated : p)));
      return updated;
    },
    [api]
  );

  const sendMessage = useCallback(
    async (content: string, roomId?: string, conversationId = activeConversationId) => {
      const agentMsg = await api.sendMessage(content, roomId || activeRoom, conversationId);
      const allMsgs = await api.listMessages(conversationId);
      setMessages(allMsgs);
      setConversations(await api.listConversations());
      return agentMsg;
    },
    [api, activeRoom, activeConversationId]
  );

  const createConversation = useCallback(async () => {
    const id = await api.createConversation();
    setActiveConversationId(id);
    setMessages([]);
  }, [api]);

  const selectConversation = useCallback(async (conversationId: string) => {
    await api.selectConversation(conversationId);
    setActiveConversationId(conversationId);
    setMessages(await api.listMessages(conversationId));
  }, [api]);

  const decideApproval = useCallback(
    async (approvalId: string, decision: 'approve' | 'reject') => {
      const decided = await api.decideApproval(approvalId, { decision });
      setApprovals((prev) => prev.map((a) => (a.id === approvalId ? decided : a)));
      if (selectedApproval?.id === approvalId) {
        setSelectedApproval(decided);
      }
      const updatedJobs = await api.listJobs();
      setJobs(updatedJobs);
      const updatedAudits = await api.listAuditEvents();
      setAuditEvents(updatedAudits);
      return decided;
    },
    [api, selectedApproval]
  );

  const createJob = useCallback(
    async (payload: CreateJobPayload) => {
      const job = await api.createJob(payload);
      setJobs((prev) => [job, ...prev]);
      const updatedAudits = await api.listAuditEvents();
      setAuditEvents(updatedAudits);
      return job;
    },
    [api]
  );

  const pauseJob = useCallback(
    async (jobId: string) => {
      const job = await api.pauseJob(jobId);
      setJobs((prev) => prev.map((j) => (j.id === jobId ? job : j)));
      if (selectedJob?.id === jobId) {
        setSelectedJob(job);
      }
      return job;
    },
    [api, selectedJob]
  );

  const resumeJob = useCallback(
    async (jobId: string) => {
      const job = await api.resumeJob(jobId);
      setJobs((prev) => prev.map((j) => (j.id === jobId ? job : j)));
      if (selectedJob?.id === jobId) {
        setSelectedJob(job);
      }
      return job;
    },
    [api, selectedJob]
  );

  const cancelJob = useCallback(
    async (jobId: string) => {
      const job = await api.cancelJob(jobId);
      setJobs((prev) => prev.map((j) => (j.id === jobId ? job : j)));
      if (selectedJob?.id === jobId) {
        setSelectedJob(job);
      }
      return job;
    },
    [api, selectedJob]
  );

  const updateSettings = useCallback(
    async (patch: Partial<SettingsState>) => {
      const updated = await api.updateSettings(patch);
      setSettings(updated);
      return updated;
    },
    [api]
  );

  const resetDemoData = useCallback(async () => {
    api.resetDemoData();
    closeAllDrawers();
    setIsQuickCaptureOpen(false);
    setSearchQuery('');
    setSelectedCategory('all');
    await refreshAll();
  }, [api, closeAllDrawers, refreshAll]);

  return (
    <AgentContext.Provider
      value={{
        activeScreen,
        setActiveScreen,
        runConsolePreviewGoal,
        openRunPreview,
        clearRunPreview,
        activeRoom,
        setActiveRoom,
        activePersona,
        setActivePersona,
        isLeftRailCollapsed,
        setIsLeftRailCollapsed,
        commandPaletteOpen,
        setCommandPaletteOpen,
        searchQuery,
        setSearchQuery,
        selectedCategory,
        setSelectedCategory,
        selectedTask,
        setSelectedTask,
        openTaskDetail,
        closeTaskDetail,
        selectedGraphNode,
        setSelectedGraphNode,
        openNodeDetail,
        selectedJob,
        setSelectedJob,
        openJobDetail,
        selectedApproval,
        setSelectedApproval,
        openApprovalDetail,
        activeDrawerType,
        closeAllDrawers,
        tasks,
        reminders,
        approvals,
        jobs,
        auditEvents,
        settings,
        projects,
        graphNodes,
        graphEdges,
        messages,
        conversations,
        activeConversationId,
        loading,
        graphLoadError,
        canUndo: canUndoState,
        captureTask,
        createTask,
        updateTask,
        transitionTask,
        reorderTasks,
        deleteTask,
        undo,
        snoozeReminder,
        dismissReminder,
        cancelReminder,
        createReminder,
        updateProject,
        sendMessage,
        createConversation,
        selectConversation,
        decideApproval,
        createJob,
        pauseJob,
        resumeJob,
        cancelJob,
        updateSettings,
        isQuickCaptureOpen,
        setIsQuickCaptureOpen,
        refreshAll,
        resetDemoData,
      }}
    >
      {children}
    </AgentContext.Provider>
  );
};

export const useAgent = (): AgentContextType => {
  const context = useContext(AgentContext);
  if (!context) {
    throw new Error('useAgent must be used within an AgentProvider');
  }
  return context;
};
