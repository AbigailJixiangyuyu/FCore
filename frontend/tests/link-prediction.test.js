import assert from 'node:assert/strict'
import { test } from 'node:test'
import { matchesCommunityPrediction } from '../src/graph/prediction.js'

const context = { dataset_id: 'test', dataset_version: 'v2', observed_until: 'S12' }
const parameters = { account: '49', k: 6, threshold: 0.5, model: 'zebra' }
const model = { id: 'zebra', model_version: 'zebra-1' }
const result = {
  ...context, ...parameters, model_version: model.model_version,
  target_snapshot: 'S13', status: 'ok',
}

test('future results match the submitted query, dataset, forecast target and model', function () {
  assert.equal(matchesCommunityPrediction(result, context, parameters, model), true)
  for (const key of [
    'dataset_id', 'dataset_version', 'observed_until', 'account', 'k', 'threshold',
    'model', 'model_version', 'target_snapshot',
  ]) {
    assert.equal(matchesCommunityPrediction({ ...result, [key]: 'old' }, context, parameters, model), false, key)
  }
  const undergs = { id: 'undergs', model_version: 'undergs-1' }
  const switched = { ...result, model: undergs.id, model_version: undergs.model_version }
  assert.equal(matchesCommunityPrediction(switched, context, { ...parameters, model: undergs.id }, undergs), true)
  assert.equal(matchesCommunityPrediction(result, context, { ...parameters, model: undergs.id }, undergs), false)
})

test('an empty historical union can match a prediction without a model evaluation', function () {
  const empty = { ...result, model_version: null, status: 'no_historical_community' }
  assert.equal(matchesCommunityPrediction(empty, context, parameters, model), true)
  assert.equal(matchesCommunityPrediction(empty, context, { ...parameters, k: 7 }, model), false)
  assert.equal(matchesCommunityPrediction({ ...empty, status: 'no_threshold_edges' }, context, parameters, model), false)
})
