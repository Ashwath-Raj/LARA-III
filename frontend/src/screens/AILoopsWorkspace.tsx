import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle, ArrowDownLeft, ArrowUpRight, ChevronDown, Circle, Clipboard,
  ExternalLink, FileDown, FileText, GitBranch, History, Plus, Search, ShieldCheck, X,
} from 'lucide-react';
import { adaptPersistedGraph } from '../api/graphAdapter';
import { GraphCanvas, GraphErrorBoundary, supportsWebGL } from './KnowledgeGraphWorkspace';
import { useAgent } from '../context/AgentContext';
import {
  AILoopGraphEdge, AILoopGraphNode, AILoopMessage, AILoopParticipant,
  AILoopRole, AILoopSession,
} from '../types';
import './AILoopsWorkspace.css';

type WorkspaceTab = 'meeting' | 'graph' | 'synthesis' | 'records';
type LoopViewState = {
  loopId: string;
  tab: WorkspaceTab;
  showCreateForm: boolean;
  selectedMessageId: string | null;
};
type GraphScope = AILoopRole | 'shared';
type SafeArtifact = {
  id: string;
  name: string;
  type: string;
  provenance: string;
  excerpt: string;
  url?: string;
};

const ROLE_ORDER: AILoopRole[] = ['red_team', 'blue_team', 'judge', 'reviewer'];
const ROLE_LABEL: Record<AILoopRole, string> = {
  red_team: 'Red Team',
  blue_team: 'Blue Team',
  judge: 'Judge',
  reviewer: 'Unbiased Reviewer',
};
const ROLE_CLASS: Record<AILoopRole, string> = {
  red_team: 'role-red',
  blue_team: 'role-blue',
  judge: 'role-judge',
  reviewer: 'role-reviewer',
};
const CONTRIBUTION_LABEL: Record<AILoopMessage['contributionType'], string> = {
  proposal: 'Proposal',
  critique: 'Critique',
  counterargument: 'Response',
  evidence: 'Evidence',
  revision: 'Revision',
  review_finding: 'Review finding',
  judge_decision: 'Verdict',
  final_synthesis: 'Synthesis',
};
const GRAPH_SCOPES: Array<{ id: GraphScope; label: string }> = [
  { id: 'shared', label: 'Shared Project Graph' },
  { id: 'red_team', label: 'Red Team' },
  { id: 'blue_team', label: 'Blue Team' },
  { id: 'judge', label: 'Judge' },
  { id: 'reviewer', label: 'Unbiased Reviewer' },
];
const EMAIL_OR_SECRET_VALUE = /\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|credential)\b["']?\s*[:=]\s*["']?([^\s"',;}]+)["']?/gi;
const EMAIL_ADDRESS = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const RAW_TOKEN = /\b(?:Bearer\s+[A-Za-z0-9._~+/-]+=*|gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{16,}|sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{30,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b/gi;

function redactSensitiveText(value: string): string {
  return value
    .replace(EMAIL_OR_SECRET_VALUE, '$1=[redacted]')
    .replace(RAW_TOKEN, '[redacted credential]')
    .replace(EMAIL_ADDRESS, '[redacted email]');
}

function safeReference(value: string): string {
  const clean = redactSensitiveText(value.trim());
  if (clean.startsWith('/')) return clean.split('/').filter(Boolean).at(-1) || 'Local source';
  return clean.replace(/^local:\/\//, 'Local source · ');
}

function safeHttpUrl(value?: string): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;
    url.username = '';
    url.password = '';
    for (const key of [...url.searchParams.keys()]) {
      if (/api[_-]?key|token|password|secret|auth|signature|credential|session/i.test(key)) {
        url.searchParams.delete(key);
      }
    }
    url.hash = '';
    return url.toString();
  } catch {
    return null;
  }
}

function localDate(value?: string): string {
  if (!value || !Number.isFinite(Date.parse(value))) return 'Time not recorded';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function lifecycle(status: AILoopSession['status']): { category: string; label: string } {
  if (status === 'Synthesized') return { category: 'completed', label: 'Completed · synthesis recorded' };
  if (status === 'Failed') return { category: 'failed', label: 'Failed' };
  if (status === 'Cancelled') return { category: 'cancelled', label: 'Cancelled' };
  if (status === 'Awaiting User') return { category: 'awaiting', label: 'Awaiting user' };
  if (status === 'Awaiting Approval') return { category: 'awaiting', label: 'Awaiting approval' };
  return { category: 'active', label: status === 'Created' ? 'Created' : `Active · ${status}` };
}

function activityLabel(participant: AILoopParticipant): string {
  if (participant.isSimulated) return 'Simulated record';
  if (participant.executionStatus === 'failed') return `Failed${participant.errorClass ? ` · ${participant.errorClass}` : ''}`;
  if (participant.executionStatus === 'cancelled') return 'Cancelled';
  if (participant.executionStatus === 'pending') return 'Not run';
  if (participant.executionStatus === 'succeeded') return 'Completed';
  if (participant.activityState === 'idle') return 'Execution recorded';
  return participant.activityState.replaceAll('_', ' ');
}

function participantMessages(loop: AILoopSession, role: AILoopRole): AILoopMessage[] {
  return loop.messages
    .filter((message) => message.loopId === loop.id && message.role === role)
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

function latestMessage(loop: AILoopSession, role: AILoopRole): AILoopMessage | undefined {
  return participantMessages(loop, role).at(-1);
}

function collectArtifacts(loop: AILoopSession): SafeArtifact[] {
  const artifacts = new Map<string, SafeArtifact>();
  loop.desktopContext.gatheredArtifacts.forEach((artifact) => {
    artifacts.set(artifact.id, {
      id: artifact.id,
      name: redactSensitiveText(artifact.name),
      type: redactSensitiveText(artifact.type),
      provenance: safeReference(artifact.provenance),
      excerpt: redactSensitiveText(artifact.excerpt),
    });
  });
  loop.messages.forEach((message) => message.evidenceReferences?.forEach((reference) => {
    artifacts.set(reference.id, {
      id: reference.id,
      name: redactSensitiveText(reference.title),
      type: reference.sourceType,
      provenance: safeReference(reference.provenance),
      excerpt: redactSensitiveText(reference.excerpt),
      url: safeHttpUrl(reference.url) || undefined,
    });
  }));
  loop.synthesis?.sourceArtifacts.forEach((artifact) => {
    const existing = artifacts.get(artifact.id);
    artifacts.set(artifact.id, {
      id: artifact.id,
      name: existing?.name || redactSensitiveText(artifact.title),
      type: existing?.type || 'Source reference',
      provenance: existing?.provenance || safeReference(artifact.ref),
      excerpt: existing?.excerpt || '',
      url: safeHttpUrl(artifact.url) || existing?.url,
    });
  });
  return [...artifacts.values()];
}

function formattedMessage(text: string): React.ReactNode[] {
  return redactSensitiveText(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>;
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function buildFinalPrompt(loop: AILoopSession): string {
  const synthesis = loop.synthesis;
  if (!synthesis) return '';
  const sources = synthesis.sourceArtifacts.map((source) => `- ${redactSensitiveText(source.title)} (${safeReference(source.ref)})`).join('\n');
  return [
    `Goal: ${redactSensitiveText(loop.objective)}`,
    `Conclusion: ${redactSensitiveText(synthesis.consolidatedConclusion)}`,
    'Accepted recommendations:',
    ...synthesis.acceptedRecommendations.map((item) => `- ${redactSensitiveText(item.summary)} Evidence: ${redactSensitiveText(item.supportingEvidence)}`),
    'Open disagreements and uncertainties:',
    ...synthesis.outstandingDisagreements.map((item) => `- ${redactSensitiveText(item)}`),
    ...synthesis.assumptionsAndUncertainties.map((item) => `- ${redactSensitiveText(item)}`),
    'Sources:',
    sources || '- No source references recorded.',
  ].join('\n');
}

function sanitizeForExport(value: unknown, key = ''): unknown {
  if (typeof value === 'string') {
    if (/^(url)$/i.test(key)) return safeHttpUrl(value) || undefined;
    if (/(ref|provenance|path)$/i.test(key)) return safeReference(value);
    return redactSensitiveText(value);
  }
  if (Array.isArray(value)) return value.map((item) => sanitizeForExport(item));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([childKey, child]) => [
      childKey,
      sanitizeForExport(child, childKey),
    ]).filter(([, child]) => child !== undefined));
  }
  return value;
}

function downloadExport(loop: AILoopSession, format: 'json' | 'md'): void {
  const body = format === 'json'
    ? JSON.stringify(sanitizeForExport(loop), null, 2)
    : buildFinalPrompt(loop);
  const blob = new Blob([body], { type: format === 'json' ? 'application/json' : 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${loop.id}-report.${format === 'json' ? 'json' : 'md'}`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function safeHttpLink(url?: string, label?: string): React.ReactNode {
  const safeUrl = safeHttpUrl(url);
  return safeUrl
    ? <a href={safeUrl} target="_blank" rel="noreferrer">{label || safeUrl}<ExternalLink size={12} /></a>
    : null;
}

function LoopCreationForm({ onCancel }: { onCancel: () => void }) {
  const { createLoop } = useAgent();
  const [name, setName] = useState('');
  const [objective, setObjective] = useState('');
  const [constraints, setConstraints] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await createLoop({
        name,
        objective,
        constraints: constraints.split('\n').map((item) => item.trim()).filter(Boolean),
      });
      onCancel();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The loop could not be saved.');
      setSaving(false);
    }
  };

  return <form className="loop-create-form" onSubmit={(event) => void submit(event)}>
    <header><div><p className="loop-eyebrow">NEW SESSION</p><h2>Set up a loop</h2></div>
      <button type="button" className="loop-icon-button" aria-label="Close new loop form" onClick={onCancel}><X size={16} /></button></header>
    <label>Session name<input required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} placeholder="Compare cache eviction strategies" /></label>
    <label>Goal<textarea required maxLength={6000} rows={4} value={objective} onChange={(event) => setObjective(event.target.value)} placeholder="State the outcome to evaluate with local reasoning roles." /></label>
    <label>Constraints <span>One per line, optional</span><textarea maxLength={6000} rows={3} value={constraints} onChange={(event) => setConstraints(event.target.value)} placeholder="Keep the data local&#10;Compare measured p95 latency" /></label>
    <p className="loop-create-note">This saves a new session. Start model execution separately from its meeting room.</p>
    {error && <p className="loop-inline-error" role="alert"><AlertCircle size={14} />{error}</p>}
    <footer><button type="button" className="loop-button loop-button-quiet" onClick={onCancel}>Cancel</button><button type="submit" className="loop-button loop-button-primary" disabled={saving}>{saving ? 'Saving…' : 'Create loop'}</button></footer>
  </form>;
}

function MessageCard({ loop, message, selected, onSelect }: {
  loop: AILoopSession;
  message: AILoopMessage;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const role = loop.participants[message.role];
  return <article id={message.id} className={`loop-message ${ROLE_CLASS[message.role]}${selected ? ' is-highlighted' : ''}`}>
    <header>
      <span className="loop-role-mark" aria-hidden="true" />
      <button className="loop-message-role" onClick={() => onSelect(message.id)}>{role.name}</button>
      <span className="loop-message-type">{CONTRIBUTION_LABEL[message.contributionType]}</span>
      <span className="loop-message-round">Round {message.roundNumber}</span>
      <time dateTime={message.timestamp}>{localDate(message.timestamp)}</time>
    </header>
    <p className="loop-message-content">{formattedMessage(message.content)}</p>
    {!!message.evidenceReferences?.length && <ul className="loop-evidence-list" aria-label="Evidence references">
      {message.evidenceReferences.map((reference) => <li key={reference.id}>
        {safeHttpLink(reference.url, reference.title) || <span className="loop-evidence-link"><FileText size={12} />{redactSensitiveText(reference.title)}</span>}
        <small>{reference.sourceType} · {safeReference(reference.provenance)}</small>
      </li>)}
    </ul>}
    <small className="loop-simulation-stamp">{message.simulated ? 'Simulated contribution' : 'Persisted model output'}</small>
  </article>;
}

function RoleSeat({ loop, role, selected, onSelect }: {
  loop: AILoopSession;
  role: AILoopRole;
  selected: boolean;
  onSelect: (role: AILoopRole) => void;
}) {
  const participant = loop.participants[role];
  const latest = latestMessage(loop, role);
  return <button className={`loop-seat ${ROLE_CLASS[role]} seat-${role}${selected ? ' is-selected' : ''}`}
    onClick={() => onSelect(role)} aria-pressed={selected}>
    <span className="loop-seat-top"><span className="loop-role-mark" /><strong>{ROLE_LABEL[role]}</strong></span>
    <span className="loop-seat-state"><Circle size={8} fill="currentColor" />{activityLabel(participant)}</span>
    <span className="loop-seat-contribution">{latest ? `${CONTRIBUTION_LABEL[latest.contributionType]} · ${redactSensitiveText(latest.content).replace(/\s+/g, ' ').slice(0, 88)}` : 'No contribution recorded'}</span>
  </button>;
}

function DesktopOperatorPanel({ loop }: { loop: AILoopSession }) {
  const context = loop.desktopContext;
  return <section className="loop-panel loop-desktop-panel" aria-labelledby="loop-desktop-title">
    <header className="loop-panel-heading">
      <div><span className="loop-panel-icon"><ShieldCheck size={15} /></span><div><h2 id="loop-desktop-title">Desktop operator</h2><p>Read-only session record</p></div></div>
      <span className={`loop-status-tag desktop-${context.state}`}>{loop.isSimulated ? 'Simulated' : context.state.replaceAll('_', ' ')}</span>
    </header>
    <div className="loop-window-grid">
      {[0, 1, 2, 3].map((index) => {
        const window = context.windows[index];
        return <div className={`loop-window-slot${window ? ` window-${window.status}` : ' window-empty'}`} key={window?.windowId || `slot-${index + 1}`}>
          <span className="loop-window-number">Window {index + 1}</span>
          {window ? <>
            <strong>{redactSensitiveText(window.title)}</strong>
            <small>{window.role} · {window.status}</small>
            <p>{redactSensitiveText(window.currentObservation)}</p>
            {window.lastAction && <small>Last recorded action: {redactSensitiveText(window.lastAction)}</small>}
          </> : <p>No window assigned or observed.</p>}
        </div>;
      })}
    </div>
    <div className="loop-desktop-meta">
      <div className="loop-subsection-heading"><h3>Macro steps</h3><span>{context.macroSteps.length} recorded</span></div>
      {context.macroSteps.length ? <ol className="loop-macro-list">{context.macroSteps.map((step) => <li key={step.id}>
        <span className={`macro-result result-${step.result}`}>{step.result}</span>
        <div><strong>{step.stepNumber}. {step.action.replaceAll('_', ' ')}</strong><p>{redactSensitiveText(step.target)}</p></div>
        <time dateTime={step.timestamp}>{localDate(step.timestamp)}</time>
        {step.screenshotRef && <small className="macro-artifact-ref">Screenshot reference: {safeReference(step.screenshotRef)}</small>}
      </li>)}</ol> : <p className="loop-empty-copy">No macro steps are recorded for this session.</p>}
      {context.approvalRequired && <div className="loop-approval-record"><strong>Approval recorded as required</strong><p>{redactSensitiveText(context.approvalRequired.action)} · {redactSensitiveText(context.approvalRequired.target)}</p><small>{redactSensitiveText(context.approvalRequired.risk)} · {redactSensitiveText(context.approvalRequired.policyBasis)}</small></div>}
      {context.errorMessage && <p className="loop-inline-error"><AlertCircle size={14} />{redactSensitiveText(context.errorMessage)}</p>}
      {context.state === 'error' && !context.errorMessage && <p className="loop-inline-error"><AlertCircle size={14} />The adapter recorded an error without details.</p>}
      <p className="loop-cancellation">Cancellation: {(context.cancellationState || 'not_requested').replaceAll('_', ' ')}</p>
    </div>
  </section>;
}

function ParticipantInspector({ loop, role, onShowMessage, artifacts }: {
  loop: AILoopSession;
  role: AILoopRole;
  onShowMessage: (id: string) => void;
  artifacts: SafeArtifact[];
}) {
  const participant = loop.participants[role];
  const messages = participantMessages(loop, role);
  const graphNodes = loop.graphNodes.filter((node) => node.loopId === loop.id
    && (node.roleScope === role || node.roleScope === 'shared')
    && node.relatedMessageIds.some((id) => messages.some((message) => message.id === id)));
  const linkedArtifacts = new Map(artifacts.filter((artifact) =>
    graphNodes.some((node) => node.linkedSourceIds.includes(artifact.id))).map((artifact) => [artifact.id, artifact]));
  return <section className={`loop-panel loop-participant-inspector ${ROLE_CLASS[role]}`} aria-labelledby="loop-participant-inspector-title">
    <header className="loop-panel-heading"><div><span className="loop-role-mark" /><div><p className="loop-eyebrow">PARTICIPANT INSPECTOR</p><h2 id="loop-participant-inspector-title">{participant.name}</h2></div></div></header>
    <p className="loop-participant-description">{participant.description}</p>
    <dl className="loop-inspector-facts">
      <div><dt>Role</dt><dd>{participant.title}</dd></div>
      <div><dt>Provider / model</dt><dd>{participant.providerModel || 'Not recorded'}{participant.isSimulated ? ' · simulated configuration' : ''}</dd></div>
      <div><dt>Activity</dt><dd>{activityLabel(participant)}</dd></div>
    </dl>
    <div className="loop-inspector-section"><h3>Configured prompt</h3><p>{redactSensitiveText(participant.configuredPrompt) || 'No prompt recorded.'}</p></div>
    <div className="loop-inspector-section"><h3>Responsibilities and constraints</h3>
      <ul>{participant.constraints.map((item, index) => <li key={`${index}-${item}`}>{redactSensitiveText(item)}</li>)}</ul>
      {participant.permissions?.length ? <div className="loop-permission-list"><span>Permissions</span><ul>{participant.permissions.map((item, index) => <li key={`${index}-${item}`}>{redactSensitiveText(item)}</li>)}</ul></div> : <p className="loop-empty-copy">No permissions are recorded for this participant.</p>}
    </div>
    <div className="loop-inspector-section"><h3>Recorded contributions ({messages.length})</h3>
      {messages.length ? <ul className="loop-inspector-contributions">{messages.map((message) => <li key={message.id}>
        <button onClick={() => onShowMessage(message.id)}><span>Round {message.roundNumber} · {CONTRIBUTION_LABEL[message.contributionType]}</span><small>{redactSensitiveText(message.content).replace(/\s+/g, ' ').slice(0, 115)}</small></button>
      </li>)}</ul> : <p className="loop-empty-copy">No contribution is recorded in this session. The participant has not run.</p>}
    </div>
    <div className="loop-inspector-section"><h3>Linked claims and evidence</h3>
      {graphNodes.length ? <ul className="loop-inspector-links">{graphNodes.map((node) => <li key={node.id}><strong>{redactSensitiveText(node.displayName)}</strong><small>{node.originatingRound ? `Round ${node.originatingRound}` : 'Session record'} · {node.disposition || 'no disposition recorded'}</small></li>)}</ul> : <p className="loop-empty-copy">No linked graph claims are recorded.</p>}
      {linkedArtifacts.size > 0 && <ul className="loop-inspector-links">{[...linkedArtifacts.values()].map((artifact) => <li key={artifact.id}><strong>{artifact.name}</strong><small>{artifact.type} · {artifact.provenance}</small></li>)}</ul>}
    </div>
    {loop.status === 'Failed' && <p className="loop-inline-error"><AlertCircle size={14} />The session is marked failed; no additional work is implied.</p>}
    {loop.status === 'Awaiting User' && <p className="loop-pending-note">This session is waiting for user input.</p>}
  </section>;
}

function MeetingRoom({ loop, selectedRole, selectRole, selectedMessageId, showMessage }: {
  loop: AILoopSession;
  selectedRole: AILoopRole;
  selectRole: (role: AILoopRole) => void;
  selectedMessageId: string | null;
  showMessage: (id: string) => void;
}) {
  const rounds = useMemo(() => {
    const grouped = new Map<number, AILoopMessage[]>();
    [...loop.messages].filter((message) => message.loopId === loop.id)
      .sort((a, b) => a.roundNumber - b.roundNumber || a.timestamp.localeCompare(b.timestamp))
      .forEach((message) => grouped.set(message.roundNumber, [...(grouped.get(message.roundNumber) || []), message]));
    return [...grouped.entries()];
  }, [loop.id, loop.messages]);
  const roleFilteredMessages = selectedRole
    ? loop.messages.filter((message) => message.role === selectedRole)
    : loop.messages;

  return <div className="loop-meeting-layout">
    <aside className="loop-brief-column">
      <section className="loop-panel loop-brief-panel">
        <p className="loop-eyebrow">CURRENT LOOP</p>
        <h2>{redactSensitiveText(loop.name)}</h2>
        <span className={`loop-status-tag status-${lifecycle(loop.status).category}`}>{lifecycle(loop.status).label}</span>
        <p className="loop-objective">{redactSensitiveText(loop.objective)}</p>
        <dl className="loop-brief-meta"><div><dt>Created</dt><dd>{localDate(loop.createdAt)}</dd></div><div><dt>Last activity</dt><dd>{localDate(loop.updatedAt)}</dd></div><div><dt>Rounds</dt><dd>{loop.roundCount}</dd></div></dl>
        <div className="loop-constraints"><h3>Constraints</h3>{loop.constraints.length
          ? <ul>{loop.constraints.map((item, index) => <li key={`${index}-${item}`}>{redactSensitiveText(item)}</li>)}</ul>
          : <p>No session constraints recorded.</p>}</div>
      </section>
      <section className="loop-panel loop-role-selectors" aria-labelledby="loop-select-participant-title">
        <div className="loop-subsection-heading"><h2 id="loop-select-participant-title">Participants</h2><span>Select to inspect</span></div>
        {ROLE_ORDER.map((role) => {
          const count = participantMessages(loop, role).length;
          return <button className={`loop-role-selector ${ROLE_CLASS[role]}${selectedRole === role ? ' is-selected' : ''}`} key={role}
            onClick={() => selectRole(role)} aria-pressed={selectedRole === role}>
            <span className="loop-role-mark" /><span><strong>{ROLE_LABEL[role]}</strong><small>{count} recorded {count === 1 ? 'contribution' : 'contributions'}</small></span><ChevronDown size={14} />
          </button>;
        })}
      </section>
    </aside>
    <section className="loop-debate-column" aria-label="Debate timeline">
      <header className="loop-debate-heading"><div><p className="loop-eyebrow">PERSISTED MODEL INVOCATIONS</p><h2>Meeting room</h2><p>Only completed role invocations appear in the discussion.</p></div>
        <span className="loop-debate-count">{roleFilteredMessages.length} {roleFilteredMessages.length === 1 ? 'contribution' : 'contributions'}</span></header>
      {rounds.length ? <div className="loop-round-history">
        {rounds.map(([round, messages], index) => <details key={round} open={round === loop.currentRound || (rounds.length === 1 && index === 0)} className="loop-round">
          <summary><span>Round {round}</span><small>{messages.length} recorded contributions</small><ChevronDown size={15} /></summary>
          <div className="loop-round-messages">{messages.map((message) => <MessageCard key={message.id} loop={loop} message={message}
            selected={selectedMessageId === message.id} onSelect={showMessage} />)}</div>
        </details>)}
      </div> : <div className="loop-empty-state">
        <GitBranch size={20} /><h3>No debate contributions yet</h3>
        <p>The session is saved with its goal and role configuration. No agent has run, so the timeline is empty.</p>
      </div>}
      {loop.status === 'Awaiting User' && <p className="loop-pending-note">The loop is waiting for a user response. No role is currently running.</p>}
      {loop.status === 'Failed' && <p className="loop-inline-error"><AlertCircle size={14} />This loop is marked failed. No retry has been started.</p>}
      {loop.status === 'Cancelled' && <p className="loop-pending-note">This loop was cancelled. Existing records remain available.</p>}
    </section>
    <aside className="loop-room-aside">
      <section className="loop-panel loop-conference-panel" aria-labelledby="loop-conference-title">
        <header className="loop-panel-heading"><div><span className="loop-panel-icon"><History size={15} /></span><div><h2 id="loop-conference-title">Conference table</h2><p>Choose a seat to inspect its record</p></div></div></header>
        <div className="loop-conference-table" role="group" aria-label="Four participant seats">
          <RoleSeat loop={loop} role="judge" selected={selectedRole === 'judge'} onSelect={selectRole} />
          <RoleSeat loop={loop} role="red_team" selected={selectedRole === 'red_team'} onSelect={selectRole} />
          <div className="loop-table-surface"><span>Loop session</span><small>{loop.isSimulated ? 'Simulated' : 'Recorded'}</small></div>
          <RoleSeat loop={loop} role="blue_team" selected={selectedRole === 'blue_team'} onSelect={selectRole} />
          <RoleSeat loop={loop} role="reviewer" selected={selectedRole === 'reviewer'} onSelect={selectRole} />
        </div>
      </section>
      <ParticipantInspector loop={loop} role={selectedRole} artifacts={collectArtifacts(loop)} onShowMessage={showMessage} />
      <DesktopOperatorPanel loop={loop} />
    </aside>
  </div>;
}

function LoopGraph({ loop, onShowMessage }: { loop: AILoopSession; onShowMessage: (id: string) => void }) {
  const [scope, setScope] = useState<GraphScope>('shared');
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedNode, setSelectedNode] = useState<AILoopGraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<AILoopGraphEdge | null>(null);
  const [webglAvailable] = useState(supportsWebGL);
  const [reducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const artifacts = useMemo(() => collectArtifacts(loop), [loop]);
  const scopedNodes = useMemo(() => {
    const nodes = loop.graphNodes.filter((node) => node.loopId === loop.id);
    const edges = loop.graphEdges.filter((edge) => edge.loopId === loop.id);
    if (scope === 'shared') return nodes;
    const included = new Set(nodes.filter((node) => node.roleScope === scope || node.roleScope === 'shared').map((node) => node.id));
    edges.filter((edge) => edge.roleScope === scope || edge.roleScope === 'shared').forEach((edge) => {
      if (included.has(edge.sourceNodeId)) included.add(edge.targetNodeId);
      if (included.has(edge.targetNodeId)) included.add(edge.sourceNodeId);
    });
    return nodes.filter((node) => included.has(node.id));
  }, [loop.graphEdges, loop.graphNodes, loop.id, scope]);
  const query = search.trim().toLocaleLowerCase();
  const visibleNodes = scopedNodes.filter((node) =>
    (typeFilter === 'all' || node.nodeType === typeFilter)
    && (!query || `${node.displayName} ${node.claimSummary} ${node.sourceRef}`.toLocaleLowerCase().includes(query)));
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = loop.graphEdges.filter((edge) => edge.loopId === loop.id
    && visibleIds.has(edge.sourceNodeId) && visibleIds.has(edge.targetNodeId)
    && (scope === 'shared' || edge.roleScope === 'shared' || edge.roleScope === scope));
  const graph = useMemo(() => adaptPersistedGraph({ nodes: visibleNodes, edges: visibleEdges }), [visibleNodes, visibleEdges]);
  const selected = selectedNode && scopedNodes.find((node) => node.id === selectedNode.id);
  const selectedRelation = selectedEdge && visibleEdges.find((edge) => edge.id === selectedEdge.id);
  const messageById = new Map(loop.messages.map((message) => [message.id, message]));
  const typeOptions = [...new Set(scopedNodes.map((node) => node.nodeType))];

  return <section className="loop-graph-view" aria-labelledby="loop-graph-title">
    <header className="loop-subview-heading"><div><p className="loop-eyebrow">SESSION RECORDS</p><h2 id="loop-graph-title">Knowledge graph</h2><p>Explicit claims, evidence and links from this loop only.</p></div>
      <span className="loop-status-tag">{loop.isSimulated ? 'Simulated records' : 'Recorded data'}</span></header>
    <div className="loop-graph-scope" role="group" aria-label="Choose graph view">
      {GRAPH_SCOPES.map((option) => <button key={option.id} className={scope === option.id ? 'is-selected' : ''}
        onClick={() => setScope(option.id)} aria-pressed={scope === option.id}>{option.label}</button>)}
    </div>
    {scope !== 'shared' && <p className="loop-graph-scope-note">This view includes the participant's records and explicitly linked neighboring records. No relationships are inferred.</p>}
    <div className="loop-graph-toolbar">
      <label><Search size={14} /><span className="sr-only">Search graph</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search claims, nodes or sources" /></label>
      <label><span className="sr-only">Filter graph by node type</span><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">All record types</option>{typeOptions.map((type) => <option value={type} key={type}>{type.replaceAll('_', ' ')}</option>)}</select></label>
      <span>{visibleNodes.length} nodes · {visibleEdges.length} explicit links</span>
    </div>
    {!loop.graphNodes.some((node) => node.loopId === loop.id) ? <div className="loop-empty-state">
      <GitBranch size={20} /><h3>No graph records yet</h3><p>Claims and evidence appear here only after they are recorded in this session.</p>
    </div> : !visibleNodes.length ? <div className="loop-empty-state"><Search size={20} /><h3>No matching graph records</h3><p>Try another search term or record type.</p></div>
      : <div className="loop-graph-layout">
        <div className="loop-graph-main">
          {webglAvailable ? <GraphErrorBoundary><GraphCanvas graph={graph} selectedNode={selected || null} selectedEdge={selectedRelation ?? null}
            search="" typeFilter="all" roomFilter="all" reducedMotion={reducedMotion}
            onSelectNode={(node) => { const actual = scopedNodes.find((item) => item.id === node.id); if (actual) { setSelectedNode(actual); setSelectedEdge(null); } }}
            onSelectEdge={(edge) => { const actual = visibleEdges.find((item) => item.id === edge.id); if (actual) { setSelectedEdge(actual); setSelectedNode(null); } }} /></GraphErrorBoundary>
            : <p className="graph-fallback-status">WebGL is unavailable. Use the searchable record list below.</p>}
          <section className="graph-node-list loop-graph-record-list" aria-labelledby="loop-graph-records-title">
            <header><h2 id="loop-graph-records-title">Visible records</h2><span>Keyboard accessible</span></header>
            <ul>{visibleNodes.map((node) => <li key={node.id}><button className={selected?.id === node.id ? 'is-selected' : ''} onClick={() => { setSelectedNode(node); setSelectedEdge(null); }} aria-pressed={selected?.id === node.id}>
              <span className="graph-node-dot" /><span className="graph-list-title">{redactSensitiveText(node.displayName)}</span><small>{node.nodeType.replaceAll('_', ' ')} · {node.originatingRound ? `Round ${node.originatingRound}` : 'Session record'}</small>
            </button></li>)}</ul>
          </section>
          <section className="graph-node-list graph-edge-list" aria-labelledby="loop-graph-links-title">
            <header><h2 id="loop-graph-links-title">Explicit relationships</h2><span>{visibleEdges.length}</span></header>
            <ul>{visibleEdges.map((edge) => <li key={edge.id}><button className={selectedEdge?.id === edge.id ? 'is-selected' : ''} onClick={() => { setSelectedEdge(edge); setSelectedNode(null); }} aria-pressed={selectedEdge?.id === edge.id}>
              <span className="graph-list-title">{scopedNodes.find((node) => node.id === edge.sourceNodeId)?.displayName} → {scopedNodes.find((node) => node.id === edge.targetNodeId)?.displayName}</span><small>{edge.relationType.replaceAll('_', ' ')}</small>
            </button></li>)}</ul>
          </section>
        </div>
        <aside className="graph-detail-panel loop-graph-detail" aria-live="polite">
          {selected ? <>
            <header><span className="graph-detail-type">{selected.nodeType.replaceAll('_', ' ')} · {selected.originatingRound ? `Round ${selected.originatingRound}` : 'Session record'}</span><button aria-label="Clear selected node" onClick={() => setSelectedNode(null)}><X size={16} /></button></header>
            <h2>{redactSensitiveText(selected.displayName)}</h2>
            <p className="graph-detail-scope">{selected.roleScope === 'shared' ? 'Shared session record' : ROLE_LABEL[selected.roleScope]}</p>
            <dl><div><dt>Recorded claim or observation</dt><dd>{redactSensitiveText(selected.claimSummary)}</dd></div>
              <div><dt>Disposition</dt><dd>{selected.disposition || 'Not recorded'}</dd></div>
              <div><dt>Source provenance</dt><dd>{safeReference(selected.sourceRef)}</dd></div>
              <div><dt>Confidence in record</dt><dd>{typeof selected.confidence === 'number' && Number.isFinite(selected.confidence) ? `${Math.round(selected.confidence * 100)}%` : 'Not recorded'}</dd></div>
            </dl>
            <section className="graph-relations"><h3><ArrowDownLeft size={13} />Related messages</h3>
              {selected.relatedMessageIds.length ? selected.relatedMessageIds.map((id) => {
                const message = messageById.get(id);
                return message ? <button key={id} onClick={() => onShowMessage(id)}><span>Round {message.roundNumber} · {ROLE_LABEL[message.role]}</span><small>{redactSensitiveText(message.content).replace(/\s+/g, ' ').slice(0, 90)}</small></button> : <p key={id}>Message reference {id} is unavailable.</p>;
              }) : <p>No message links recorded.</p>}
            </section>
            <section className="graph-relations"><h3><ArrowUpRight size={13} />Linked sources</h3>
              {selected.linkedSourceIds.length ? selected.linkedSourceIds.map((id) => {
                const artifact = artifacts.find((item) => item.id === id);
                return artifact ? <div className="loop-graph-source" key={id}><strong>{artifact.name}</strong><small>{artifact.type} · {artifact.provenance}</small>{safeHttpLink(artifact.url, 'Open source')}</div> : <p key={id}>Source reference {id} is unavailable.</p>;
              }) : <p>No source references recorded.</p>}
            </section>
          </> : selectedRelation ? <>
            <header><span className="graph-detail-type">Explicit loop relationship</span><button aria-label="Clear selected relationship" onClick={() => setSelectedEdge(null)}><X size={16} /></button></header>
            <h2>{scopedNodes.find((node) => node.id === selectedRelation.sourceNodeId)?.displayName} → {scopedNodes.find((node) => node.id === selectedRelation.targetNodeId)?.displayName}</h2>
            <p className="graph-relation-name">{selectedRelation.relationType.replaceAll('_', ' ')}</p>
            <div className="graph-evidence"><strong>Why connected</strong><p>{redactSensitiveText(selectedRelation.whyConnected)}</p><strong>Provenance</strong><p>{safeReference(selectedRelation.provenance)}</p></div>
          </> : <div className="graph-detail-empty"><GitBranch size={18} /><p>Select a node or relationship to inspect its source messages and provenance.</p></div>}
        </aside>
      </div>}
  </section>;
}

function SynthesisView({ loop, onCopy, onExport }: { loop: AILoopSession; onCopy: () => void; onExport: (format: 'json' | 'md') => void }) {
  const synthesis = loop.synthesis;
  if (!synthesis) return <div className="loop-empty-state">
    <FileText size={20} /><h3>No final synthesis recorded</h3>
    <p>{loop.status === 'Failed' ? 'The failed session has no synthesis record.' : loop.status === 'Cancelled' ? 'The cancelled session has no synthesis record.' : 'A conclusion appears here after the Judge records a synthesis.'}</p>
  </div>;
  return <section className="loop-synthesis-view" aria-labelledby="loop-synthesis-title">
    <header className="loop-subview-heading"><div><p className="loop-eyebrow">RECORDED CONCLUSION</p><h2 id="loop-synthesis-title">Final synthesis</h2><p>This is the stored session result, not proof that a recommendation was executed.</p></div>
      <div className="loop-export-actions"><button className="loop-button loop-button-quiet" onClick={onCopy}><Clipboard size={14} />Copy final prompt</button><button className="loop-button loop-button-quiet" onClick={() => onExport('md')}><FileDown size={14} />Export report</button><button className="loop-button loop-button-quiet" onClick={() => onExport('json')}><FileDown size={14} />Export JSON</button></div>
    </header>
    {loop.isSimulated && <p className="loop-synthesis-simulation">Simulated synthesis record · no agent execution or action completion is claimed.</p>}
    <article className="loop-conclusion-panel"><h3>Consolidated conclusion</h3><p>{redactSensitiveText(synthesis.consolidatedConclusion)}</p></article>
    {synthesis.reviewVerdict && <article className="loop-conclusion-panel role-reviewer"><h3>Unbiased Reviewer verdict · {synthesis.reviewVerdict.replaceAll('_',' ')}</h3>
      {synthesis.reviewerSummary?.length ? <ul>{synthesis.reviewerSummary.map((reason,index)=><li key={`${index}-${reason}`}>{redactSensitiveText(reason)}</li>)}</ul> : <p>No reviewer reasons were recorded.</p>}</article>}
    <div className="loop-synthesis-grid">
      <section className="loop-synthesis-section"><h3>Accepted recommendations</h3>{synthesis.acceptedRecommendations.length
        ? <ol>{synthesis.acceptedRecommendations.map((recommendation) => <li key={recommendation.id}><strong>{redactSensitiveText(recommendation.summary)}</strong><p>{redactSensitiveText(recommendation.supportingEvidence)}</p></li>)}</ol>
        : <p className="loop-empty-copy">No recommendations recorded.</p>}</section>
      <section className="loop-synthesis-section role-red"><h3>Red Team objections and disposition</h3>{synthesis.redTeamDispositions.length
        ? <ul>{synthesis.redTeamDispositions.map((item, index) => <li key={`${index}-${item.objection}`}><strong>{redactSensitiveText(item.objection)}</strong><span className={`loop-disposition disposition-${item.disposition}`}>{item.disposition.replaceAll('_', ' ')}</span><p>{redactSensitiveText(item.resolutionDetails)}</p></li>)}</ul>
        : <p className="loop-empty-copy">No Red Team dispositions recorded.</p>}</section>
      <section className="loop-synthesis-section role-reviewer"><h3>Reviewer findings</h3>{synthesis.reviewerFindings.length
        ? <ul>{synthesis.reviewerFindings.map((item, index) => <li key={`${index}-${item.finding}`}><strong>{redactSensitiveText(item.finding)}</strong><span className="loop-disposition">{item.status.replaceAll('_', ' ')}</span><p>{redactSensitiveText(item.details)}</p></li>)}</ul>
        : <p className="loop-empty-copy">No reviewer findings recorded.</p>}</section>
      <section className="loop-synthesis-section role-judge"><h3>Judge criteria and summary</h3>{synthesis.judgeCriteria.length
        ? <ul>{synthesis.judgeCriteria.map((item, index) => <li key={`${index}-${item.criterion}`}><strong>{redactSensitiveText(item.criterion)}</strong><span className="loop-disposition">{redactSensitiveText(item.weight)}</span><p>{redactSensitiveText(item.assessment)}</p></li>)}</ul>
        : <p className="loop-empty-copy">No decision criteria recorded.</p>}</section>
    </div>
    <section className="loop-open-questions">
      <div><h3>Remaining disagreements</h3>{synthesis.outstandingDisagreements.length ? <ul>{synthesis.outstandingDisagreements.map((item, index) => <li key={`${index}-${item}`}>{redactSensitiveText(item)}</li>)}</ul> : <p>None recorded.</p>}</div>
      <div><h3>Assumptions and uncertainties</h3>{synthesis.assumptionsAndUncertainties.length ? <ul>{synthesis.assumptionsAndUncertainties.map((item, index) => <li key={`${index}-${item}`}>{redactSensitiveText(item)}</li>)}</ul> : <p>None recorded.</p>}</div>
    </section>
    <section className="loop-source-list"><h3>Source references</h3>
      {synthesis.sourceArtifacts.length ? <ul>{synthesis.sourceArtifacts.map((source) => <li key={source.id}><FileText size={14} /><span><strong>{redactSensitiveText(source.title)}</strong><small>{safeReference(source.ref)}</small></span>{safeHttpLink(source.url, 'Open source') || <small>Local or artifact reference</small>}</li>)}</ul>
        : <p className="loop-empty-copy">No source references recorded.</p>}
    </section>
  </section>;
}

function PromptAndArtifactView({ loop }: { loop: AILoopSession }) {
  const artifacts = collectArtifacts(loop);
  return <section className="loop-record-view" aria-labelledby="loop-records-title">
    <header className="loop-subview-heading"><div><p className="loop-eyebrow">PROMPTS &amp; SOURCES</p><h2 id="loop-records-title">Session records</h2><p>Recorded inputs and artifacts for this loop. Sensitive-looking values are redacted in this view.</p></div></header>
    <article className="loop-record-card"><h3>Initial request</h3><p>{redactSensitiveText(loop.objective)}</p><div><span>Session name</span><strong>{redactSensitiveText(loop.name)}</strong></div></article>
    <article className="loop-record-card"><h3>Session constraints</h3>{loop.constraints.length ? <ul>{loop.constraints.map((item, index) => <li key={`${index}-${item}`}>{redactSensitiveText(item)}</li>)}</ul> : <p>No constraints recorded.</p>}</article>
    <article className="loop-record-card"><h3>Desktop operator prompt</h3><p>{loop.desktopContext.configuredPrompt ? redactSensitiveText(loop.desktopContext.configuredPrompt) : 'No desktop operator prompt is recorded for this session.'}</p><small>{loop.isSimulated ? 'Configuration belongs to a simulated session.' : 'Configuration source is not identified.'}</small></article>
    <section className="loop-artifact-list"><div className="loop-subsection-heading"><h3>Gathered information and source records</h3><span>{artifacts.length} records</span></div>
      {artifacts.length ? <ul>{artifacts.map((artifact) => <li key={artifact.id}><header><strong>{artifact.name}</strong><span>{artifact.type}</span></header><p>{artifact.excerpt || 'No excerpt recorded.'}</p><small>{artifact.provenance}</small>{safeHttpLink(artifact.url, 'Open source')}</li>)}</ul>
        : <p className="loop-empty-copy">No gathered information or source artifacts are recorded.</p>}
    </section>
    {loop.synthesis && <article className="loop-record-card"><h3>Final synthesis</h3><p>{redactSensitiveText(loop.synthesis.consolidatedConclusion)}</p></article>}
  </section>;
}

export const AILoopsWorkspace: React.FC = () => {
  const {
    loops, activeLoopId, selectedLoopParticipantRole, setSelectedLoopParticipantRole,
    loopsLoadError, loading, refreshAll, newLoopRequested, clearNewLoopRequest, runLoop, cancelLoop,
  } = useAgent();
  const loop = loops.find((session) => session.id === activeLoopId) || loops[0] || null;
  const [loopView, setLoopView] = useState<LoopViewState>(() => ({
    loopId: activeLoopId,
    tab: 'meeting',
    showCreateForm: false,
    selectedMessageId: null,
  }));
  const sameLoopView = loopView.loopId === activeLoopId;
  const tab = sameLoopView ? loopView.tab : 'meeting';
  const showCreateForm = sameLoopView ? loopView.showCreateForm : false;
  const selectedMessageId = sameLoopView ? loopView.selectedMessageId : null;
  const updateLoopView = (patch: Partial<Omit<LoopViewState, 'loopId'>>) => {
    setLoopView((previous) => ({
      ...(previous.loopId === activeLoopId ? previous : {
        loopId: activeLoopId,
        tab: 'meeting',
        showCreateForm: false,
        selectedMessageId: null,
      }),
      ...patch,
      loopId: activeLoopId,
    }));
  };
  const [feedback, setFeedback] = useState('');
  const [copyError, setCopyError] = useState('');
  const [running, setRunning] = useState(false);
  const selectedRole = selectedLoopParticipantRole || 'blue_team';

  useEffect(() => {
    if (!selectedMessageId || tab !== 'meeting') return;
    const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
    document.getElementById(selectedMessageId)?.scrollIntoView({ block: 'center', behavior });
  }, [selectedMessageId, tab]);

  const showMessage = (id: string) => {
    const message = loop?.messages.find((item) => item.id === id && item.loopId === loop.id);
    if (message) setSelectedLoopParticipantRole(message.role);
    updateLoopView({ tab: 'meeting', selectedMessageId: id });
  };
  const closeCreateForm = () => {
    updateLoopView({ showCreateForm: false });
    clearNewLoopRequest();
  };
  const exportSession = (format: 'json' | 'md') => {
    if (!loop) return;
    setCopyError('');
    try {
      downloadExport(loop, format);
      setFeedback(format === 'md' ? 'Report export started.' : 'Session JSON export started.');
    } catch (error) {
      setCopyError(error instanceof Error ? error.message : 'The session could not be exported.');
    }
  };

  const copyFinalPrompt = async () => {
    if (!loop?.synthesis) return;
    setCopyError('');
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard access is unavailable in this browser context.');
      await navigator.clipboard.writeText(buildFinalPrompt(loop));
      setFeedback('Final prompt copied.');
    } catch (error) {
      setCopyError(error instanceof Error ? error.message : 'The final prompt could not be copied.');
    }
  };
  const executeLoop = async () => {
    if (!loop) return;
    setRunning(true); setCopyError('');
    try { const result = await runLoop(loop.id); setFeedback(`Execution finished with status: ${result.status}.`); }
    catch (error) { setCopyError(error instanceof Error ? error.message : 'Loop execution failed.'); }
    finally { setRunning(false); }
  };
  const stopLoop = async () => {
    if (!loop) return;
    try { const result = await cancelLoop(loop.id); setFeedback(`Cancellation state: ${result.status}.`); }
    catch (error) { setCopyError(error instanceof Error ? error.message : 'Cancellation failed.'); }
  };

  if (loading && !loops.length) return <div className="ai-loops-workspace"><div className="loop-loading" role="status"><span className="loop-loading-bar" /><span className="loop-loading-bar" /><span className="loop-loading-bar" />Loading saved AI Loop sessions…</div></div>;

  return <section className="ai-loops-workspace" aria-labelledby="ai-loops-title">
    <header className="ai-loops-header"><div><p className="loop-eyebrow">LARA IV · LOCAL AI LOOP</p><h1 id="ai-loops-title">AI Loops</h1><p>Inspect persistent local debate sessions and model invocations.</p></div>
      <div>{loop && <>{loop.status === 'Debating' && <button className="loop-button loop-button-quiet" onClick={() => void stopLoop()}>Cancel</button>}<button className="loop-button loop-button-primary" disabled={running || ['Synthesized','Cancelled','Failed','Awaiting User'].includes(loop.status)} onClick={() => void executeLoop()}>{running ? 'Running roles…' : 'Run Loop'}</button></>} <button className="loop-button loop-button-primary" onClick={() => { updateLoopView({ showCreateForm: !showCreateForm }); setFeedback(''); }}><Plus size={15} />New Loop</button></div>
    </header>
    <div className="loop-honesty-banner"><AlertCircle size={15} /><p><strong>Local execution.</strong> Each role appears only after its model invocation is persisted. A failed or review-required run remains visible as such.</p></div>
    {loopsLoadError && <div className="loop-load-error" role="alert"><AlertCircle size={16} /><p>{loopsLoadError}</p><button className="loop-button loop-button-quiet" onClick={() => void refreshAll()}>Retry loading</button></div>}
    {(showCreateForm || newLoopRequested) && <LoopCreationForm onCancel={closeCreateForm} />}
    {feedback && <p className="loop-action-feedback" role="status">{feedback}</p>}
    {!loop && loopsLoadError ? <div className="loop-empty-state loop-first-session">
      <AlertCircle size={22} /><h2>Sessions unavailable</h2><p>Saved sessions could not be loaded. Retry before treating the session list as empty.</p>
      <button className="loop-button loop-button-quiet" onClick={() => void refreshAll()}>Retry loading</button>
    </div> : !loop ? <div className="loop-empty-state loop-first-session">
      <GitBranch size={22} /><h2>No AI Loop sessions</h2><p>Create a persistent session, then run the four local reasoning roles.</p>
      {!showCreateForm && !newLoopRequested && <button className="loop-button loop-button-primary" onClick={() => updateLoopView({ showCreateForm: true })}><Plus size={15} />Create first loop</button>}
    </div> : <>
      <nav className="loop-workspace-tabs" aria-label="Loop views">
        {([
          ['meeting', 'Meeting room'],
          ['graph', 'Knowledge graph'],
          ['synthesis', 'Final synthesis'],
          ['records', 'Prompts & artifacts'],
        ] as Array<[WorkspaceTab, string]>).map(([id, label]) => <button key={id} className={tab === id ? 'is-active' : ''}
          onClick={() => updateLoopView({ tab: id, selectedMessageId: null })} aria-current={tab === id ? 'page' : undefined}>{label}</button>)}
      </nav>
      {tab === 'meeting' && <MeetingRoom loop={loop} selectedRole={selectedRole} selectRole={setSelectedLoopParticipantRole} selectedMessageId={selectedMessageId} showMessage={showMessage} />}
      {tab === 'graph' && <LoopGraph key={loop.id} loop={loop} onShowMessage={showMessage} />}
      {tab === 'synthesis' && <SynthesisView loop={loop} onCopy={() => void copyFinalPrompt()} onExport={exportSession} />}
      {tab === 'records' && <PromptAndArtifactView loop={loop} />}
      {copyError && <p className="loop-inline-error" role="alert"><AlertCircle size={14} />{copyError}</p>}
    </>}
  </section>;
};
