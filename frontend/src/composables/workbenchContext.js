import { inject } from 'vue'

export const workbenchKey = Symbol('workbench')

export function useWorkbench() {
  const workbench = inject(workbenchKey)
  if (!workbench) throw new Error('Workbench context is missing')
  return workbench
}

export const currentAlgorithms = {
  parallel: {
    paperTitle: 'Parallel k-Core Decomposition: Theory and Practice',
    method: 'sigmod25-parallel-kcore-v1',
    path: '/queries/local-core',
  },
  tccs: {
    paperTitle: 'Evolution Forest Index: Towards Optimal Temporal k-Core Component Search via Time-Topology Isomorphic Computation',
    method: 'tccs-online-v1',
    path: '/queries/local-core',
  },
  pkmc: {
    paperTitle: 'Scalable Algorithms for Densest Subgraph Discovery',
    method: 'pkmc-v1',
    path: '/queries/max-core',
  },
}

export const metricLabels = {
  internal_edges: '内部连接数',
  transaction_count: '交易次数',
}

export function probabilityLabel(value) {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1).replace(/\.0$/, '')}%`
}

