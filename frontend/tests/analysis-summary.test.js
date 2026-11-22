import assert from 'node:assert/strict'
import { test } from 'node:test'

import { summarizeRisk } from '../src/domain/analysisSummary.js'

function account(account_id, score, rank) {
  return { account_id, score, rank }
}

test('community risk uses scored members and preserves the full-graph rank', function () {
  const accounts = [
    account('outside', 0.95, 1),
    account('a', 0.9, 2),
    account('b', 0.4, 9),
    account('c', 0.3, 10),
    account('d', 0.2, 11),
    account('e', 0.1, 12),
  ]
  const original = structuredClone(accounts)
  const summary = summarizeRisk(['a', 'b', 'c', 'd', 'e', 'unscored'], accounts, 'outside')

  assert.equal(summary.scoredCount, 5)
  assert.deepEqual(summary.memberScores, [
    ...accounts.slice(1),
    { account_id: 'unscored', score: null },
  ])
  assert.equal(summary.topCount, 3)
  assert.equal(summary.mean.toFixed(4), '0.3800')
  assert.equal(summary.median, 0.3)
  assert.equal(summary.focus.account_id, 'a')
  assert.deepEqual(summary.box, {
    q1: 0.2, q3: 0.4,
    lowerWhisker: 0.1, upperWhisker: 0.4,
    minimum: 0.1, maximum: 0.9,
    outliers: [accounts[1]],
  })
  assert.deepEqual(accounts, original)
})

test('box plot interpolates quartiles between scores for an even community size', function () {
  const scores = [0.1, 0.3, 0.5, 0.7]
  const accounts = scores.map((score, index) => account(String(index), score, scores.length - index))
  const summary = summarizeRisk(accounts.map(item => item.account_id), accounts)

  assert.equal(summary.median.toFixed(4), '0.4000')
  assert.equal(summary.box.q1.toFixed(4), '0.2500')
  assert.equal(summary.box.q3.toFixed(4), '0.5500')
})

test('no scores and tied scores have distinct summaries', function () {
  const empty = summarizeRisk(['unscored'], [])
  assert.equal(empty.scoredCount, 0)
  assert.equal(empty.mean, null)
  assert.equal(empty.median, null)
  assert.equal(empty.box, null)

  const accounts = [account('a', 0.24, 1), account('b', 0.24, 2)]
  for (const members of [['a'], ['a', 'b']]) {
    const summary = summarizeRisk(members, accounts)
    assert.equal(summary.mean, 0.24)
    assert.equal(summary.median, 0.24)
    assert.equal(summary.box.lowerWhisker, 0.24)
    assert.equal(summary.box.upperWhisker, 0.24)
    assert.deepEqual(summary.box.outliers, [])
  }
})
