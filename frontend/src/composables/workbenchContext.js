import { inject } from 'vue'

export const workbenchKey = Symbol('workbench')

export function useWorkbench() {
  const workbench = inject(workbenchKey)
  if (!workbench) throw new Error('Workbench context is missing')
  return workbench
}

export const metricLabels = {
  internal_edges: 'Internal edges',
  transaction_count: 'Interactions',
}

export function probabilityLabel(value) {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1).replace(/\.0$/, '')}%`
}

