import React, { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { useAgent } from '../context/AgentContext';
import { RoomBadge, StatusBadge } from '../components/common/Badge';

export const ProjectsWorkspace: React.FC = () => {
  const { projects, tasks, openTaskDetail, updateProject, createProject, deleteProject, updateTask } = useAgent();
  const [selectedProjectId, setSelectedProjectId] = useState<string>(projects[0]?.id || '');
  const [error, setError] = useState('');

  const selectedProject = projects.find((p) => p.id === selectedProjectId) || projects[0];

  const projectTasks = tasks.filter((t) => t.project === selectedProject?.id);
  const roomTasks = tasks.filter((t) => t.room === selectedProject?.roomId);

  const handleToggleMilestone = (milestoneId: string) => {
    if (!selectedProject) return;
    const updatedMilestones = selectedProject.milestones.map((m) =>
      m.id === milestoneId
        ? { ...m, completed: !m.completed }
        : m
    );
    void updateProject(selectedProject.id, { milestones: updatedMilestones }).catch(() => setError('Milestone could not be saved.'));
  };

  const handleCreateProject = async () => {
    const name = window.prompt('Project name');
    if (!name?.trim()) return;
    try { const created = await createProject(name.trim()); setSelectedProjectId(created.id); setError(''); }
    catch { setError('Project could not be saved. Check the local backend connection.'); }
  };

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '320px 1fr',
        height: '100%',
        backgroundColor: 'var(--app-canvas)',
        overflow: 'hidden',
      }}
    >
      {/* Left List of Projects */}
      <div
        style={{
          borderRight: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--surface-primary)',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflowY: 'auto',
          padding: '16px',
          gap: '10px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--onyx)' }}>
            Tracked Projects
          </h2>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {projects.length} ACTIVE
          </span>
          <button type="button" className="u-btn u-btn-primary" onClick={() => void handleCreateProject()}>New project</button>
        </div>

        {error && <p role="alert" style={{ color: 'var(--status-error)', fontSize: 13 }}>{error}</p>}
        {!projects.length && <p role="status" style={{ color: 'var(--text-muted)', fontSize: 13 }}>No projects yet. Create one to organize related tasks.</p>}

        {projects.map((proj) => {
          const isSelected = proj.id === selectedProjectId;
          const completedCount = proj.milestones.filter((m) => m.completed).length;
          const progressPercent = Math.round((completedCount / (proj.milestones.length || 1)) * 100);

          return (
            <div
              key={proj.id}
              onClick={() => setSelectedProjectId(proj.id)}
              style={{
                padding: '12px 14px',
                borderRadius: '8px',
                border: isSelected ? '2px solid var(--cerulean)' : '1px solid var(--border-subtle)',
                backgroundColor: isSelected ? 'var(--surface-warm)' : 'var(--surface-subtle)',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                transition: 'border 0.1s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <RoomBadge room={proj.roomId} size="small" />
                <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {progressPercent}%
                </span>
              </div>

              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--onyx)' }}>
                {proj.name}
              </div>

              {/* Progress bar */}
              <div
                style={{
                  height: '4px',
                  backgroundColor: 'var(--border-subtle)',
                  borderRadius: '2px',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${progressPercent}%`,
                    backgroundColor: 'var(--cerulean)',
                    borderRadius: '2px',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Right Project Detail Canvas */}
      {selectedProject ? (
        <div
          style={{
            padding: '24px 32px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          {/* Project Title & Meta */}
          <div
            style={{
              backgroundColor: 'var(--surface-primary)',
              borderRadius: '10px',
              border: '1px solid var(--border-subtle)',
              padding: '20px',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <RoomBadge room={selectedProject.roomId} size="small" />
              <span
                style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                }}
              >
                Updated: {selectedProject.updatedAt.slice(0, 10)}
              </span>
            </div>

            <h1 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--onyx)', marginBottom: '6px' }}>
              {selectedProject.name}
            </h1>

            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              {selectedProject.description}
            </p>
            <button type="button" className="u-btn u-btn-secondary" onClick={() => {
              if (window.confirm(`Delete project “${selectedProject.name}”? Its tasks will remain without a project.`)) {
                void deleteProject(selectedProject.id).then(() => setSelectedProjectId('')).catch(() => setError('Project could not be deleted.'));
              }
            }}>Delete project</button>
          </div>

          {/* Milestones Checklist */}
          <div
            style={{
              backgroundColor: 'var(--surface-primary)',
              borderRadius: '10px',
              border: '1px solid var(--border-subtle)',
              padding: '20px',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <h2 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--onyx)', marginBottom: '12px' }}>
              Milestone Deliverables ({selectedProject.milestones.length})
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {selectedProject.milestones.map((ms) => {
                const isDone = ms.completed;
                return (
                  <div
                    key={ms.id}
                    onClick={() => handleToggleMilestone(ms.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 14px',
                      borderRadius: '6px',
                      backgroundColor: isDone ? 'var(--surface-subtle)' : 'var(--surface-primary)',
                      border: '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <input
                        type="checkbox"
                        checked={isDone}
                        onChange={() => {}}
                        style={{ cursor: 'pointer' }}
                      />
                      <span
                        style={{
                          fontSize: '13px',
                          fontWeight: isDone ? 400 : 600,
                          textDecoration: isDone ? 'line-through' : 'none',
                          color: isDone ? 'var(--text-muted)' : 'var(--onyx)',
                        }}
                      >
                        {ms.title}
                      </span>
                    </div>

                    {ms.dueDate && (
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        Due {ms.dueDate}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Linked Tasks on Kanban */}
          <div
            style={{
              backgroundColor: 'var(--surface-primary)',
              borderRadius: '10px',
              border: '1px solid var(--border-subtle)',
              padding: '20px',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <h2 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--onyx)', marginBottom: '12px' }}>
              Associated Kanban Tasks ({projectTasks.length})
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {roomTasks.map((t) => (
                <div
                  key={t.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--surface-subtle)',
                  }}
                >
                  <button type="button" onClick={() => openTaskDetail(t)} style={{ display: 'flex', alignItems: 'center', gap: '8px', border:0, background:'transparent', cursor:'pointer' }}>
                    <StatusBadge status={t.status} size="small" />
                    <span style={{ fontSize: '12.5px', fontWeight: 500, color: 'var(--onyx)' }}>
                      {t.title}
                    </span>
                    <ArrowRight size={14} color="var(--grey-olive)" />
                  </button>
                  <label className="sr-only" htmlFor={`project-task-${t.id}`}>Project for {t.title}</label>
                  <select id={`project-task-${t.id}`} value={t.project || ''} onChange={(event) => void updateTask(t.id,{project:event.target.value || null}).catch(() => setError('Task project link could not be saved.'))}>
                    <option value="">No project</option>
                    {projects.filter((project) => project.roomId === t.room).map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}
                  </select>
                </div>
              ))}
              {!roomTasks.length && <p style={{ color:'var(--text-muted)',fontSize:13 }}>Create or move a task into this project room to link it here.</p>}
            </div>
          </div>
        </div>
      ) : (
        <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
          No project selected
        </div>
      )}
    </div>
  );
};
