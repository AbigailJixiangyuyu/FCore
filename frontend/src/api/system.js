import { getJson, postForm } from './client.js'

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
