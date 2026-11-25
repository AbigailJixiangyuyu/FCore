import { getJson, postJson } from './client.js'

function contextParams(context, extra) {
  return new URLSearchParams({
    dataset_version: context.dataset_version,
    observed_until: context.observed_until,
    ...extra,
  })
}

export function matchesContext(response, context) {
  return !!(
    response && context &&
    response.dataset_id === context.dataset_id &&
    response.dataset_version === context.dataset_version &&
    response.observed_until === context.observed_until
  )
}

export function getCatalog(datasetId, options, granularity) {
  return getJson(
    `/datasets/${encodeURIComponent(datasetId)}/snapshots${granularity ? '?granularity=' + granularity : ''}`,
    options,
  )
}

export function getSnapshot(context, snapshotId, options) {
  const params = contextParams(context)
  return getJson(
    `/datasets/${encodeURIComponent(context.dataset_id)}/snapshots/${encodeURIComponent(snapshotId)}?${params}`,
    options,
  )
}

export function getAggregate(context, range, options) {
  const params = contextParams(context, range)
  return getJson(
    `/datasets/${encodeURIComponent(context.dataset_id)}/aggregate?${params}`,
    options,
  )
}

export function getObservedAggregate(context, options) {
  return getJson(
    `/datasets/${encodeURIComponent(context.dataset_id)}/observed-aggregate?${contextParams(context)}`,
    options,
  )
}

export function getWindowCoreness(context, start, options) {
  const params = contextParams(context, { start_snapshot_id: start })
  return getJson(`/datasets/${encodeURIComponent(context.dataset_id)}/window-coreness?${params}`, options)
}

export function analyze(path, context, parameters, options) {
  return postJson(path, { ...context, ...parameters }, options)
}

export function getPredictionModels(context, horizon, options) {
  const params = contextParams(context, { horizon })
  return getJson(
    `/datasets/${encodeURIComponent(context.dataset_id)}/link-prediction/models?${params}`,
    options,
  )
}
