import React, { useState } from 'react';
import {
  X,
  Calendar,
  Folder,
  Trash2,
  Play,
  Pause,
  StopCircle,
  Share2,
} from 'lucide-react';

import { useAgent } from '../../context/AgentContext';
import { TaskStatus, TaskPriority, KnowledgeRoom } from '../../types';
import { PriorityBadge, RoomBadge, StatusBadge } from '../common/Badge';

export const ContextDrawer: React.FC = () => {
  const {
    activeDrawerType,
    closeAllDrawers,
    selectedTask,
    updateTask,
    transitionTask,
    deleteTask,
    createReminder,
    selectedGraphNode,
    graphEdges,
    graphNodes,
    openNodeDetail,
    selectedJob,
    pauseJob,
    resumeJob,
    cancelJob,
    selectedApproval,
    decideApproval,
  } = useAgent();

  // Task local editing state
  const [newReminderTime, setNewReminderTime] = useState('');
  const [isAddingReminder, setIsAddingReminder] = useState(false);

  if (activeDrawerType === 'none') return null;

  const handleStatusChange = (status: TaskStatus) => {
    if (selectedTask) {
      transitionTask(selectedTask.id, status);
    }
  };

  const handlePriorityChange = (priority: TaskPriority) => {
    if (selectedTask) {
      updateTask(selectedTask.id, { priority });
    }
  };

  const requestApprovalDecision = (decision: 'approve' | 'reject') => {
    if (!selectedApproval) return;
    const verb = decision === 'approve' ? 'simulate approval for' : 'simulate rejection of';
    if (window.confirm(`${verb} “${selectedApproval.plainLanguageAction}” targeting ${selectedApproval.targetResource}? No external action will run.`)) {
      void decideApproval(selectedApproval.id, decision);
    }
  };

  const handleRoomChange = (room: KnowledgeRoom) => {
    if (selectedTask) {
      updateTask(selectedTask.id, { room });
    }
  };

  const handleCreateReminder = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask || !newReminderTime) return;

    createReminder(selectedTask.id, `Reminder for: ${selectedTask.title}`, newReminderTime);
    setNewReminderTime('');
    setIsAddingReminder(false);
  };

  return (
    <aside
      style={{
        width: '420px',
        backgroundColor: 'var(--surface-primary)',
        borderLeft: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        boxShadow: 'var(--shadow-md)',
        zIndex: 15,
        flexShrink: 0,
        overflow: 'hidden',
      }}
      aria-label="Context Inspection Drawer"
    >
      {/* Drawer Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 18px',
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--surface-subtle)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              textTransform: 'uppercase',
              color: 'var(--text-muted)',
              fontWeight: 600,
            }}
          >
            {activeDrawerType === 'task' && 'Task Details'}
            {activeDrawerType === 'node' && 'Knowledge Node Detail'}
            {activeDrawerType === 'job' && 'Agent Job Telemetry'}
            {activeDrawerType === 'approval' && 'Approval Gate'}
          </span>
        </div>

        <button
          onClick={closeAllDrawers}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '4px',
            borderRadius: '4px',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
          }}
          title="Close drawer (Escape)"
        >
          <X size={16} />
        </button>
      </div>

      {/* Drawer Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '18px' }}>
        {/* TASK INSPECTION */}
        {activeDrawerType === 'task' && selectedTask && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            {/* Title & Status */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <StatusBadge status={selectedTask.status} size="small" />
                <PriorityBadge priority={selectedTask.priority} size="small" />
                <RoomBadge room={selectedTask.room} size="small" />
              </div>

              <input
                type="text"
                value={selectedTask.title}
                onChange={(e) => updateTask(selectedTask.id, { title: e.target.value })}
                style={{
                  width: '100%',
                  fontSize: '16px',
                  fontWeight: 700,
                  color: 'var(--onyx)',
                  border: '1px solid transparent',
                  borderRadius: '4px',
                  padding: '4px 0',
                  outline: 'none',
                }}
              />
            </div>

            {/* Description / Notes */}
            <div>
              <label
                style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  display: 'block',
                  marginBottom: '4px',
                }}
              >
                Notes & Context
              </label>
              <textarea
                value={selectedTask.description || ''}
                onChange={(e) => updateTask(selectedTask.id, { description: e.target.value })}
                placeholder="Add task notes, relevant context, or links..."
                rows={3}
                style={{
                  width: '100%',
                  padding: '8px',
                  fontSize: '13px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--surface-subtle)',
                  resize: 'vertical',
                  outline: 'none',
                }}
              />
            </div>

            {/* Status & Priority Controls */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
                padding: '12px',
                backgroundColor: 'var(--surface-subtle)',
                borderRadius: '8px',
              }}
            >
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Status Lane
                </label>
                <select
                  value={selectedTask.status}
                  onChange={(e) => handleStatusChange(e.target.value as TaskStatus)}
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--surface-primary)',
                    fontSize: '12px',
                  }}
                >
                  <option value="inbox">Inbox</option>
                  <option value="next">Next</option>
                  <option value="in_progress">In Progress</option>
                  <option value="waiting">Waiting</option>
                  <option value="review">Review</option>
                  <option value="ready_to_submit">Ready to Submit</option>
                  <option value="done">Done</option>
                  <option value="archived">Archived</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Priority
                </label>
                <select
                  value={selectedTask.priority}
                  onChange={(e) => handlePriorityChange(e.target.value as TaskPriority)}
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--surface-primary)',
                    fontSize: '12px',
                  }}
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>

            {/* Metadata Fields: Due Date, Room, Course */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Calendar size={14} /> Due Date
                </span>
                <input
                  type="date"
                  value={selectedTask.dueDate || ''}
                  onChange={(e) => updateTask(selectedTask.id, { dueDate: e.target.value || undefined })}
                  style={{
                    padding: '3px 6px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '12px',
                  }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Folder size={14} /> Room
                </span>
                <select
                  value={selectedTask.room}
                  onChange={(e) => handleRoomChange(e.target.value as KnowledgeRoom)}
                  style={{
                    padding: '3px 6px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '12px',
                  }}
                >
                  <option value="academic">Academic</option>
                  <option value="projects">Projects</option>
                  <option value="opportunities">Opportunities</option>
                  <option value="operations">Operations</option>
                  <option value="public_research">Public Research</option>
                  <option value="personal_vault">Personal Vault</option>
                  <option value="health">Health</option>
                </select>
              </div>

              {selectedTask.course && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Folder size={14} /> Course
                  </span>
                  <span style={{ fontWeight: 500, color: 'var(--onyx)' }}>{selectedTask.course}</span>
                </div>
              )}
            </div>

            {/* Scheduled Reminders */}
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '6px',
                }}
              >
                <label
                  style={{
                    fontSize: '11px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-muted)',
                    textTransform: 'uppercase',
                  }}
                >
                  Reminders ({selectedTask.remindersCount || 0})
                </label>
                <button
                  onClick={() => setIsAddingReminder(!isAddingReminder)}
                  style={{
                    fontSize: '11px',
                    color: 'var(--cerulean)',
                    fontWeight: 600,
                  }}
                >
                  + Add Alert
                </button>
              </div>

              {isAddingReminder && (
                <form
                  onSubmit={handleCreateReminder}
                  style={{
                    display: 'flex',
                    gap: '6px',
                    padding: '8px',
                    backgroundColor: 'var(--surface-warm)',
                    borderRadius: '6px',
                    marginBottom: '8px',
                  }}
                >
                  <input
                    type="datetime-local"
                    value={newReminderTime}
                    onChange={(e) => setNewReminderTime(e.target.value)}
                    required
                    style={{
                      flex: 1,
                      fontSize: '11px',
                      padding: '4px',
                      borderRadius: '4px',
                      border: '1px solid var(--border-subtle)',
                    }}
                  />
                  <button
                    type="submit"
                    style={{
                      padding: '4px 8px',
                      backgroundColor: 'var(--cerulean)',
                      color: '#ffffff',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                    }}
                  >
                    Schedule
                  </button>
                </form>
              )}
            </div>

            {/* Delete Task Button */}
            <div style={{ marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
              <button
                onClick={() => deleteTask(selectedTask.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: 'var(--status-danger)',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  padding: '6px 8px',
                  borderRadius: '4px',
                  backgroundColor: 'var(--status-danger-bg)',
                  width: '100%',
                  justifyContent: 'center',
                }}
              >
                <Trash2 size={14} />
                <span>Delete Task</span>
              </button>
            </div>
          </div>
        )}

        {/* KNOWLEDGE NODE INSPECTION */}
        {activeDrawerType === 'node' && selectedGraphNode && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <RoomBadge room={selectedGraphNode.roomId} size="small" />
                <span
                  style={{
                    fontSize: '10px',
                    fontFamily: 'var(--font-mono)',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    backgroundColor: 'var(--surface-subtle)',
                    color: 'var(--text-muted)',
                  }}
                >
                  {selectedGraphNode.nodeType}
                </span>
              </div>
              <h2 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--onyx)' }}>
                {selectedGraphNode.displayName}
              </h2>
            </div>

            {/* Provenance Summary */}
            <div
              style={{
                padding: '12px',
                backgroundColor: 'var(--surface-warm)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--text-secondary)',
                  textTransform: 'uppercase',
                  marginBottom: '6px',
                }}
              >
                <Share2 size={13} color="var(--cerulean)" />
                Provenance Reference
              </div>
              <p style={{ fontSize: '12.5px', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                Source: <code style={{ fontFamily: 'var(--font-mono)' }}>{selectedGraphNode.sourceRef}</code>
              </p>
            </div>

            {/* Connected Relationships */}
            <div>
              <div
                style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  marginBottom: '8px',
                }}
              >
                Connected Relationships
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {graphEdges
                  .filter((e) => e.sourceNodeId === selectedGraphNode.id || e.targetNodeId === selectedGraphNode.id)
                  .map((edge) => {
                    const otherNodeId = edge.sourceNodeId === selectedGraphNode.id ? edge.targetNodeId : edge.sourceNodeId;
                    const otherNode = graphNodes.find((n) => n.id === otherNodeId);
                    return (
                      <div
                        key={edge.id}
                        onClick={() => otherNode && openNodeDetail(otherNode)}
                        style={{
                          padding: '8px 10px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-subtle)',
                          backgroundColor: 'var(--surface-subtle)',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--onyx)' }}>
                            {otherNode?.displayName || otherNodeId}
                          </span>
                          <span
                            style={{
                              fontSize: '10px',
                              fontFamily: 'var(--font-mono)',
                              color: 'var(--cerulean)',
                            }}
                          >
                            {edge.relationType}
                          </span>
                        </div>
                        {edge.whyConnected && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                            {edge.whyConnected}
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>
        )}

        {/* AGENT JOB INSPECTION */}
        {activeDrawerType === 'job' && selectedJob && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    padding: '2px 8px',
                    borderRadius: '4px',
                    backgroundColor:
                      selectedJob.status === 'executing'
                        ? 'rgba(0, 117, 162, 0.15)'
                        : selectedJob.status === 'paused'
                        ? 'var(--status-warning-bg)'
                        : 'var(--status-success-bg)',
                    color:
                      selectedJob.status === 'executing'
                        ? 'var(--cerulean)'
                        : selectedJob.status === 'paused'
                        ? 'var(--status-warning)'
                        : 'var(--status-success)',
                  }}
                >
                  {selectedJob.status.toUpperCase()}
                </span>
                <RoomBadge room={selectedJob.room} size="small" />
              </div>
              <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--onyx)' }}>
                {selectedJob.goal}
              </h2>
            </div>

            {/* Lifecycle Tracker */}
            <div
              style={{
                padding: '12px',
                backgroundColor: 'var(--surface-subtle)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div
                style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  marginBottom: '8px',
                }}
              >
                Current Stage
              </div>
              <div style={{ fontWeight: 600, color: 'var(--cerulean)', fontSize: '13px' }}>
                {selectedJob.currentStage}
              </div>
            </div>

            {/* Controls */}
            <div style={{ display: 'flex', gap: '8px' }}>
              {selectedJob.status === 'executing' && (
                <button
                  onClick={() => pauseJob(selectedJob.id)}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '8px',
                    backgroundColor: 'var(--status-warning-bg)',
                    color: 'var(--status-warning)',
                    borderRadius: '6px',
                    fontWeight: 600,
                    fontSize: '12px',
                  }}
                >
                  <Pause size={14} /> Pause Run
                </button>
              )}

              {selectedJob.status === 'paused' && (
                <button
                  onClick={() => resumeJob(selectedJob.id)}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '8px',
                    backgroundColor: 'var(--status-info-bg)',
                    color: 'var(--cerulean)',
                    borderRadius: '6px',
                    fontWeight: 600,
                    fontSize: '12px',
                  }}
                >
                  <Play size={14} /> Resume Run
                </button>
              )}

              <button
                onClick={() => cancelJob(selectedJob.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 12px',
                  backgroundColor: 'var(--status-danger-bg)',
                  color: 'var(--status-danger)',
                  borderRadius: '6px',
                  fontWeight: 600,
                  fontSize: '12px',
                }}
              >
                <StopCircle size={14} /> Cancel
              </button>
            </div>

            {/* Tool Calls Log */}
            {selectedJob.toolTraces && (
              <div>
                <div
                  style={{
                    fontSize: '11px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-muted)',
                    textTransform: 'uppercase',
                    marginBottom: '6px',
                  }}
                >
                  Bounded Tool Executions
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {selectedJob.toolTraces.map((tc) => (
                    <div
                      key={tc.id}
                      style={{
                        padding: '8px',
                        backgroundColor: 'var(--surface-subtle)',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '11px',
                      }}
                    >
                      <div style={{ fontWeight: 600, color: 'var(--cerulean)' }}>{tc.tool}</div>
                      <div style={{ color: 'var(--text-muted)', marginTop: '2px' }}>
                        {tc.summary}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* APPROVAL REQUEST INSPECTION */}
        {activeDrawerType === 'approval' && selectedApproval && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    padding: '2px 6px',
                    borderRadius: '4px',
                    backgroundColor: 'var(--status-danger-bg)',
                    color: 'var(--status-danger)',
                  }}
                >
                  HIGH-RISK GATE
                </span>
                <RoomBadge room={selectedApproval.sourceRoom} size="small" />
              </div>
              <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--onyx)' }}>
                {selectedApproval.plainLanguageAction}
              </h2>
            </div>

            {/* Target and Policy Rule */}
            <div
              style={{
                padding: '12px',
                backgroundColor: 'var(--surface-subtle)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
                fontSize: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Target Resource: </span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {selectedApproval.targetResource}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Policy Gate: </span>
                <span style={{ fontWeight: 600 }}>{selectedApproval.policyBasis}</span>
              </div>
            </div>

            {/* Normalized Arguments Inspection */}
            <div>
              <label
                style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  display: 'block',
                  marginBottom: '4px',
                }}
              >
                Exact Normalized Payload
              </label>
              <pre
                style={{
                  padding: '10px',
                  backgroundColor: 'var(--onyx)',
                  color: 'var(--beige)',
                  borderRadius: '6px',
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  overflowX: 'auto',
                }}
              >
                {JSON.stringify(selectedApproval.normalizedArguments, null, 2)}
              </pre>
            </div>

            {/* Decision Controls */}
            {selectedApproval.status === 'pending' ? (
              <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                <button
                  onClick={() => requestApprovalDecision('approve')}
                  style={{
                    flex: 1,
                    padding: '8px',
                    backgroundColor: 'var(--status-success)',
                    color: '#ffffff',
                    borderRadius: '6px',
                    fontWeight: 600,
                    fontSize: '12px',
                    cursor: 'pointer',
                  }}
                >
                  {selectedApproval.specificButtonLabel || 'Approve Action'}
                </button>
                <button
                  onClick={() => requestApprovalDecision('reject')}
                  style={{
                    flex: 1,
                    padding: '8px',
                    backgroundColor: 'var(--status-danger)',
                    color: '#ffffff',
                    borderRadius: '6px',
                    fontWeight: 600,
                    fontSize: '12px',
                    cursor: 'pointer',
                  }}
                >
                  Reject & Abort
                </button>
              </div>
            ) : (
              <div
                style={{
                  padding: '10px',
                  borderRadius: '6px',
                  textAlign: 'center',
                  fontWeight: 600,
                  fontSize: '12px',
                  backgroundColor:
                    selectedApproval.status === 'approved'
                      ? 'var(--status-success-bg)'
                      : 'var(--status-danger-bg)',
                  color:
                    selectedApproval.status === 'approved'
                      ? 'var(--status-success)'
                      : 'var(--status-danger)',
                }}
              >
                Decision: {selectedApproval.status.toUpperCase()}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
