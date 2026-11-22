import { matchesContext } from '../api/analysis.js'
import { FUTURE_INDEX, snapshotId } from '../domain/timeline.js'

export function matchesCommunityPrediction(response, context, parameters, model) {
  if (!matchesContext(response, context) || !model || response.model !== model.id) return false
  // An empty historical union ends the query before loading a model.
  const withoutModel = response.status === 'no_historical_community' && response.model_version === null
  return !!(
    response.account === parameters.account &&
    response.k === parameters.k &&
    response.threshold === parameters.threshold &&
    response.model === parameters.model &&
    response.target_snapshot === snapshotId(FUTURE_INDEX) &&
    (withoutModel || response.model_version === model.model_version)
  )
}
