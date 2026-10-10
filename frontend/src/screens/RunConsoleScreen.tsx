import React from 'react';
import { ArrowLeft, ArrowUpRight, CircleAlert, CircleCheck, Clock3, LockKeyhole, Play, TerminalSquare } from 'lucide-react';
import { useAgent } from '../context/AgentContext';
import { AgentJob, ApprovalRequest, Task, ToolTrace } from '../types';

const flow = ['queued', 'planning', 'awaiting_approval', 'running', 'completed'] as const;

function canonicalStatus(status: AgentJob['status']) {
  if (status === 'researching' || status === 'reviewing' || status === 'executing' || status === 'verifying' || status === 'paused') return 'running';
  if (status === 'blocked') return 'awaiting_approval';
  return status;
}

function statusLabel(status: string) {
  return status.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function recordedStepLabel(trace: ToolTrace) {
  if (trace.status === 'completed' || trace.status === 'verified') return 'Recorded complete';
  if (trace.status === 'blocked') return 'Recorded blocked';
  return 'Recorded in progress';
}

const ApprovalPreview: React.FC<{ approval: ApprovalRequest; onReview: () => void }> = ({ approval, onReview }) => (
  <section className="run-panel run-approval-panel" aria-labelledby="run-approval-title">
    <div className="run-panel-heading"><div><LockKeyhole size={16} /><h3 id="run-approval-title">Approval needed</h3></div><span className="run-status-pill status-warn">Pending</span></div>
    <p className="run-approval-action">{approval.plainLanguageAction}</p>
    <dl className="run-approval-facts">
      <div><dt>Target</dt><dd>{approval.targetResource}</dd></div>
      <div><dt>Source room</dt><dd>{statusLabel(approval.sourceRoom)}</dd></div>
      <div><dt>Destination</dt><dd>{approval.destination}</dd></div>
      <div><dt>Risk</dt><dd>{statusLabel(approval.riskTier)}</dd></div>
      <div><dt>Leaves this device</dt><dd>{approval.leavesMachine ? 'Yes' : 'No'}</dd></div>
      <div><dt>Reversibility</dt><dd>{approval.reversibility}</dd></div>
      <div><dt>Expires</dt><dd><time dateTime={approval.expiresAt}>{new Date(approval.expiresAt).toLocaleString()}</time></dd></div>
      <div><dt>Policy basis</dt><dd>{approval.policyBasis}</dd></div>
    </dl>
    <div><h4 className="run-subheading">Exact proposed arguments</h4>
      <pre className="run-arguments">{JSON.stringify(approval.normalizedArguments, null, 2)}</pre></div>
    <p className="run-local-note">This is a browser-local approval record. Reviewing or deciding it here does not execute an external action.</p>
    <button className="u-btn u-btn-secondary run-review-button" type="button" onClick={onReview}>Review approval <ArrowUpRight size={14} /></button>
  </section>
);

const TraceList: React.FC<{ traces: ToolTrace[] }> = ({ traces }) => {
  const complete = traces.filter((trace) => trace.status === 'completed' || trace.status === 'verified').length;
  return <section className="run-panel" aria-labelledby="run-traces-title">
    <div className="run-panel-heading"><div><TerminalSquare size={16} /><h3 id="run-traces-title">Recorded steps</h3></div>
      <span className="run-step-count">{complete} of {traces.length} marked complete</span></div>
    {traces.length === 0 ? <p className="run-empty-inline">No step records are attached to this sample.</p>
      : <ol className="run-trace-list">{traces.map((trace) => <li key={trace.id}>
        <span className={`run-trace-marker trace-${trace.status}`} aria-hidden="true">{trace.status === 'completed' || trace.status === 'verified' ? <CircleCheck size={16} /> : trace.status === 'blocked' ? <CircleAlert size={16} /> : <Clock3 size={16} />}</span>
        <div className="run-trace-copy"><div><strong>{trace.tool}</strong><span>{recordedStepLabel(trace)}</span></div>
          <p>{trace.summary}</p>
          {trace.outputExcerpt && <details><summary>Show recorded excerpt</summary><pre>{trace.outputExcerpt}</pre></details>}
          <time dateTime={trace.timestamp}>{new Date(trace.timestamp).toLocaleString()}</time>
        </div>
      </li>)}</ol>}
    <p className="run-local-note">These sample records are not live tool calls, execution logs, or verified output.</p>
  </section>;
};

const JobDetail: React.FC<{ job: AgentJob; approval?: ApprovalRequest; onReviewApproval: () => void; relatedTasks: Task[]; onBack: () => void; onOpenTask: (task: Task) => void; onOpenTaskList: () => void }> = ({ job, approval, onReviewApproval, relatedTasks, onBack, onOpenTask, onOpenTaskList }) => {
  const current = canonicalStatus(job.status);
  const isTerminal = ['completed', 'failed', 'cancelled'].includes(job.status);
  const stepsComplete = job.toolTraces.filter((trace) => trace.status === 'completed' || trace.status === 'verified').length;
  const hasTraces = job.toolTraces.length > 0;

  return <div className="run-detail">
    <header className="run-detail-header">
      <button className="run-back-button" type="button" onClick={onBack} aria-label="Return to conversation"><ArrowLeft size={15} />Back to conversation</button>
      <div><p className="run-overline">SAMPLE RUN RECORD</p><h2>{job.goal}</h2></div>
      <span className={`run-status-pill status-${job.status === 'completed' ? 'ok' : ['failed', 'blocked'].includes(job.status) ? 'warn' : 'neutral'}`}>{statusLabel(job.status)}</span>
    </header>
    <div className="run-boundary-banner" role="note"><CircleAlert size={17} /><p><strong>Browser demo record — not a live run.</strong> Its state, route, and trace rows are sample data. No model, job service, or external tool executed.</p></div>

    <section className="run-panel" aria-labelledby="run-lifecycle-title">
      <div className="run-panel-heading"><div><Play size={16} /><h3 id="run-lifecycle-title">Lifecycle</h3></div><span className="run-no-provider">No provider connected</span></div>
      <ol className="run-lifecycle">{flow.map((step, index) => {
        const currentIndex = flow.indexOf(current as typeof flow[number]);
        const done = isTerminal ? job.status === 'completed' && index < flow.length : currentIndex > index;
        const active = current === step && !isTerminal;
        return <li key={step} className={`${done ? 'is-done' : ''}${active ? ' is-current' : ''}`} aria-current={active ? 'step' : undefined}>
          <span>{done ? <CircleCheck size={16} /> : index + 1}</span><small>{statusLabel(step)}</small>
        </li>;
      })}</ol>
      <div className="run-progress-copy"><span>{hasTraces ? `${stepsComplete} of ${job.toolTraces.length} sample steps marked complete` : 'No step progress is available'}</span><span>{job.currentStage}</span></div>
      {hasTraces && <progress className="run-progress" value={stepsComplete} max={job.toolTraces.length} aria-label={`${stepsComplete} of ${job.toolTraces.length} sample steps marked complete`} />}
      <dl className="run-meta-grid">
        <div><dt>Sample route</dt><dd>{job.route} · not connected</dd></div>
        <div><dt>Started</dt><dd><time dateTime={job.startedAt}>{new Date(job.startedAt).toLocaleString()}</time></dd></div>
        <div><dt>Scope</dt><dd>{job.scope}</dd></div>
        <div><dt>Room</dt><dd>{statusLabel(job.room)}</dd></div>
      </dl>
      <p className="run-local-note">Pause, resume, cancel, and retry are unavailable until a real runtime service is configured.</p>
      {['failed', 'blocked'].includes(job.status) && <p className="run-recovery-note" role="status">Recovery is not started. Review the recorded state and configure a runtime before retrying.</p>}
    </section>

    {approval && <ApprovalPreview approval={approval} onReview={onReviewApproval} />}
    {job.executiveSummary && <section className="run-panel"><div className="run-panel-heading"><h3>Recorded summary</h3></div><p className="run-summary">{job.executiveSummary}</p></section>}
    {job.uncertainties?.length ? <section className="run-panel"><div className="run-panel-heading"><h3>Recorded uncertainties</h3></div><ul className="run-uncertainties">{job.uncertainties.map((item, index) => <li key={index}>{item}</li>)}</ul></section> : null}
    <TraceList traces={job.toolTraces} />
    <section className="run-panel">
      <div className="run-panel-heading"><h3>Related tasks</h3></div>
      {relatedTasks.length ? <ul className="run-related-tasks">{relatedTasks.map((task) => <li key={task.id}><button type="button" onClick={() => onOpenTask(task)}>{task.title}</button><span>{statusLabel(task.status)}</span></li>)}
        </ul> : <div><p className="run-empty-inline">No task links are stored for this run record.</p><button className="run-back-button" type="button" onClick={onOpenTaskList}>Open task board <ArrowUpRight size={14} /></button></div>}
    </section>
  </div>;
};

export const RunConsoleScreen: React.FC = () => {
  const { jobs, selectedJob, setSelectedJob, approvals, tasks, runConsolePreviewGoal, clearRunPreview, setActiveScreen, openApprovalDetail, openTaskDetail } = useAgent();
  const jobApproval = selectedJob?.pendingApprovalId ? approvals.find((item) => item.id === selectedJob.pendingApprovalId) : undefined;
  const relatedTasks = selectedJob ? tasks.filter((task) => selectedJob.evidence.includes(task.id)) : [];

  const reviewApproval = () => {
    if (!jobApproval) return;
    openApprovalDetail(jobApproval);
    setActiveScreen('approvals');
  };
  const returnToConversation = () => {
    setSelectedJob(null);
    clearRunPreview();
    setActiveScreen('workbench');
  };
  const openTask = (task: Task) => {
    setActiveScreen('kanban');
    openTaskDetail(task);
  };
  const openTaskList = () => {
    setSelectedJob(null);
    setActiveScreen('kanban');
  };

  return <div className="run-console-workspace u-workspace-scroll">
    <div className="run-console-heading"><div><p className="run-overline">OPERATIONS / TRACE</p><h1>Run console</h1><p>Inspect sample records or review a proposed run. Nothing here starts execution.</p></div>
      {runConsolePreviewGoal && <button className="u-btn u-btn-secondary" onClick={() => { clearRunPreview(); setActiveScreen('workbench'); }}>Back to conversation <ArrowUpRight size={14} /></button>}
    </div>
    {runConsolePreviewGoal && !selectedJob && <section className="run-preview-card" aria-labelledby="run-preview-title">
      <div className="run-panel-heading"><div><Play size={16} /><h2 id="run-preview-title">Proposed run preview</h2></div><span className="run-status-pill status-neutral">Preview only</span></div>
      <p className="run-preview-goal">{runConsolePreviewGoal}</p>
      <div className="run-boundary-banner" role="note"><CircleAlert size={17} /><p><strong>No run has started.</strong> This browser demo has no connected model provider or job service. Your prompt is shown here for review only.</p></div>
      <dl className="run-meta-grid"><div><dt>Provider</dt><dd>Not configured</dd></div><div><dt>Execution</dt><dd>Unavailable</dd></div><div><dt>Approval policy</dt><dd>Not evaluated by a backend</dd></div></dl>
      <p className="run-local-note">To execute this request, configure a trusted job service, provider, policy checks, and a durable event stream.</p>
      <button className="run-back-button" type="button" onClick={() => { clearRunPreview(); setActiveScreen('workbench'); }}><ArrowLeft size={15} />Return to conversation</button>
    </section>}
    {selectedJob ? <JobDetail job={selectedJob} approval={jobApproval} onReviewApproval={reviewApproval} relatedTasks={relatedTasks} onBack={returnToConversation} onOpenTask={openTask} onOpenTaskList={openTaskList} />
      : <section className="run-records-section" aria-labelledby="run-records-title">
        <div className="run-records-header"><div><h2 id="run-records-title">Sample run records</h2><p>Browser-local fixtures; they do not represent live activity.</p></div><span>{jobs.length} records</span></div>
        {jobs.length === 0 ? <p className="run-empty-inline">No sample run records are available.</p>
          : <ul className="run-record-list">{jobs.map((job) => <li key={job.id}><button type="button" className="run-record-card" onClick={() => { clearRunPreview(); setSelectedJob(job); }}>
            <div className="run-record-card-top"><span className={`run-status-pill status-${job.status === 'completed' ? 'ok' : ['failed', 'blocked'].includes(job.status) ? 'warn' : 'neutral'}`}>{statusLabel(job.status)}</span><time dateTime={job.startedAt}>{new Date(job.startedAt).toLocaleDateString()}</time></div>
            <strong>{job.goal}</strong><span>{job.toolTraces.length} recorded steps · sample only</span>
          </button></li>)}</ul>}
      </section>}
  </div>;
};
