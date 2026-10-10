import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, ChevronDown, Clock3, FileSearch, ListPlus, LockKeyhole, MessageSquarePlus, Search, X, Wrench } from 'lucide-react';
import { useAgent } from '../context/AgentContext';
import { INITIAL_ROOMS } from '../data/mockData';
import { ConversationMessage } from '../types';

type WaveState = 'idle' | 'focused' | 'processing' | 'ready' | 'error';
const suggestions = [
  { label: 'Plan my day', prompt: 'Help me plan my day around my upcoming tasks.' },
  { label: 'Capture a task', prompt: 'Capture a task: ' },
  { label: 'Search my local notes', prompt: 'Search my local notes for ' },
];
const operations = [
  { icon: <ListPlus size={16} />, name: 'Task capture', detail: 'Create and edit browser demo tasks in the Inbox.', available: true },
  { icon: <Search size={16} />, name: 'Local note search', detail: 'No note index is connected; prompt replies do not search notes.', available: false },
  { icon: <FileSearch size={16} />, name: 'Task and room context', detail: 'View the demo task list and the selected room context.', available: true },
  { icon: <Wrench size={16} />, name: 'Providers and external tools', detail: 'No inference provider, backend, or external tool is connected.', available: false },
];

function suggestedOperation(text: string) {
  const query = text.toLocaleLowerCase();
  if (/plan|today|schedule/.test(query)) return 'Task and schedule review (simulated)';
  if (/search|find|look up|notes/.test(query)) return 'Local note search (unavailable; no notes searched)';
  if (/capture|add|task|remind/.test(query)) return 'Task capture (preview only; not performed)';
  return 'General browser simulation (no tool selected)';
}

function makeWavePath(index: number, state: WaveState, time: number, pointer: { x: number; y: number }, hover: number) {
  const center = 110;
  const offset = index - 9;
  const distance = Math.abs(offset);
  const amplitude = 8 + Math.max(0, 54 - distance * 4.7) * (state === 'focused' ? 1.16 : state === 'processing' ? 1.12 : 1);
  const phase = index * 0.29 + time * (state === 'processing' ? 0.00105 : 0.00043);
  const points: string[] = [];
  for (let x = 0; x <= 1120; x += 8) {
    const focus = Math.exp(-Math.pow((x - 560) / 260, 2));
    const breathing = Math.sin(x * 0.0039 + phase) * amplitude * (0.28 + focus * 0.52);
    const local = Math.exp(-Math.pow((x - pointer.x) / 155, 2)) * hover;
    const displacement = local * ((pointer.y - center) * 0.16 + Math.sin((x - pointer.x) * 0.014) * 7);
    points.push(`${x === 0 ? 'M' : 'L'}${x},${(center + breathing + displacement).toFixed(2)}`);
  }
  return points.join(' ');
}

