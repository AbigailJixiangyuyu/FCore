import { matchesContext } from '../api/analysis.js'

export const reportStages = { history: 'History', current: 'Current', future: 'Future' }
const storageKey = 'temporal-graph:lifecycle-report:v1'
const historyMethods = {
  periodic: 'Periodic', durable: 'Durable', burst: 'Bursting core',
  frequency: 'Frequency-aware', temporal_core: 'Temporal core',
}
const currentMethods = { tccs: 'TCCS', pkmc: 'PKMC', parallel: 'Parallel core' }

export function readReportSession() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey))
    if (!saved?.context || !saved.slots) return null
    for (const [stage, slot] of Object.entries(saved.slots)) {
      if (!Object.hasOwn(reportStages, stage) || !matchesContext(slot?.reference, saved.context)) return null
    }
    if (Array.isArray(saved.report?.sentences)) {
      const { model, sentences } = saved.report
      saved.report = { model, content: sentences.join(' '), node_labels: {}, legacy: true }
    }
    if (!Array.isArray(saved.turns)) saved.turns = []
    return saved
  } catch {
    return null
  }
}

export function saveReportSession(value) {
  try {
    if (value) sessionStorage.setItem(storageKey, JSON.stringify(value))
    else sessionStorage.removeItem(storageKey)
  } catch {
    // The current page still works when tab storage is unavailable.
  }
}

function rangeLabel(start, end) {
  return start === end ? end : [start, end].join('–')
}

export function structureEvidence(context, structure, riskModelVersion = null) {
  if (!matchesContext(structure, context)) return null
  const { origin, method, parameters, snapshot_id, structure_id, membership_hash } = structure
  const reference = { ...context, origin, method, parameters: { ...parameters }, snapshot_id, structure_id, membership_hash }
  if (origin === 'pattern') {
    const e = structure.evidence
    const analysis = e.analysis_snapshot_ids
    const window = rangeLabel(e.witness_start_snapshot_id ?? analysis[0], e.witness_end_snapshot_id ?? analysis.at(-1))
    return { method: historyMethods[parameters.pattern], window, reference }
  }
  reference.risk_model_version = riskModelVersion
  const window = rangeLabel(parameters.start_snapshot_id ?? snapshot_id, snapshot_id)
  return { method: currentMethods[parameters.algorithm ?? 'parallel'], window, reference }
}

export function forecastEvidence(context, forecast, parameters) {
  if (!matchesContext(forecast, context) || !forecast.result_fingerprint || forecast.threshold !== parameters.threshold) return null
  const { account, k, model, threshold, model_version, target_snapshot, result_fingerprint } = forecast
  return {
    method: 'Zebra',
    window: [target_snapshot, Number((threshold * 100).toFixed(2)) + '%'].join(' · '),
    reference: { ...context, account, k, model, threshold, horizon: parameters.horizon, model_version, target_snapshot, result_fingerprint },
  }
}
