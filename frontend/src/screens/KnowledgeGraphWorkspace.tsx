import React, { Component, lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import type { ErrorInfo } from 'react';
import type { ForceGraphMethods } from 'react-force-graph-3d';
import { ArrowDownLeft, ArrowUpRight, Focus, LocateFixed, RotateCcw, Search, Share2, X } from 'lucide-react';
import { useAgent } from '../context/AgentContext';
import { adaptPrototypeGraph, GraphRecord, GraphRelation } from '../api/graphAdapter';
import { KnowledgeGraphEdge, KnowledgeGraphNode } from '../types';
import { INITIAL_ROOMS } from '../data/mockData';

const ForceGraph3D = lazy(() => import('react-force-graph-3d'));

function supportsWebGL() {
  try {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (!context) return false;
    (context as WebGLRenderingContext).getExtension('WEBGL_lose_context')?.loseContext();
    return true;
  } catch { return false; }
}

interface GraphProps {
  graph: ReturnType<typeof adaptPrototypeGraph>;
  selectedNode: KnowledgeGraphNode | null;
  selectedEdge: KnowledgeGraphEdge | null;
  onSelectNode: (node: KnowledgeGraphNode) => void;
  onSelectEdge: (edge: GraphRelation) => void;
  search: string;
  typeFilter: string;
  roomFilter: string;
  reducedMotion: boolean;
}


function domainEdge(edge: GraphRelation): KnowledgeGraphEdge {
  return { id: edge.id, sourceNodeId: edge.source, targetNodeId: edge.target,
    relationType: edge.relationType, roomId: edge.roomId, whyConnected: edge.whyConnected, provenance: edge.provenance };
}

function GraphCanvas({ graph, selectedNode, selectedEdge, onSelectNode, onSelectEdge, search, typeFilter, roomFilter, reducedMotion }: GraphProps) {
  const graphRef = useRef<ForceGraphMethods | undefined>(undefined);
  const renderedNodesRef = useRef(new Map<string, GraphRecord & { x?: number; y?: number; z?: number }>());
  const [size, setSize] = useState({ width: 680, height: 500 });
  const hostRef = useRef<HTMLDivElement>(null);
  const needle = search.trim().toLocaleLowerCase();
  const nodes = useMemo(() => graph.nodes.filter((node) =>
    (typeFilter === 'all' || node.nodeType === typeFilter)
    && (roomFilter === 'all' || node.roomId === roomFilter)
    && (!needle || node.displayName.toLocaleLowerCase().includes(needle) || node.sourceRef.toLocaleLowerCase().includes(needle))), [graph.nodes, typeFilter, roomFilter, needle]);
  const visibleIds = useMemo(() => new Set(nodes.map((node) => node.id)), [nodes]);
  const links = useMemo(() => graph.links.filter((link) => visibleIds.has(link.source) && visibleIds.has(link.target)), [graph.links, visibleIds]);
  const rendererData = useMemo(() => ({ nodes: nodes.map((node, index) => ({
    ...node,
    ...(reducedMotion ? { fx: node.x ?? index * 45, fy: node.y ?? (index % 3) * 60, fz: (INITIAL_ROOMS.findIndex((room) => room.id === node.roomId) - 2) * 70 } : {}),
  })), links: links.map((link) => ({ ...link })) }), [nodes, links, reducedMotion]);
  useEffect(() => {
    renderedNodesRef.current = new Map(rendererData.nodes.map((node) => [node.id, node]));
  }, [rendererData]);
  const neighborIds = useMemo(() => {
    const id = selectedNode?.id;
    if (!id) return new Set<string>();
    return new Set(links.flatMap((link) => link.source === id ? [link.target] : link.target === id ? [link.source] : []));
  }, [links, selectedNode?.id]);

  useEffect(() => {
    if (!hostRef.current) return;
    const observer = new ResizeObserver(([entry]) => setSize({ width: entry.contentRect.width, height: entry.contentRect.height }));
    observer.observe(hostRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!nodes.length) return;
    const timer = window.setTimeout(() => graphRef.current?.zoomToFit(reducedMotion ? 0 : 450, 46), 100);
    return () => window.clearTimeout(timer);
  }, [nodes.length, roomFilter, typeFilter, reducedMotion]);

  const focusSelected = () => {
    const node = selectedNode ? renderedNodesRef.current.get(selectedNode.id) || selectedNode : null;
    if (!node) return;
    const point = node as { x?: number; y?: number; z?: number };
    graphRef.current?.cameraPosition({ x: (point.x || 0) + 70, y: (point.y || 0) + 55, z: (point.z || 0) + 190 }, { x: point.x || 0, y: point.y || 0, z: point.z || 0 }, reducedMotion ? 0 : 520);
  };

  return <div className="graph-canvas" ref={hostRef} aria-label="Interactive three dimensional graph. Drag to orbit, right drag to pan, scroll to zoom.">
    <Suspense fallback={<div className="graph-fallback-status" role="status">Loading the 3D renderer…</div>}>
      <ForceGraph3D ref={graphRef as never} graphData={rendererData} width={size.width} height={size.height} backgroundColor="#F0F2EF"
        controlType="orbit" showNavInfo={false} enableNavigationControls enablePointerInteraction enableNodeDrag
        nodeLabel={(node) => `${node.displayName} · ${node.nodeType}`}
        nodeColor={(node) => selectedNode?.id === String(node.id) ? '#005779' : selectedNode && !neighborIds.has(String(node.id)) ? '#A7B2AD' : node.color}
        nodeVal={(node) => selectedNode?.id === node.id ? 7 : 4}
        linkLabel={(link) => `${link.relationType}: ${link.whyConnected}`}
        linkColor={(link) => {
          const source = typeof link.source === 'object' ? link.source.id : link.source;
          const target = typeof link.target === 'object' ? link.target.id : link.target;
          return selectedEdge?.id === String(link.id) ? '#0075A2' : selectedNode && source !== selectedNode.id && target !== selectedNode.id ? '#B9C2BE' : '#7F938B';
        }}
        linkOpacity={0.68} linkWidth={(link) => selectedEdge?.id === link.id ? 2.8 : 1.05}
        linkDirectionalArrowLength={3.5} linkDirectionalArrowRelPos={1} linkDirectionalArrowColor={() => '#536E68'}
        cooldownTicks={reducedMotion ? 0 : 90} d3AlphaDecay={0.035} warmupTicks={reducedMotion ? 0 : 40}
        onNodeClick={(node) => { const actual = graph.nodes.find((item) => item.id === node.id); if (actual) onSelectNode(actual); }}
        onLinkClick={(link) => { const actual = graph.links.find((item) => item.id === String(link.id)); if (actual) onSelectEdge(actual); }} />
    </Suspense>
    <div className="graph-canvas-tools" aria-label="Graph camera controls">
      <button aria-label="Fit all visible nodes" title="Fit to view" onClick={() => graphRef.current?.zoomToFit(520, 48)}><Focus size={16} /></button>
      <button aria-label="Reset graph camera" title="Reset view" onClick={() => { graphRef.current?.zoomToFit(reducedMotion ? 0 : 450, 48); if (!reducedMotion) graphRef.current?.d3ReheatSimulation(); }}><RotateCcw size={16} /></button>
      <button aria-label="Focus selected node" title="Focus selection" onClick={focusSelected} disabled={!selectedNode}><LocateFixed size={16} /></button>
    </div>
    <span className="graph-axis-hint" aria-hidden="true">DRAG ORBIT <i /> RIGHT DRAG PAN <i /> SCROLL ZOOM</span>
  </div>;
}

class GraphErrorBoundary extends Component<React.PropsWithChildren, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* The accessible list remains available below. */ }
  render() { return this.state.failed ? <div className="graph-fallback-status" role="status">3D rendering is unavailable in this browser. Use the searchable node list below.</div> : this.props.children; }
}

