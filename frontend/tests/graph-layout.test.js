import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { computeLayout } from '../src/graph/forceLayout.js'
import { boxesOverlap, placeNodeLabels } from '../src/graph/labels.js'
import {
  boundsOf,
  normalizeReference,
  referenceFingerprint,
} from '../src/graph/layoutReference.js'
import { futureScene, observedScene } from '../src/graph/scene.js'

function reference(nodes, edges = []) {
  return normalizeReference({
    nodes: nodes.map(function (id) {
      return { id }
    }),
    edges: edges.map(function ([u, v]) {
      return { u, v }
    }),
  })
}

function dept3Frame(snapshotIds) {
  const directory = new URL('../../data/email-eu-core-dept3/', import.meta.url)
  const nodes = JSON.parse(
    readFileSync(new URL('accounts.json', directory), 'utf8'),
  )
  const counts = new Map()
  for (const sid of snapshotIds) {
    const csv = readFileSync(new URL(`${sid}.csv`, directory), 'utf8')
      .trim()
      .split(/\r?\n/)
      .slice(1)
    for (const row of csv) {
      const pair = row.split(',').slice(0, 2).sort()
      const key = JSON.stringify(pair)
      counts.set(key, (counts.get(key) || 0) + 1)
    }
  }
  return {
    nodes,
    core_numbers: {},
    snapshot_id: snapshotIds.join(':'),
    edges: [...counts].map(function ([key, transaction_count]) {
      const [u, v] = JSON.parse(key)
      return { id: key, u, v, transaction_count }
    }),
  }
}
const history = dept3Frame(
  Array.from({ length: 11 }, function (_, index) {
    return `S${String(index + 1).padStart(2, '0')}`
  }),
)
const historyReference = normalizeReference(history)
const layout = computeLayout(historyReference)

test('layout projection removes direction, repetition, self-loops and metadata only', async function () {
  const a = reference(
    ['c', 'a', 'b', 'isolated'],
    [
      ['a', 'b'],
      ['b', 'a'],
      ['a', 'a'],
      ['b', 'c'],
    ],
  )
  const b = reference(
    ['isolated', 'b', 'a', 'c'],
    [
      ['c', 'b'],
      ['a', 'b'],
      ['a', 'b'],
    ],
  )
  assert.deepEqual(a, b)
  assert.equal(await referenceFingerprint(a), await referenceFingerprint(b))
  assert.notEqual(
    await referenceFingerprint(a),
    await referenceFingerprint(reference(a.nodes, [['a', 'c']])),
  )
})

test('current-only accounts get positions and empty history uses the current topology', function () {
  const history = { nodes: [{ id: '001' }], edges: [] }
  const current = {
    nodes: [{ id: '001' }, { id: '002' }],
    edges: [{ u: '001', v: '002' }],
  }
  const stable = normalizeReference(history, current)
  assert.deepEqual(stable, { nodes: ['001', '002'], edges: [] })
  assert.ok(computeLayout(stable).positions['002'])
  assert.deepEqual(normalizeReference({ nodes: [], edges: [] }, current), {
    nodes: ['001', '002'],
    edges: [['001', '002']],
  })
})

test('empty, single, isolated and disconnected graphs retain every node with finite distinct positions', function () {
  for (const input of [
    reference([]),
    reference(['one']),
    reference(['a', 'b', 'c']),
    reference(
      ['a', 'b', 'c', 'd', 'e'],
      [
        ['a', 'b'],
        ['c', 'd'],
      ],
    ),
  ]) {
    const result = computeLayout(input)
    assert.deepEqual(
      Object.keys(result.positions).sort(),
      [...input.nodes].sort(),
    )
    const unique = new Set()
    for (const point of Object.values(result.positions)) {
      assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y))
      unique.add(`${point.x}:${point.y}`)
    }
    assert.equal(unique.size, input.nodes.length)
    assert.deepEqual(result, computeLayout(input))
  }
})

test('Dept3 history layout is deterministic, nonoverlapping and does not mutate input', function () {
  const before = JSON.stringify(historyReference)
  assert.equal(historyReference.nodes.length, 89)
  assert.equal(historyReference.edges.length, 848)
  assert.deepEqual(
    layout,
    computeLayout(
      normalizeReference({
        ...history,
        nodes: [...history.nodes].reverse(),
        edges: [...history.edges].reverse(),
      }),
    ),
  )
  assert.equal(JSON.stringify(historyReference), before)
  const points = Object.values(layout.positions)
  for (let a = 0; a < points.length; a++)
    for (let b = a + 1; b < points.length; b++) {
      assert.ok(
        Math.hypot(points[a].x - points[b].x, points[a].y - points[b].y) >= 12,
      )
    }
})

test('isolated vertices scatter inside the network and leave connected vertices in place', function () {
  const connected = Array.from({ length: 24 }, (_, i) => `v${i}`)
  const isolates = Array.from({ length: 8 }, (_, i) => `isolate${i}`)
  const edges = connected.map((id, i) => [id, connected[(i + 1) % connected.length]])
  const fixed = computeLayout(reference(connected, edges)).positions
  const mixed = reference([...connected, ...isolates], edges)
  const { positions } = computeLayout(mixed)
  const bounds = boundsOf(fixed, 0)

  for (const id of connected) assert.deepEqual(positions[id], fixed[id])
  assert.deepEqual(computeLayout(mixed).positions, positions)
  assert.equal(new Set(isolates.map(id => positions[id].y)).size, isolates.length)
  for (const id of isolates) {
    const point = positions[id]
    assert.ok(point.x >= bounds.x[0] && point.x <= bounds.x[1])
    assert.ok(point.y >= bounds.y[0] && point.y <= bounds.y[1])
    for (const other of mixed.nodes.filter(other => other !== id)) {
      assert.ok(Math.hypot(point.x - positions[other].x, point.y - positions[other].y) >= 12)
    }
  }
})

