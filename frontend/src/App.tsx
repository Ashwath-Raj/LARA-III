import React, { useEffect, useState } from 'react';
import { AgentProvider } from './context/AgentContext';
import { Shell } from './components/layout/Shell';
import { StartupIntro } from './components/StartupIntro';
import { LocalUbuntuAgentApi } from './api/localAdapter';

function LocalPairing() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { new LocalUbuntuAgentApi().session().then(() => setConnected(true)).catch(() => setConnected(false)); }, []);
  if (connected !== false) return null;
  const pair = async (event: React.FormEvent) => {
    event.preventDefault(); setError('');
    try { await new LocalUbuntuAgentApi().connect(token.trim()); setConnected(true); window.location.reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Pairing failed. Create a new token with the backend CLI.'); }
  };
  return <div style={{ position:'fixed', inset:0, zIndex:10000, display:'grid', placeItems:'center', background:'#0d1110eF', padding:24 }}>
    <form onSubmit={(e) => void pair(e)} style={{ width:'min(460px,100%)', padding:28, borderRadius:16, background:'#f6f7f4', color:'#17201d' }}>
      <h1>Connect to local LARA IV</h1><p>Paste the one-time pairing token printed by <code>ubuntu-agent api-session-create</code>. The browser stores only an HttpOnly session cookie.</p>
      <label style={{ display:'block', margin:'18px 0' }}>Pairing token<input autoFocus required value={token} onChange={(e) => setToken(e.target.value)} style={{ display:'block', width:'100%', marginTop:8, padding:12 }} /></label>
      {error && <p role="alert">{error}</p>}<button type="submit">Connect</button>
    </form>
  </div>;
}

export function App() {
  return (
    <AgentProvider>
      <Shell />
      <StartupIntro />
      <LocalPairing />
    </AgentProvider>
  );
}

export default App;
