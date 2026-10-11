import { UbuntuAgentApiAdapter, GraphData, CalendarEventRecord } from './adapter';
import { Task, Reminder, AILoopSession, ConversationMessage, ConversationSummary, Project, ApprovalRequest, AgentJob, SettingsState, AuditEvent, KnowledgeGraphNode } from '../types';
import { TaskFilterParams, CreateTaskPayload, UpdateTaskPayload, CreateAILoopPayload, PostLoopMessagePayload } from './types';

const PREFIX = '/api/v1';
declare const __LARA_LOCAL_DEMO__: boolean;
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${PREFIX}${path}`, { credentials: __LARA_LOCAL_DEMO__ ? 'omit' : 'same-origin', ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `Local API request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
const json = (method: string, body?: unknown): RequestInit => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
const statusMap: Record<string, Task['status']> = { inbox: 'inbox', next: 'next', in_progress: 'in_progress', waiting: 'waiting', review: 'review', ready_to_submit: 'ready_to_submit', done: 'done', archived: 'archived' };
const categoryToBackend: Record<string,string> = { 'Hackathons':'Hackathons & Competitions','AI/ML':'AI/ML Research','Robotics':'Robotics','Quantum':'Quantum Computing','Personal/Admin':'Personal / Admin' };
const categoryToUi: Record<string,Task['category']> = { 'Hackathons & Competitions':'Hackathons','AI/ML Research':'AI/ML','Quantum Computing':'Quantum','Personal / Admin':'Personal/Admin','Waiting / Follow-up':'Personal/Admin' };
function task(row: any): Task {
  return { id: row.id, title: row.title, description: row.description || '', status: statusMap[row.status] || 'inbox',
    priority: row.priority === 'urgent' ? 'high' : row.priority === 'normal' ? 'medium' : row.priority,
    category: categoryToUi[row.category] || row.category as Task['category'], room: row.room_id, dueDate: row.due_date || undefined,
    dueTime: row.due_at ? new Date(row.due_at).toTimeString().slice(0, 5) : undefined,
    createdAt: row.created_at, updatedAt: row.updated_at, project:row.project_id || undefined, attachments: [], remindersCount: 0, tags: [] };
}
function reminder(row: any): Reminder {
  return { id: row.id, taskId: row.task_id, taskTitle: row.task_title, title: row.message,
    remindAt: row.scheduled_at, status: row.status, type: 'custom', snoozeUntil: row.snoozed_until, deliveredAt: row.delivered_at };
}
function project(row: any): Project {
  return { id:row.id,name:row.name,description:row.description,roomId:row.room_id,status:row.status,
    milestones:row.milestones || [],taskIds:row.task_ids || [],fileAttachments:[],dependencies:row.dependencies || [],
    createdAt:row.created_at,updatedAt:row.updated_at };
}
const roleNames: Record<string, 'blue_team'|'red_team'|'judge'|'reviewer'> = { blue_team:'blue_team', red_team:'red_team', judge:'judge', unbiased_reviewer:'reviewer' };
const graphNodeTypes: Record<string, KnowledgeGraphNode['nodeType']> = {
  goal:'task',constraint:'claim',claim:'claim',proposal:'argument',counterargument:'contradiction',
  evidence:'source',source_summary:'source',decision:'decision',unresolved:'contradiction',
  conclusion:'conclusion',external_response:'claim',
};
function loop(row: any, graph: any = {nodes:[],edges:[]}): AILoopSession {
  const roles = row.roles || [];
  const participants = Object.fromEntries((['blue_team','red_team','judge','unbiased_reviewer'] as const).map((name) => {
    const role = roles.find((item: any) => item.role_name === name);
    const uiRole = roleNames[name];
    return [uiRole, { role: uiRole, name: role?.role_label || name, title: role?.role_label || name,
      description: 'Local model role', configuredPrompt: '', constraints: [], providerModel: role?.executions?.at(-1)?.model_id || 'Ollama',
      isSimulated: false, activityState: role?.status === 'running' ? 'thinking' : 'idle',
      executionStatus: role?.status || 'pending', errorClass:role?.executions?.at(-1)?.error_class || undefined }];
  })) as unknown as AILoopSession['participants'];
  const messages = (row.rounds || []).filter((r: any) => r.status === 'succeeded' && r.role_name).map((r: any) => {
    let result: any = {}; try { result = JSON.parse(r.output_json || '{}'); } catch { result = {}; }
    const role = roleNames[r.role_name] || 'judge';
    const text = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
    return { id: r.id, loopId: row.id, roundNumber: r.round_index, role, timestamp: r.updated_at,
      contributionType: role === 'blue_team' ? 'proposal' : role === 'red_team' ? 'critique' : role === 'reviewer' ? 'review_finding' : 'judge_decision',
      content: text, simulated: false };
  });
  const state = row.execution?.status || row.status;
  const status: AILoopSession['status'] = state === 'succeeded' ? 'Synthesized' : state === 'review_required' ? 'Awaiting User'
    : state === 'failed' ? 'Failed' : state === 'cancelled' ? 'Cancelled' : state === 'running' ? 'Debating' : 'Created';
  const emptyDesktop = { state: 'idle' as const, windows: [], macroSteps: [], gatheredArtifacts: [] };
  let synthesis: AILoopSession['synthesis'];
  if (row.execution?.final_synthesis) {
    try {
      const final = JSON.parse(row.execution.final_synthesis);
      const reviewer = final.reviewer || {};
      const findings = [...(reviewer.unsupported_claims || []), ...(reviewer.unanswered_questions || []), ...(reviewer.potential_bias || [])];
      synthesis = {
        consolidatedConclusion: `${final.final_recommendation || ''}${final.rationale ? `\n\n${final.rationale}` : ''}`,
        reviewVerdict: final.review_verdict,
        reviewerSummary: reviewer.reasons || [],
        acceptedRecommendations: (final.accepted_arguments || []).map((summary:string,index:number)=>({id:`accepted-${index}`,summary,supportingEvidence:''})),
        redTeamDispositions: (final.unresolved_objections || []).map((objection:string)=>({objection,disposition:'open' as const,resolutionDetails:'The Judge recorded this objection as unresolved.'})),
        reviewerFindings: findings.map((finding:string)=>({finding,status:'open' as const,details:'Recorded by the Unbiased Reviewer.'})),
        judgeCriteria: [],
        outstandingDisagreements: final.unresolved_objections || [],
        assumptionsAndUncertainties: [...(final.confidence_limitations || []), ...(final.evidence_gaps || [])],
        sourceArtifacts: [],
      };
    } catch { synthesis = undefined; }
  }
  const nodeTypeMap: Record<string,AILoopSession['graphNodes'][number]['nodeType']> = {
    goal:'task',constraint:'claim',claim:'claim',proposal:'argument',counterargument:'contradiction',
    evidence:'source',source_summary:'source',decision:'decision',unresolved:'contradiction',conclusion:'conclusion',external_response:'claim',
  };
  const graphNodes = (graph.nodes || []).map((node:any) => {
    let provenance:any = {}; try { provenance=JSON.parse(node.provenance_json || '{}'); } catch { /* preserve the node without invented metadata */ }
    const sourceRound=(row.rounds || []).find((round:any)=>round.id===provenance.execution_id);
    return { id:node.id,loopId:row.id,nodeType:nodeTypeMap[node.node_type] || 'claim',displayName:node.display_name,
      roomId:node.room_id,sensitivityLabel:node.sensitivity_label,sourceRef:provenance.execution_id?`loop://invocation/${provenance.execution_id}`:`loop://node/${node.id}`,
      confidence:undefined,lastUpdated:node.updated_at,metadata:{source_content:node.content,...provenance},roleScope:'shared' as const,
      claimSummary:node.content,originatingRound:sourceRound?.round_index,relatedMessageIds:provenance.execution_id?[provenance.execution_id]:[],linkedSourceIds:[] };
  });
  const nodeIds = new Set(graphNodes.map((node:any)=>node.id));
  const graphEdges = (graph.edges || []).filter((edge:any)=>nodeIds.has(edge.source_node_id)&&nodeIds.has(edge.target_node_id)).map((edge:any)=>({
    id:edge.id,loopId:row.id,sourceNodeId:edge.source_node_id,targetNodeId:edge.target_node_id,relationType:edge.relation_type,
    roomId:edge.room_id,whyConnected:`Persisted ${edge.relation_type} relation`,provenance:`loop:${row.id}`,roleScope:'shared' as const,
  }));
  return { id: row.id, name: row.goal.slice(0, 120), objective: row.goal, constraints: row.constraints || [], status,
    roundCount: (row.rounds || []).length, currentRound: Math.max(1, row.execution?.current_round || 1),
    createdAt: row.created_at, updatedAt: row.updated_at, participants, messages, desktopContext: emptyDesktop,
    graphNodes, graphEdges, synthesis, isSimulated: false };
}

