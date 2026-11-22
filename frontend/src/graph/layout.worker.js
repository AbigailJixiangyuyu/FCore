import { computeLayout } from './forceLayout.js'

self.onmessage = function ({ data }) {
  try {
    self.postMessage({ key: data.key, layout: computeLayout(data.reference) })
  } catch (error) {
    self.postMessage({ key: data.key, error: error.message })
  }
}