function printableSource(value: string) {
  if (value.startsWith('/')) return value.split('/').at(-1) || 'Local source';
  return value.replace(/^local:\/\//, 'Demo record · ');
}

export const KnowledgeGraphWorkspace: React.FC = () => {
  const { graphNodes, graphEdges, graphLoadError, loading, refreshAll } = useAgent();
  const [selectedGraphNode, setSelectedGraphNode] = useState<KnowledgeGraphNode | null>(null);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [roomFilter, setRoomFilter] = useState('all');
  const [selectedEdge, setSelectedEdge] = useState<KnowledgeGraphEdge | null>(null);
  const [webgl] = useState(supportsWebGL);
  const [retrying, setRetrying] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const graph = useMemo(() => adaptPrototypeGraph({ nodes: graphNodes, edges: graphEdges }), [graphNodes, graphEdges]);
  const filteredNodes = useMemo(() => {
    const needle = debouncedSearch.trim().toLocaleLowerCase();
    return graph.nodes.filter((node) => (typeFilter === 'all' || node.nodeType === typeFilter)
      && (roomFilter === 'all' || node.roomId === roomFilter)
      && (!needle || node.displayName.toLocaleLowerCase().includes(needle) || node.sourceRef.toLocaleLowerCase().includes(needle)));
  }, [graph.nodes, debouncedSearch, typeFilter, roomFilter]);
  const filteredIds = useMemo(() => new Set(filteredNodes.map((node) => node.id)), [filteredNodes]);
  const visibleEdges = useMemo(() => graph.links.filter((edge) => filteredIds.has(edge.source) && filteredIds.has(edge.target)), [graph.links, filteredIds]);
  const selected = selectedGraphNode ? graph.nodes.find((node) => node.id === selectedGraphNode.id) : undefined;
  const incoming = selected ? graph.links.filter((edge) => edge.target === selected.id) : [];
  const outgoing = selected ? graph.links.filter((edge) => edge.source === selected.id) : [];
  const types = [...new Set(graph.nodes.map((node) => node.nodeType))];

  useEffect(() => { const timer = window.setTimeout(() => setDebouncedSearch(search), 160); return () => window.clearTimeout(timer); }, [search]);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updatePreference = () => setReducedMotion(preference.matches);
    preference.addEventListener('change', updatePreference);
    return () => preference.removeEventListener('change', updatePreference);
  }, []);
  const currentSelectedEdge = selectedEdge && graph.links.some((edge) => edge.id === selectedEdge.id) ? selectedEdge : null;

  return <section className="graph-workspace" aria-labelledby="graph-title">
    <header className="graph-heading"><div><p className="ask-overline">PROJECTS &amp; MEMORY</p><h1 id="graph-title">Knowledge graph</h1><p>Explore relationships explicitly listed in the prototype records.</p></div>
      <span className="graph-demo-label">Prototype data · not live memory</span></header>
    <p className="graph-provenance-note">No authorized graph API is connected. This view uses bundled demo records only; filters are for exploration and do not enforce access policy.</p>
    <div className="graph-toolbar">
      <label className="graph-search"><Search size={16} /><span className="sr-only">Search nodes and sources</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search nodes or sources" /></label>
      <label><span className="sr-only">Filter graph by entity type</span><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">All types</option>{types.map((type) => <option key={type} value={type}>{type.replaceAll('_', ' ')}</option>)}</select></label>
      <label><span className="sr-only">Filter graph by room</span><select value={roomFilter} onChange={(event) => setRoomFilter(event.target.value)}><option value="all">All demo rooms</option>{INITIAL_ROOMS.filter((room) => graph.nodes.some((node) => node.roomId === room.id)).map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}</select></label>
      {selectedGraphNode && <button className="graph-clear-selection" onClick={() => { setSelectedGraphNode(null); setSelectedEdge(null); }}><X size={14} />Clear selection</button>}
    </div>
    <div className="graph-summary"><span>{filteredNodes.length} demo nodes</span><span>{visibleEdges.length} explicit relations</span><span>3D orbit workspace</span></div>
    {loading ? <div className="graph-empty" role="status"><Share2 size={20} /><h2>Loading prototype records</h2><p>Reading the bundled graph fixture.</p></div>
      : graphLoadError ? <div className="graph-empty" role="alert"><Share2 size={20} /><h2>Graph records could not be loaded</h2><p>{graphLoadError}</p><button disabled={retrying} onClick={() => { setRetrying(true); void refreshAll().finally(() => setRetrying(false)); }}>{retrying ? 'Retrying…' : 'Retry'}</button></div>
      : !graph.nodes.length ? <div className="graph-empty"><Share2 size={20} /><h2>No prototype graph records</h2><p>When authorized graph data is available, this workspace can display its explicitly stored relationships.</p></div>
      : !filteredNodes.length ? <div className="graph-empty"><Search size={20} /><h2>No matching records</h2><p>Clear the search or broaden the room and entity filters.</p><button onClick={() => { setSearch(''); setTypeFilter('all'); setRoomFilter('all'); }}>Clear filters</button></div>
        : <div className="graph-layout">
          <div className="graph-main-column">
            {webgl ? <GraphErrorBoundary><GraphCanvas graph={graph} selectedNode={selectedGraphNode} selectedEdge={currentSelectedEdge} search={debouncedSearch} typeFilter={typeFilter} roomFilter={roomFilter} reducedMotion={reducedMotion} onSelectNode={(node) => { setSelectedGraphNode(node); setSelectedEdge(null); }} onSelectEdge={(edge) => { setSelectedEdge(domainEdge(edge)); setSelectedGraphNode(null); }} /></GraphErrorBoundary>
              : <div className="graph-fallback-status" role="status">WebGL is unavailable. Select records from the accessible list below.</div>}
            <section className="graph-node-list" aria-labelledby="graph-node-list-title"><header><h2 id="graph-node-list-title">Visible records</h2><span>Keyboard accessible</span></header>
              <ul>{filteredNodes.map((node) => <li key={node.id}><button className={selected?.id === node.id ? 'is-selected' : ''} onClick={() => { setSelectedGraphNode(node); setSelectedEdge(null); }} aria-pressed={selected?.id === node.id}>
                <span className="graph-node-dot" style={{ backgroundColor: node.color }} /><span className="graph-list-title">{node.displayName}</span><small>{node.nodeType} · {INITIAL_ROOMS.find((room) => room.id === node.roomId)?.name}</small>
              </button></li>)}</ul>
            </section>
            <section className="graph-node-list graph-edge-list" aria-labelledby="graph-edge-list-title"><header><h2 id="graph-edge-list-title">Explicit relationships</h2><span>{visibleEdges.length}</span></header>
              <ul>{visibleEdges.map((edge) => <li key={edge.id}><button className={currentSelectedEdge?.id === edge.id ? 'is-selected' : ''} onClick={() => { setSelectedEdge(domainEdge(edge)); setSelectedGraphNode(null); }} aria-pressed={currentSelectedEdge?.id === edge.id}>
                <span className="graph-list-title">{graph.nodes.find((node) => node.id === edge.source)?.displayName} → {graph.nodes.find((node) => node.id === edge.target)?.displayName}</span><small>{edge.relationType}</small>
              </button></li>)}</ul>
            </section>
          </div>
          <aside className="graph-detail-panel" aria-live="polite">
            {selected ? <><header><span className="graph-detail-type">{selected.nodeType} · {selected.roomId.replaceAll('_', ' ')}</span><button aria-label="Close node details" onClick={() => setSelectedGraphNode(null)}><X size={17} /></button></header>
              <h2>{selected.displayName}</h2><p className="graph-detail-scope">Prototype fixture · not a verified persistent record</p>
              <dl><div><dt>Source reference</dt><dd>{printableSource(selected.sourceRef)}</dd></div><div><dt>Last updated in fixture</dt><dd>{new Date(selected.lastUpdated).toLocaleString()}</dd></div>{Object.entries(selected.metadata).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{Array.isArray(value) ? value.join(', ') : String(value)}</dd></div>)}</dl>
              <section className="graph-relations"><h3><ArrowDownLeft size={14} />Incoming ({incoming.length})</h3>{incoming.length ? incoming.map((edge) => <button key={edge.id} onClick={() => { setSelectedEdge(domainEdge(edge)); setSelectedGraphNode(null); }}><span>{graph.nodes.find((node) => node.id === edge.source)?.displayName}</span><small>{edge.relationType} → {selected.displayName}</small></button>) : <p>No incoming prototype relations.</p>}</section>
              <section className="graph-relations"><h3><ArrowUpRight size={14} />Outgoing ({outgoing.length})</h3>{outgoing.length ? outgoing.map((edge) => <button key={edge.id} onClick={() => { setSelectedEdge(domainEdge(edge)); setSelectedGraphNode(null); }}><span>{edge.relationType} → {graph.nodes.find((node) => node.id === edge.target)?.displayName}</span><small>{edge.whyConnected}</small></button>) : <p>No outgoing prototype relations.</p>}</section>
            </> : currentSelectedEdge ? <><header><span className="graph-detail-type">EXPLICIT PROTOTYPE RELATION</span><button aria-label="Close relation details" onClick={() => setSelectedEdge(null)}><X size={17} /></button></header>
              <h2>{graph.nodes.find((node) => node.id === currentSelectedEdge.sourceNodeId)?.displayName} → {graph.nodes.find((node) => node.id === currentSelectedEdge.targetNodeId)?.displayName}</h2>
              <p className="graph-relation-name">{currentSelectedEdge.relationType}</p><div className="graph-evidence"><strong>Why this edge exists</strong><p>{currentSelectedEdge.whyConnected}</p><strong>Fixture provenance</strong><p>{currentSelectedEdge.provenance}</p><small>These are supplied prototype strings, not verified provenance.</small></div>
            </> : <div className="graph-detail-empty"><Focus size={18} /><p>Select a node or relationship to inspect its fixture details.</p></div>}
          </aside>
        </div>}
  </section>;
};
