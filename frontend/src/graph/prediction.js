import { matchesContext } from '../api/analysis.js'
import { forecastSnapshotId } from '../domain/timeline.js'

export function matchesCommunityPrediction(response, context, parameters, model) {
  if (!matchesContext(response, context) || !model || response.model !== model.id) return false
  // An empty historical union ends the query before loading a model.
  const withoutModel = response.status === 'no_historical_community' && response.model_version === null
  return !!(
    response.account === parameters.account &&
    response.k === parameters.k &&
    response.threshold === parameters.threshold &&
    response.target_snapshot === forecastSnapshotId(context.observed_until, parameters.horizon) &&
    (withoutModel || response.model_version === model.model_version)
  )
}
