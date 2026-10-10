import React from 'react';
import { AgentProvider } from './context/AgentContext';
import { Shell } from './components/layout/Shell';
import { StartupIntro } from './components/StartupIntro';

export function App() {
  return (
    <AgentProvider>
      <Shell />
      <StartupIntro />
    </AgentProvider>
  );
}

export default App;
