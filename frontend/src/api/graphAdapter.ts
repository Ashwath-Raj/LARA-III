import { GraphData } from './adapter';
import { KnowledgeGraphEdge, KnowledgeGraphNode } from '../types';

export interface GraphRecord extends KnowledgeGraphNode {
  color: string;
}

export interface GraphRelation extends Omit<KnowledgeGraphEdge, 'sourceNodeId' | 'targetNodeId'> {
  source: string;
  target: string;
}

export interface GraphViewData {
  nodes: GraphRecord[];
  links: GraphRelation[];
  source: 'prototype';
}

const nodeColors: Record<KnowledgeGraphNode['nodeType'], string> = {
  task: '#0075A2',
  course: '#536E68',
  file: '#BDC2BF',
  project: '#536E68',
  person: '#989C94',
  source: '#71847D',
  observation: '#996200',
  claim: '#0075A2',
  argument: '#536E68',
  contradiction: '#B52B27',
  revision: '#1D7337',
  decision: '#0075A2',
  conclusion: '#536E68',
  deadline: '#996200',
  job: '#536E68',
};

const safeMetadata = (metadata: Record<string, unknown>) => Object.fromEntries(
  Object.entries(metadata).filter(([key, value]) =>
    !/path|sha|hash|secret|token|credential|url|absolute/i.test(key)
    && (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')),
);

/** Adapts only explicitly supplied mock graph rows; it never infers edges or claims authorization. */
export function adaptPrototypeGraph(data: GraphData): GraphViewData {
  const nodes: GraphRecord[] = data.nodes.slice(0, 150).map((node) => ({
    ...node,
    sourceRef: node.sourceRef.startsWith('/') ? node.sourceRef.split('/').at(-1) || 'local source' : node.sourceRef,
    metadata: safeMetadata(node.metadata),
    color: nodeColors[node.nodeType],
  }));
  const ids = new Set(nodes.map((node) => node.id));
  const links: GraphRelation[] = data.edges.slice(0, 400)
    .filter((edge) => ids.has(edge.sourceNodeId) && ids.has(edge.targetNodeId))
    .map(({ sourceNodeId, targetNodeId, ...edge }) => ({ ...edge, source: sourceNodeId, target: targetNodeId }));
  return { nodes, links, source: 'prototype' };
}
