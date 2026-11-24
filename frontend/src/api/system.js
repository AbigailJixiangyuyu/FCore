import { getJson, postForm, startDemoSession } from './client.js'

export function getHealth(options) {
  return getJson('/health', options)
}

export function getCapabilities(options) {
  return getJson('/capabilities', options)
}

export function getDatasets(options) {
  return getJson('/datasets', options)
}

export function importDataset(file) {
  const form = new FormData()
  form.append('file', file)
  return postForm('/datasets/import', form)
}

export function appendSnapshot(dataset, file, operationId) {
  startDemoSession()
  const form = new FormData()
  form.append('file', file)
  form.append('dataset_version', dataset.dataset_version)
  form.append('observed_until', dataset.observed_until)
  form.append('operation_id', operationId)
  return postForm(`/datasets/${encodeURIComponent(dataset.dataset_id)}/snapshots`, form)
}