function Waveform({ state, compact = false }: { state: WaveState; compact?: boolean }) {
  const pathsRef = useRef<Array<SVGPathElement | null>>([]);
  const centerRef = useRef<SVGPathElement>(null);
  const pointerRef = useRef({ x: 560, y: 110, targetX: 560, targetY: 110, hover: 0, targetHover: 0 });
  const frameRef = useRef<number | null>(null);
  const [staticMotion, setStaticMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotion = () => setStaticMotion(media.matches);
    updateMotion();
    media.addEventListener('change', updateMotion);
    return () => media.removeEventListener('change', updateMotion);
  }, []);

  useEffect(() => {
    if (staticMotion) {
      pathsRef.current.forEach((path, index) => path?.setAttribute('d', makeWavePath(index, state, 0, { x: 560, y: 110 }, 0)));
      centerRef.current?.setAttribute('d', makeWavePath(9, state, 0, { x: 560, y: 110 }, 0));
      return;
    }
    let visible = !document.hidden;
    const tick = (time: number) => {
      const pointer = pointerRef.current;
      pointer.x += (pointer.targetX - pointer.x) * 0.035;
      pointer.y += (pointer.targetY - pointer.y) * 0.035;
      pointer.hover += (pointer.targetHover - pointer.hover) * 0.035;
      pathsRef.current.forEach((path, index) => path?.setAttribute('d', makeWavePath(index, state, time, pointer, pointer.hover)));
      centerRef.current?.setAttribute('d', makeWavePath(9, state, time, pointer, pointer.hover));
      if (visible) frameRef.current = window.requestAnimationFrame(tick);
    };
    const onVisibility = () => {
      visible = !document.hidden;
      if (!visible && frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
      if (visible) frameRef.current = window.requestAnimationFrame(tick);
    };
    document.addEventListener('visibilitychange', onVisibility);
    if (visible) frameRef.current = window.requestAnimationFrame(tick);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
    };
  }, [state, staticMotion]);

  const trackPointer = (event: React.PointerEvent<HTMLDivElement>) => {
    if (staticMotion || event.pointerType !== 'mouse') return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const pointer = pointerRef.current;
    pointer.targetX = ((event.clientX - bounds.left) / bounds.width) * 1120;
    pointer.targetY = ((event.clientY - bounds.top) / bounds.height) * 220;
    pointer.targetHover = 1;
  };

  return <div className={`wave-wrap${compact ? ' wave-wrap-compact' : ''}`} onPointerMove={trackPointer}
    onPointerLeave={() => { pointerRef.current.targetHover = 0; pointerRef.current.targetX = 560; pointerRef.current.targetY = 110; }}>
    <div className={`wave-field wave-${state}${staticMotion ? ' wave-static' : ''}`} aria-hidden="true">
      <svg viewBox="0 0 1120 220" preserveAspectRatio="none">
        {Array.from({ length: 19 }, (_, index) => <path key={index} ref={(node) => { pathsRef.current[index] = node; }}
          className={index === 9 ? 'wave-centerline' : 'wave-line'}
          strokeOpacity={0.1 + (1 - Math.abs(index - 9) / 10) * 0.32} strokeWidth={index === 9 ? 1.5 : 0.9} />)}
        <path ref={centerRef} className="wave-centerline wave-center-over" />
      </svg>
    </div>
    {!compact && <span className="wave-caption" aria-hidden="true">A quieter place to gather your work</span>}
  </div>;
}

