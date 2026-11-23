import { matchesContext } from '../api/analysis.js'
import { predictionAlgorithms, structureAlgorithm } from './algorithms.js'

export const reportStages = { history: 'History', current: 'Current', future: 'Future' }

export function evidenceMethodName({ reference, method }) {
  const algorithm = predictionAlgorithms[reference.model] ?? structureAlgorithm(reference)
  return algorithm?.name ?? method
}

export function reportEvidenceDraft(slots) {
  return Object.entries(reportStages)
    .filter(([stage]) => slots[stage])
    .map(([stage, label]) => {
      const slot = slots[stage]
      return [label, evidenceMethodName(slot), slot.window].filter(Boolean).join(' · ')
    })
    .join('\n')
}

function rangeLabel(start, end) {
  return start === end ? end : [start, end].join('–')
}

export function structureEvidence(context, structure, riskModelVersion = null) {
  if (!matchesContext(structure, context)) return null
  const { origin, method, parameters, snapshot_id, structure_id, membership_hash } = structure
  const name = structureAlgorithm(structure)?.name ?? structure.label ?? method
  const reference = { ...context, origin, method, parameters: { ...parameters }, snapshot_id, structure_id, membership_hash }
  if (origin === 'pattern') {
    const e = structure.evidence
    const analysis = e.analysis_snapshot_ids
    const window = rangeLabel(e.witness_start_snapshot_id ?? analysis[0], e.witness_end_snapshot_id ?? analysis.at(-1))
    return { method: name, window, reference }
  }
  reference.risk_model_version = riskModelVersion
  const window = rangeLabel(parameters.start_snapshot_id ?? snapshot_id, snapshot_id)
  return { method: name, window, reference }
}

export function forecastEvidence(context, forecast, parameters) {
  if (!matchesContext(forecast, context) || !forecast.result_fingerprint || forecast.threshold !== parameters.threshold) return null
  const { account, k, model, threshold, model_version, target_snapshot, result_fingerprint } = forecast
  return {
    method: predictionAlgorithms[model]?.name ?? model,
    window: [target_snapshot, Number((threshold * 100).toFixed(2)) + '%'].join(' · '),
    reference: { ...context, account, k, model, threshold, horizon: parameters.horizon, model_version, target_snapshot, result_fingerprint },
  }
}
