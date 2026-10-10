import React, { lazy, Suspense } from 'react';
import { useAgent } from '../../context/AgentContext';
import { DisclaimerBanner } from '../common/DisclaimerBanner';
import { NavigationRail } from './NavigationRail';
import { TopHeader } from './TopHeader';
import { ContextDrawer } from './ContextDrawer';
import { CommandPalette } from './CommandPalette';
import { QuickCaptureModal } from '../quickcapture/QuickCaptureBar';

const TodayWorkspace = lazy(() => import('../../screens/TodayWorkspace').then(({ TodayWorkspace }) => ({ default: TodayWorkspace })));
const InboxScreen = lazy(() => import('../../screens/InboxScreen').then(({ InboxScreen }) => ({ default: InboxScreen })));
const KanbanWorkspace = lazy(() => import('../../screens/KanbanWorkspace').then(({ KanbanWorkspace }) => ({ default: KanbanWorkspace })));
const CalendarWorkspace = lazy(() => import('../../screens/CalendarWorkspace').then(({ CalendarWorkspace }) => ({ default: CalendarWorkspace })));
const ProjectsWorkspace = lazy(() => import('../../screens/ProjectsWorkspace').then(({ ProjectsWorkspace }) => ({ default: ProjectsWorkspace })));
const KnowledgeGraphWorkspace = lazy(() => import('../../screens/KnowledgeGraphWorkspace').then(({ KnowledgeGraphWorkspace }) => ({ default: KnowledgeGraphWorkspace })));
const AgentWorkbench = lazy(() => import('../../screens/AgentWorkbench').then(({ AgentWorkbench }) => ({ default: AgentWorkbench })));
const RunsAndApprovalsWorkspace = lazy(() => import('../../screens/RunsAndApprovalsWorkspace').then(({ RunsAndApprovalsWorkspace }) => ({ default: RunsAndApprovalsWorkspace })));
const RunConsoleScreen = lazy(() => import('../../screens/RunConsoleScreen').then(({ RunConsoleScreen }) => ({ default: RunConsoleScreen })));
const RemindersScreen = lazy(() => import('../../screens/RemindersScreen').then(({ RemindersScreen }) => ({ default: RemindersScreen })));
const RoomsScreen = lazy(() => import('../../screens/RoomsScreen').then(({ RoomsScreen }) => ({ default: RoomsScreen })));
const SettingsScreen = lazy(() => import('../../screens/SettingsScreen').then(({ SettingsScreen }) => ({ default: SettingsScreen })));

export const Shell: React.FC = () => {
  const {
    activeScreen,
    isQuickCaptureOpen,
    setIsQuickCaptureOpen,
  } = useAgent();

  const renderScreen = () => {
    switch (activeScreen) {
      case 'today':
        return <TodayWorkspace />;
      case 'inbox':
        return <InboxScreen />;
      case 'kanban':
        return <KanbanWorkspace />;
      case 'calendar':
        return <CalendarWorkspace />;
      case 'projects':
        return <ProjectsWorkspace />;
      case 'graph':
        return <KnowledgeGraphWorkspace />;
      case 'workbench':
        return <AgentWorkbench />;
      case 'activity':
      case 'approvals':
        return <RunsAndApprovalsWorkspace />;
      case 'run_console':
        return <RunConsoleScreen />;
      case 'reminders':
        return <RemindersScreen />;
      case 'rooms':
        return <RoomsScreen />;
      case 'settings':
        return <SettingsScreen />;
      default:
        return <TodayWorkspace />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100dvh', width: '100vw', overflow: 'hidden' }}>
      {/* Simulation Disclaimer Banner */}
      <DisclaimerBanner />

      {/* Main 3-Region Workspace */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', width: '100%', position: 'relative' }}>
        {/* Region 1: Left Navigation Rail */}
        <NavigationRail />

        {/* Region 2: Central Context Canvas */}
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, height: '100%', overflow: 'hidden' }}>
          {activeScreen !== 'workbench' && <TopHeader />}
          <main className={activeScreen === 'workbench' ? 'lara-main' : 'workspace-main'} role="main">
            <Suspense fallback={<div className="screen-loading" role="status">Opening workspace…</div>}>
              {renderScreen()}
            </Suspense>
          </main>
        </div>

        {/* Region 3: Right Context Drawer */}
        <ContextDrawer />
      </div>

      {/* Global Overlays */}
      <CommandPalette />
      <QuickCaptureModal
        isOpen={isQuickCaptureOpen}
        onClose={() => setIsQuickCaptureOpen(false)}
      />
    </div>
  );
};
