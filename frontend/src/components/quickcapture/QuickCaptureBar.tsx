import React, { useState } from 'react';
import { Sparkles, Calendar, BookOpen, FileText, Check, AlertCircle } from 'lucide-react';
import { useAgent } from '../../context/AgentContext';
import { TaskCaptureCandidate } from '../../api/types';
import { TaskCategory, KnowledgeRoom } from '../../types';

interface QuickCaptureModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const QuickCaptureModal: React.FC<QuickCaptureModalProps> = ({ isOpen, onClose }) => {
  const { captureTask, createTask } = useAgent();

  const [inputVal, setInputVal] = useState('');
  const [candidate, setCandidate] = useState<TaskCaptureCandidate | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  // Form override fields
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<TaskCategory>('Academics');
  const [room, setRoom] = useState<KnowledgeRoom>('academic');
  const [dueDate, setDueDate] = useState('');
  const [course, setCourse] = useState('');
  const [isSticky, setIsSticky] = useState(false);

  if (!isOpen) return null;

  const handleParse = async () => {
    if (!inputVal.trim()) return;
    setIsParsing(true);
    try {
      const result = await captureTask(inputVal);
      setCandidate(result);
      setTitle(result.suggestedTitle);
      if (result.suggestedCategory) {
        setCategory(result.suggestedCategory as TaskCategory);
        if (result.suggestedCategory === 'Academics') setRoom('academic');
        else if (result.suggestedCategory === 'Projects') setRoom('projects');
        else if (result.suggestedCategory === 'Opportunities') setRoom('opportunities');
        else if (result.suggestedCategory === 'AI/ML') setRoom('public_research');
      }
      if (result.suggestedDueDate) setDueDate(result.suggestedDueDate);
      if (result.suggestedCourse) setCourse(result.suggestedCourse);
    } catch (err) {
      console.error(err);
    } finally {
      setIsParsing(false);
    }
  };

  const handleSave = async () => {
    if (!title.trim() || isSaving) return;
    setIsSaving(true);
    setSaveError('');
    try {
      await createTask({
        title,
        description: inputVal,
        category,
        room,
        priority: 'high',
        dueDate: dueDate || undefined,
        course: course || undefined,
        isSticky,
        stickyColor: isSticky ? 'beige' : undefined,
        nextAction: 'Review captured task and schedule initial work session.',
      });
      setInputVal('');
      setCandidate(null);
      onClose();
    } catch (error) {
      setSaveError(error instanceof Error ? `Task was not saved: ${error.message}` : 'Task was not saved. Try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(18, 22, 25, 0.65)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 110,
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '640px',
          maxWidth: '95vw',
          backgroundColor: 'var(--surface-primary)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border-subtle)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '16px 24px',
            backgroundColor: 'var(--surface-dark)',
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={16} color="var(--cerulean)" />
            <span style={{ fontWeight: 650, fontSize: '15px' }}>
              Natural-Language Quick Capture
            </span>
          </div>
          <span
            style={{
              fontSize: '11px',
              color: 'var(--silver)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            Ollama · Gemma Parser
          </span>
        </div>

        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label
              style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: '6px',
              }}
            >
              Enter outcome, assignment, or note (e.g. &ldquo;Algorithms problem set due on 14 Oct...&rdquo;)
            </label>
            <textarea
              rows={3}
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="e.g. Algorithms Assignment 3 is due on 14 October at 23:59. Attach assignment3_solutions.pdf and remind me 2 days before."
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--surface-subtle)',
                fontSize: '13.5px',
                lineHeight: 1.4,
                color: 'var(--onyx)',
                resize: 'none',
              }}
              autoFocus
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
            <button
              onClick={handleParse}
              disabled={isParsing || !inputVal.trim()}
              className="u-btn u-btn-secondary"
              style={{ fontSize: '12.5px' }}
            >
              <Sparkles size={14} color="var(--accent)" />
              {isParsing ? 'Analyzing candidate...' : 'Extract Fields & Validate'}
            </button>
          </div>