function MessageText({ message }: { message: ConversationMessage }) {
  return <article className={`chat-message ${message.sender === 'user' ? 'chat-user' : 'chat-agent'}`}>
    <div className="chat-message-meta"><strong>{message.sender === 'user' ? 'You' : 'LARA IV'}</strong>
      {message.sender === 'agent' && message.simulated && <span>SIMULATED</span>}
      <time dateTime={message.timestamp}>{new Date(message.timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</time>
    </div>
    <p>{message.content}</p>
  </article>;
}

export const AgentWorkbench: React.FC = () => {
  const { messages, conversations, activeConversationId, sendMessage, createConversation, selectConversation, activeRoom, activePersona, setActiveScreen } = useAgent();
  const [input, setInput] = useState('');
  const [focused, setFocused] = useState(false);
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [waveReady, setWaveReady] = useState(false);
  const [error, setError] = useState('');
  const [toolsOpen, setToolsOpen] = useState(false);
  const [operationOpen, setOperationOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);
  const historyTriggerRef = useRef<HTMLButtonElement>(null);
  const historyDialogRef = useRef<HTMLElement>(null);
  const readyTimerRef = useRef<number | null>(null);
  const room = INITIAL_ROOMS.find((item) => item.id === activeRoom);
  const active = messages.length > 0;
  const state: WaveState = error ? 'error' : sending ? 'processing' : waveReady ? 'ready' : focused || input.trim() ? 'focused' : 'idle';

  useEffect(() => () => { if (readyTimerRef.current !== null) window.clearTimeout(readyTimerRef.current); }, []);

  useEffect(() => {
    if (active) threadEndRef.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'end' });
  }, [active, messages.length]);

  useEffect(() => {
    if (!historyOpen) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusFrame = window.requestAnimationFrame(() => historyDialogRef.current?.focus());
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setHistoryOpen(false); }
      if (event.key === 'Tab' && historyDialogRef.current) {
        const focusable = historyDialogRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), [tabindex]:not([tabindex="-1"])');
        const first = focusable.item(0); const last = focusable.item(focusable.length - 1);
        if (document.activeElement === historyDialogRef.current) { event.preventDefault(); (event.shiftKey ? last : first)?.focus(); }
        else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      window.removeEventListener('keydown', closeOnEscape);
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, [historyOpen]);

  const submit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const content = input.trim();
    if (!content) { setError('Write a message before sending.'); return; }
    if (sending) return;
    if (!activeConversationId) { setError('A browser conversation could not be opened. Check browser storage and try again.'); return; }
    setSending(true); setError(''); setFeedback(''); setOperationOpen(false);
    try {
      await sendMessage(content, activeRoom, activeConversationId);
      setFeedback('A simulated reply was saved in this browser. No model or tool ran.');
      setWaveReady(true);
      if (readyTimerRef.current !== null) window.clearTimeout(readyTimerRef.current);
      readyTimerRef.current = window.setTimeout(() => setWaveReady(false), 900);
      setInput('');
    } catch {
      setError('The browser could not save this exchange. Your text is still here; try again.');
    } finally { setSending(false); }
  };

  const sendPrompt = (prompt: string) => { setInput(prompt); setError(''); composerRef.current?.focus(); };
  const startConversation = async () => {
    setError(''); setFeedback(''); setInput(''); setHistoryOpen(false);
    try { await createConversation(); window.requestAnimationFrame(() => composerRef.current?.focus()); }
    catch { setError('A new conversation could not be created. Try again.'); }
  };
  const openSavedConversation = async (id: string) => {
    try { await selectConversation(id); setError(''); setFeedback(''); setHistoryOpen(false); window.requestAnimationFrame(() => composerRef.current?.focus()); }
    catch { setError('This conversation could not be opened. It remains in your browser history.'); }
  };
  const simulateOperation = suggestedOperation(input);

  return <section className={`ask-lara-page${active ? ' ask-active' : ''}`} aria-labelledby="ask-lara-title">
    <header className="ask-topline">
      <button className="ask-brand" onClick={() => setActiveScreen('workbench')} aria-label="LARA IV home"><span>LARA IV</span></button>
      <div className="ask-context"><LockKeyhole className="context-lock" size={13} aria-hidden="true" /><span>{room?.name || 'Operations'} room</span><span className="context-divider" /><span>{activePersona.replaceAll('_', ' ')}</span></div>
      <div className="ask-actions">
        {active && <button className="quiet-action" onClick={() => void startConversation()}><MessageSquarePlus size={15} />New chat</button>}
        <button ref={historyTriggerRef} className="quiet-action" onClick={() => setHistoryOpen(true)} aria-haspopup="dialog"><Clock3 size={15} />History</button>
      </div>
    </header>

    {active ? <div className="chat-stage">
      <div className="chat-brand-strip"><Waveform state={state} compact />
        <div><p className="ask-overline">BROWSER SIMULATION</p><h1 id="ask-lara-title">{conversations.find((item) => item.id === activeConversationId)?.title || 'New conversation'}</h1></div>
      </div>
      <div className="chat-transcript" role="log" aria-label="Conversation messages" aria-live="polite" aria-relevant="additions text">
        <div className="chat-messages">{messages.map((message) => <MessageText key={message.id} message={message} />)}<div ref={threadEndRef} /></div>
      </div>
      <div className="chat-composer-dock">
        <form className={`lara-composer chat-composer${focused ? ' is-focused' : ''}`} onSubmit={(event) => void submit(event)} aria-busy={sending}>
          <label className="sr-only" htmlFor="lara-composer">Message LARA IV</label>
          <textarea id="lara-composer" ref={composerRef} rows={2} value={input} placeholder="Reply to this conversation…" maxLength={2000} disabled={sending}
            onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} onChange={(event) => { setInput(event.target.value); setError(''); setFeedback(''); }}
            onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(); } }} />
          <div className="composer-foot"><span className="composer-hint">Enter to send <span aria-hidden="true">·</span> Shift + Enter for a new line</span>
            <button type="submit" className="send-button" aria-label="Send message" disabled={sending || !input.trim()}><ArrowUp size={18} /></button>
          </div>
        </form>
        <div className="chat-status" aria-live="polite">{error && <span className="ask-feedback error" role="alert">{error}</span>}{feedback && <span>{feedback}</span>}{sending && <span>Saving this simulated exchange…</span>}</div>
        {input.trim() && <div className="operation-preview"><button onClick={() => setOperationOpen((value) => !value)} aria-expanded={operationOpen}><span>Prompt routing preview: <strong>{simulateOperation}</strong></span><ChevronDown size={14} /></button>
          {operationOpen && <p>This is a local text preview only. Sending stores your prompt with a static reply; it does not call this operation.</p>}
        </div>}
      </div>
    </div> : <div className="ask-content">
      <div className="ask-intro"><p className="ask-overline">A LOCAL WORKSPACE FOR YOUR NEXT THOUGHT</p>
        <h1 id="ask-lara-title">Good to see you.</h1>
        <p className="ask-lede">What would you like to think through or put in motion?</p>
      </div>
      <Waveform state={state} />
      <form className={`lara-composer${focused ? ' is-focused' : ''}`} onSubmit={(event) => void submit(event)} aria-busy={sending}>
        <label className="sr-only" htmlFor="lara-composer">Message LARA IV</label>
        <textarea id="lara-composer" ref={composerRef} rows={2} value={input} placeholder="Ask, capture, or make a plan…" maxLength={2000} disabled={sending}
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} onChange={(event) => { setInput(event.target.value); setError(''); setFeedback(''); }}
          onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(); } }} />
        <div className="composer-foot"><span className="composer-hint">Enter to send <span aria-hidden="true">·</span> Shift + Enter for a new line</span>
          <button type="submit" className="send-button" aria-label="Send message" disabled={sending || !input.trim()}><ArrowUp size={18} /></button>
        </div>
      </form>
      <p className="simulation-note" role="note">Prototype mode. Replies are static browser simulations; no model or tool runs.</p>
      {error && <p className="ask-feedback error" role="alert">{error}</p>}
      {feedback && <p className="ask-feedback" role="status">{feedback}</p>}
      {input.trim() && <div className="operation-preview"><button onClick={() => setOperationOpen((value) => !value)} aria-expanded={operationOpen}><span>Prompt routing preview: <strong>{simulateOperation}</strong></span><ChevronDown size={14} /></button>
        {operationOpen && <p>This is a local text preview only. Sending stores your prompt with a static reply; it does not call this operation.</p>}
      </div>}
      <div className="prompt-suggestions" aria-label="Suggested prompts">{suggestions.map((item) => <button key={item.label} onClick={() => sendPrompt(item.prompt)}>{item.label}<span aria-hidden="true">↗</span></button>)}</div>
      <section className="tools-disclosure"><button className="tools-toggle" aria-expanded={toolsOpen} onClick={() => setToolsOpen((value) => !value)}><span className="tools-toggle-icon"><Wrench size={15} /></span><span><strong>Skills &amp; tools</strong><small>Inspect available prototype operations</small></span><ChevronDown className={toolsOpen ? 'rotated' : ''} size={16} /></button>
        {toolsOpen && <div className="tools-list">{operations.map((operation) => <div className="tool-row" key={operation.name}><span className="tool-icon">{operation.icon}</span><span className="tool-copy"><strong>{operation.name}</strong><small>{operation.detail}</small></span><span className={`tool-availability ${operation.available ? 'mock-available' : 'not-connected'}`}>{operation.available ? 'Demo UI available' : 'Unavailable'}</span></div>)}</div>}
      </section>
    </div>}

    {historyOpen && <div className="history-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setHistoryOpen(false); }}>
      <section ref={historyDialogRef} className="history-dialog" role="dialog" aria-modal="true" aria-labelledby="history-title" tabIndex={-1}>
        <header><div><p className="ask-overline">BROWSER SAVED</p><h2 id="history-title">Conversation history</h2></div><button aria-label="Close history" onClick={() => setHistoryOpen(false)}><X size={18} /></button></header>
        {conversations.length ? <div className="history-list">{conversations.map((conversation) => <button key={conversation.id} className={conversation.id === activeConversationId ? 'history-item is-current' : 'history-item'} onClick={() => void openSavedConversation(conversation.id)}>
          <strong>{conversation.title}</strong><span>{conversation.preview}</span><small>{new Date(conversation.updatedAt).toLocaleString()} · {conversation.messageCount} messages</small>
        </button>)}</div> : <p className="history-empty">No saved conversations yet. Messages will appear here after you send a prompt.</p>}
        <footer><span>Stored only in this browser</span><button className="quiet-action" onClick={() => void startConversation()}><MessageSquarePlus size={15} />New conversation</button></footer>
      </section>
    </div>}
  </section>;
};