test('historical ranges preserve the same community coordinates while changing observed edges', function () {
  const options = {
    structure: { members: ['49', '2', '1', '3'], color: '#123456' },
    anchor: '49',
  }
  const a = observedScene(history, layout, options)
  const b = observedScene(dept3Frame(['S03', 'S04', 'S05']), layout, {
    ...options,
    rangeLabel: 'S03—S05',
  })
  assert.equal(a.nodes.length, 4)
  assert.equal(b.nodes.length, 4)
  assert.deepEqual(
    a.nodes.map(function ({ id, x, y }) {
      return { id, x, y }
    }),
    b.nodes.map(function ({ id, x, y }) {
      return { id, x, y }
    }),
  )
  assert.deepEqual(a.bounds, b.bounds)
  assert.notEqual(a.edges.length, b.edges.length)
})

test('observed views keep the whole graph until a result, then show only its internal transactions', function () {
  const frame = dept3Frame(['S12'])
  const ids = ['49', '0', '1', '2', '3', '4', '5']
  const members = new Set(ids)
  const options = {
    structure: { members: ids },
    anchor: '49',
  }
  const result = observedScene(frame, layout, options)
  const overview = observedScene(frame, layout, { overview: true })
  assert.equal(overview.nodes.length, 89)
  assert.equal(overview.edges.length, 320)
  assert.ok(overview.nodes.every(node => !node.matched))
  assert.equal(result.nodes.length, ids.length)
  assert.equal(
    result.edges.length,
    frame.edges.filter(function (edge) {
      return members.has(edge.u) && members.has(edge.v)
    }).length,
  )
  for (const edge of result.edges) {
    assert.ok(members.has(edge.u) && members.has(edge.v))
    assert.equal(
      edge.transaction_count,
      frame.edges.find(function (original) {
        return original.id === edge.id
      }).transaction_count,
    )
  }
  assert.equal(observedScene(frame, layout, {}), null)
})

test('anomaly location without a community shows just that account', function () {
  const frame = dept3Frame(['S12'])
  const location = { accountId: '6', source: 'anomaly' }
  const result = observedScene(frame, layout, { location })
  assert.deepEqual(result.nodes.map(node => node.id), ['6'])
  assert.equal(result.nodes[0].anomaly, true)
  assert.equal(result.nodes[0].matched, false)
  assert.deepEqual(result.edges, [])
})

test('the forecast scene keeps all community edges and places the query node in the stable layout', function () {
  const prediction = {
    members: ['0', '1', '2', '49'],
    account: '49',
    target_snapshot: 'S13',
    edges: [
      { u: '0', v: '49', probability: 0.9 },
      { u: '0', v: '1', probability: 0.8 },
      { u: '1', v: '2', probability: 0.7 },
      { u: '2', v: '49', probability: 0.6 },
    ],
  }
  const scene = futureScene(prediction, layout)
  assert.deepEqual(scene.nodes.map(({ id }) => id), prediction.members)
  for (const { id, x, y, degree, query } of scene.nodes) {
    assert.deepEqual({ x, y }, layout.positions[id])
    assert.equal(degree, 2)
    assert.equal(query, id === prediction.account)
  }
  assert.deepEqual(scene.edges.map(({ u, v, probability }) => [u, v, probability]),
    prediction.edges.map(({ u, v, probability }) => [u, v, probability]))
  assert.ok(scene.edges.every(edge => edge.predicted && edge.target_snapshot === 'S13'))
  assert.equal(futureScene({ members: [] }, layout), null)
})

const labelMetrics = { height: 18, widthFor: id => id.length * 8 + 8 }

test('labels prioritize focused nodes, stay in bounds and avoid node and label collisions', function () {
  const nodes = Array.from({ length: 40 }, function (_, index) {
    return {
      id: String(index),
      x: 40 + (index % 8) * 24,
      y: 70 + Math.floor(index / 8) * 24,
      size: 4,
      degree: index,
      focused: index === 0,
    }
  })
  const labels = placeNodeLabels(nodes, { width: 280, height: 230 }, true, labelMetrics)
  assert.ok(labels.has('0'))
  const boxes = [...labels.values()]
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++)
      assert.ok(!boxesOverlap(boxes[i], boxes[j]))
  for (const box of boxes)
    assert.ok(
      box.left >= 4 && box.top >= 38 && box.right <= 276 && box.bottom <= 226,
    )
  assert.equal(
    placeNodeLabels(nodes, { width: 280, height: 230 }, false, labelMetrics).size,
    0,
  )
})

test('label placement avoids graph toolbars and snapshot stamps', function () {
  const nodes = [{ id: '34', x: 75, y: 52, size: 4, degree: 0 }]
  const stamp = { left: 14, right: 120, top: 47, bottom: 62 }
  const labels = placeNodeLabels(
    nodes,
    { width: 300, height: 200, reservedBoxes: [stamp] },
    true,
    labelMetrics,
  )
  for (const box of labels.values()) assert.ok(!boxesOverlap(box, stamp))
})