          {/* Candidate Parsing Result */}
          {candidate && (
            <div
              style={{
                padding: '16px',
                backgroundColor: 'var(--surface-warm)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid rgba(18, 22, 25, 0.12)',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid rgba(18, 22, 25, 0.10)',
                  paddingBottom: '8px',
                }}
              >
                <span
                  style={{
                    fontSize: '12px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    color: 'var(--onyx)',
                  }}
                >
                  Candidate Proposal
                </span>
                <span
                  style={{
                    fontSize: '11px',
                    color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  Deterministic Validation Ready
                </span>
              </div>

              {/* Clarification questions if any */}
              {candidate.clarificationQuestions.length > 0 && (
                <div
                  style={{
                    padding: '8px 12px',
                    backgroundColor: 'rgba(153, 98, 0, 0.12)',
                    borderRadius: 'var(--radius-xs)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '12px',
                    color: 'var(--status-warning)',
                  }}
                >
                  <AlertCircle size={15} />
                  <span>{candidate.clarificationQuestions[0]}</span>
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Title
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 'var(--radius-xs)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: '#FFFFFF',
                      fontSize: '12.5px',
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => {
                      const newCat = e.target.value as TaskCategory;
                      setCategory(newCat);
                      if (newCat === 'Academics') setRoom('academic');
                      else if (newCat === 'Projects') setRoom('projects');
                      else if (newCat === 'Opportunities') setRoom('opportunities');
                      else if (newCat === 'AI/ML') setRoom('public_research');
                    }}
                    style={{
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 'var(--radius-xs)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: '#FFFFFF',
                      fontSize: '12.5px',
                    }}
                  >
                    <option value="Academics">Academics</option>
                    <option value="Projects">Projects</option>
                    <option value="Hackathons">Hackathons</option>
                    <option value="AI/ML">AI/ML</option>
                    <option value="Robotics">Robotics</option>
                    <option value="Quantum">Quantum</option>
                    <option value="Opportunities">Opportunities</option>
                    <option value="Personal/Admin">Personal/Admin</option>
                  </select>
                </div>

                <div>
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                      color: 'var(--text-secondary)',
                    }}
                  >
                    <Calendar size={12} />
                    Due Date
                  </label>
                  <input
                    type="date"
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 'var(--radius-xs)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: '#FFFFFF',
                      fontSize: '12.5px',
                    }}
                  />
                </div>

                <div>
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                      color: 'var(--text-secondary)',
                    }}
                  >
                    <BookOpen size={12} />
                    Course / Project
                  </label>
                  <input
                    type="text"
                    value={course}
                    onChange={(e) => setCourse(e.target.value)}
                    placeholder="e.g. CS401 Algorithms"
                    style={{
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 'var(--radius-xs)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: '#FFFFFF',
                      fontSize: '12.5px',
                    }}
                  />
                </div>
              </div>

              {candidate.suggestedFile && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '12px',
                    color: 'var(--text-secondary)',
                    backgroundColor: 'rgba(255, 255, 255, 0.7)',
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-xs)',
                  }}
                >
                  <FileText size={14} color="var(--accent)" />
                  <span>Detected File: <strong>{candidate.suggestedFile}</strong> (Linked to {room} room)</span>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                <input
                  type="checkbox"
                  id="sticky-check"
                  checked={isSticky}
                  onChange={(e) => setIsSticky(e.target.checked)}
                />
                <label
                  htmlFor="sticky-check"
                  style={{ fontSize: '12px', color: 'var(--onyx)', cursor: 'pointer' }}
                >
                  Pin as Warm Beige Sticky Note in Inbox
                </label>
              </div>
            </div>
          )}
          {saveError && <p role="alert" style={{ color: 'var(--status-error)', fontSize: '12px' }}>{saveError}</p>}
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: '14px 24px',
            backgroundColor: 'var(--surface-subtle)',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
            Stores candidate deterministically in local task memory.
          </span>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button onClick={onClose} className="u-btn u-btn-ghost">
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving || !title.trim()}
              className="u-btn u-btn-primary"
            >
              <Check size={14} />
              {isSaving ? 'Saving…' : 'Confirm & Create Task'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