export class LocalUbuntuAgentApi implements UbuntuAgentApiAdapter {
  private activeConversationId = '';
  async connect(pairingToken: string) { return request('/auth/session', json('POST', { pairing_token: pairingToken })); }
  async session() { return request<{ authenticated: boolean }>('/auth/session'); }
  async health() { return request<any>('/health'); }
  async readiness() { return request<any>('/ready'); }
  async captureTask(inputText: string) { return { rawText: inputText, suggestedTitle: inputText.slice(0, 300), missingFields: [], clarificationQuestions: [], requiresConfirmation: true }; }
  async createTask(p: CreateTaskPayload) { return task(await request('/tasks', json('POST', { title:p.title, description:p.description || '', category:categoryToBackend[p.category] || p.category, room_id:p.room, priority:p.priority === 'medium' ? 'normal' : p.priority, project_id:p.project || null, due_date:p.dueDate || null, due_at:p.dueDate && p.dueTime ? new Date(`${p.dueDate}T${p.dueTime}`).toISOString() : null, timezone:Intl.DateTimeFormat().resolvedOptions().timeZone }))); }
  async listTasks(filters?: TaskFilterParams) { const data = await request<any>(`/tasks?limit=100${filters?.status ? `&status=${filters.status}` : ''}`); return data.items.map(task); }
  async getTask(id: string) { try { return task(await request(`/tasks/${id}`)); } catch { return null; } }
  async updateTask(id: string, p: UpdateTaskPayload) { const patch: any = {}; if(p.title!==undefined)patch.title=p.title; if(p.description!==undefined)patch.description=p.description; if(p.priority!==undefined)patch.priority=p.priority==='medium'?'normal':p.priority; if(p.category!==undefined)patch.category=categoryToBackend[p.category]||p.category; if(p.project!==undefined)patch.project_id=p.project||null; if(p.dueDate!==undefined){patch.due_date=p.dueDate||null;patch.due_at=p.dueDate&&p.dueTime?new Date(`${p.dueDate}T${p.dueTime}`).toISOString():null;} return task(await request(`/tasks/${id}`,json('PATCH',patch))); }
  async transitionTask(id: string, target: Task['status']) { return task(await request(`/tasks/${id}/transitions`,json('POST',{target_status:target,evidence:target==='done'?'Completed in LARA IV':''}))); }
  async deleteTask(taskId: string): Promise<boolean> { await request(`/tasks/${taskId}`,json('DELETE')); return true; }
  async reorderTasks(_source: number, _destination: number, _status: Task['status']) { return this.listTasks(); }
  async listReminders() { return (await request<any>('/reminders?limit=100')).items.map(reminder); }
  async snoozeReminder(id: string, minutes=30) { return reminder(await request(`/reminders/${id}/snooze`,json('POST',{until:new Date(Date.now()+minutes*60000).toISOString()}))); }
  async dismissReminder(id: string) { return reminder(await request(`/reminders/${id}/dismiss`,json('POST'))); }
  async cancelReminder(id: string) { return reminder(await request(`/reminders/${id}/cancel`,json('POST'))); }
  async createReminder(taskId: string, title: string, remindAt: string) { return reminder(await request('/reminders',json('POST',{task_id:taskId,message:title,scheduled_at:new Date(remindAt).toISOString()}))); }
  async listCalendarEvents(): Promise<CalendarEventRecord[]> { return (await request<any>('/calendar/events?limit=100')).items; }
  async createCalendarEvent(event: Omit<CalendarEventRecord, 'id'|'status'>): Promise<CalendarEventRecord> { return request('/calendar/events',json('POST',{title:event.title,description:event.description,room_id:event.room_id,starts_at:event.starts_at,ends_at:event.ends_at || null,timezone:event.timezone})); }
  async cancelCalendarEvent(id:string):Promise<CalendarEventRecord>{return request(`/calendar/events/${id}/cancel`,json('POST'));}
  async listProjects(): Promise<Project[]> { return (await request<any[]>('/projects')).map(project); }
  async getProject(id: string): Promise<Project | null> { return project(await request(`/projects/${id}`)); }
  async createProject(name: string, roomId: any = 'operations'): Promise<Project> { return project(await request('/projects',json('POST',{name,room_id:roomId}))); }
  async updateProject(id: string, patch: Partial<Project>): Promise<Project> { return project(await request(`/projects/${id}`,json('PATCH',{...(patch.name!==undefined?{name:patch.name}:{}),...(patch.description!==undefined?{description:patch.description}:{}),...(patch.status!==undefined?{status:patch.status}:{}),...(patch.milestones!==undefined?{milestones:patch.milestones}:{})}))); }
  async deleteProject(id: string): Promise<void> { await request(`/projects/${id}`,json('DELETE')); }
  async getGraph(): Promise<GraphData> {
    const page = await request<any>('/loops?limit=100');
    const graphs = await Promise.all((page.items || []).map((item:any) =>
      request<any>(`/loops/${item.id}/graph`)));
    const nodes = graphs.flatMap((graph:any) => graph.nodes || []).map((node:any) => {
      let provenance:any = {}; try { provenance=JSON.parse(node.provenance_json || '{}'); } catch { /* keep stored content without inferred provenance */ }
      return { id:node.id, nodeType:graphNodeTypes[node.node_type] || 'claim',
        displayName:node.display_name, roomId:node.room_id, sensitivityLabel:node.sensitivity_label, sourceRef:provenance.execution_id ? `loop://invocation/${provenance.execution_id}` : `loop://node/${node.id}`,
        metadata:{source_content:node.content,...provenance}, lastUpdated:node.updated_at };
    });
    const edges = graphs.flatMap((graph:any) => graph.edges || []).map((edge:any) => ({ id:edge.id,
      sourceNodeId:edge.source_node_id,targetNodeId:edge.target_node_id,relationType:edge.relation_type,
      roomId:edge.room_id,whyConnected:`Persisted ${edge.relation_type} relation`,provenance:`loop:${edge.loop_id || 'authorized'}` }));
    return { nodes, edges };
  }
  async listLoops(): Promise<AILoopSession[]> { return (await request<any>('/loops?limit=100')).items.map((x:any)=>loop(x)); }
  async getLoop(id: string) { const [row,graphData]=await Promise.all([request<any>(`/loops/${id}`),request<any>(`/loops/${id}/graph`)]); return loop(row,graphData); }
  async createLoop(p: CreateAILoopPayload) { const row=await request<any>('/loops',json('POST',{goal:p.objective,constraints:p.constraints,max_rounds:8})); return this.getLoop(row.id); }
  async runLoop(id: string) { const current=await request<any>(`/loops/${id}`); const path=current.execution?.invocation_count ? 'resume' : 'run'; await request(`/loops/${id}/${path}`,json('POST',{})); return this.getLoop(id); }
  async cancelLoop(id: string) { await request(`/loops/${id}/cancel`,json('POST')); return this.getLoop(id); }
  async postLoopMessage(_id: string, _p: PostLoopMessagePayload): Promise<AILoopSession> { throw new Error('Role messages come from real model execution and cannot be entered manually.'); }
  async listMessages(id?: string): Promise<ConversationMessage[]> {
    const conversationId = id || this.activeConversationId;
    if (!conversationId) return [];
    const rows = await request<any[]>(`/conversations/${conversationId}/messages`);
    return rows.map((row) => ({ id:row.id, conversationId:row.conversation_id, sender:row.sender === 'assistant' ? 'agent' : 'user', content:row.content,
      timestamp:row.created_at, roomId:'operations', route:'Local only', simulated:false, memoryStatus:row.memory_status,
      retrievedMemories:row.retrieved_memories || [] } as ConversationMessage));
  }
  async listConversations(): Promise<ConversationSummary[]> { return (await request<any[]>('/conversations')).map(row=>({id:row.id,title:row.title,updatedAt:row.updated_at,preview:row.preview||'',messageCount:row.message_count,memoryEnabled:!!row.memory_enabled})); }
  async createConversation(): Promise<string> { const result=await request<any>('/conversations',json('POST',{})); this.activeConversationId=result.id; return result.id; }
  async selectConversation(id: string): Promise<void> { this.activeConversationId=id; }
  async renameConversation(id: string,title: string): Promise<void> { await request(`/conversations/${id}`,json('PATCH',{title})); }
  async deleteConversation(id: string): Promise<void> { await request(`/conversations/${id}`,json('DELETE')); }
  async setConversationMemory(id: string,enabled: boolean): Promise<void> { await request(`/conversations/${id}`,json('PATCH',{memory_enabled:enabled})); }
  async excludeConversationMemory(id: string,messageId: string): Promise<void> { await request(`/conversations/${id}/memory/${messageId}/exclude`,json('POST')); }
  async sendMessage(content: string, _room?: any, conversationId?: string): Promise<ConversationMessage> {
    const id=conversationId||this.activeConversationId; if(!id) throw new Error('Select or create a conversation first.');
    const row=await request<any>(`/conversations/${id}/messages`,{...json('POST',{content}),headers:{'Idempotency-Key':crypto.randomUUID()}});
    return {id:row.id,conversationId:id,sender:'agent',content:row.content,timestamp:row.created_at,roomId:'operations',route:'Local only',simulated:false,
      memoryStatus:row.memory_status,retrievedMemories:row.retrieved_memories || []} as ConversationMessage;
  }
  async retryConversationMemory(conversationId: string, messageId: string) { return request(`/conversations/${conversationId}/memory/${messageId}/retry`,json('POST')); }
  async listApprovals(): Promise<ApprovalRequest[]> { return []; } async decideApproval(_id: string, _payload: any): Promise<ApprovalRequest> { throw new Error('Approvals are unavailable in the local API.'); }
  async listJobs(): Promise<AgentJob[]> { return []; } async createJob(_payload: any): Promise<AgentJob> { throw new Error('Jobs are unavailable in the local API.'); }
  async pauseJob(_id: string): Promise<AgentJob> { throw new Error('Jobs are unavailable in the local API.'); } async resumeJob(_id: string): Promise<AgentJob> { throw new Error('Jobs are unavailable in the local API.'); } async cancelJob(_id: string): Promise<AgentJob> { throw new Error('Jobs are unavailable in the local API.'); }
  async listAuditEvents() { const page=await request<any>('/audit-events?limit=100'); return page.items.map((row:any)=>({id:row.id,eventType:row.event_type,occurredAt:row.occurred_at,aggregateType:row.aggregate_type,aggregateId:row.aggregate_id,actor:row.actor,safePayload:row.safe_payload||{}} as AuditEvent)); }
  async getSettings(): Promise<SettingsState> { return { providerStatus:{ollamaLocal:{status:'unknown'}},activeModel:'Ollama local',temperature:0,routingPolicy:'local_only',autonomyTier:'strict_approval',requireApprovalForExternal:true,requireApprovalForFileDelete:true,quietHours:{enabled:false,start:'22:00',end:'08:00'},desktopNotifications:false,reducedMotion:false } as any; }
  async updateSettings(_patch: Partial<SettingsState>): Promise<SettingsState> { throw new Error('Settings controls are not available in the local API.'); }
  resetDemoData(): void { throw new Error('Demo data reset is disabled while connected to the persistent backend.'); }
  canUndo() { return false; } async undo() { return false; }
}
