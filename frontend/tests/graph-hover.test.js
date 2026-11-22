import assert from 'node:assert/strict'
import { test } from 'node:test'
import { UndirectedGraph } from 'graphology'
import { applyCommunityHover } from '../src/graph/hover.js'
import { observedScene } from '../src/graph/scene.js'

function communityGraph() {
  const graph = new UndirectedGraph()
  for (const id of ['a', 'b', 'c', 'isolated', 'x', 'y'])
    graph.addNode(id, { matched: !['x', 'y'].includes(id) })
  for (const [u, v] of [
    ['a', 'b'],
    ['b', 'c'],
    ['a', 'x'],
    ['x', 'y'],
  ])
    graph.addUndirectedEdgeWithKey(`${u}:${v}`, u, v, {
      opacity: u === 'x' || v === 'x' ? 0.15 : 0.32,
    })
  return graph
}

test('node hover emphasizes the complete selected community, including nonincident edges and isolated members', function () {
  const graph = communityGraph()
  assert.equal(applyCommunityHover(graph, 'a'), true)
  assert.equal(graph.getNodeAttribute('isolated', 'displayOpacity'), 1)
  assert.equal(graph.getNodeAttribute('c', 'displayDepth'), 'topNodes')
  assert.equal(graph.getNodeAttribute('x', 'displayOpacity'), 0.25)
  assert.equal(graph.getEdgeAttribute('b:c', 'displayOpacity'), 0.85)
  assert.equal(graph.getEdgeAttribute('a:x', 'displayOpacity'), 0.045)
  assert.equal(graph.getEdgeAttribute('x:y', 'displayDepth'), 'edges')

  assert.equal(applyCommunityHover(graph), false)
  graph.forEachNode(function (_, attributes) {
    assert.equal(attributes.displayOpacity, 1)
    assert.equal(attributes.displayDepth, 'nodes')
  })
  graph.forEachEdge(function (_, attributes) {
    assert.equal(attributes.displayOpacity, attributes.opacity)
    assert.equal(attributes.displayDepth, 'edges')
  })
})

test('internal edge hover emphasizes the same whole community; background and crossing edges do not create a different selection', function () {
  const graph = communityGraph()
  applyCommunityHover(graph, 'a')
  const fromNode = graph.export()
  assert.equal(applyCommunityHover(graph, '', 'b:c'), true)
  assert.deepEqual(graph.export(), fromNode)

  for (const [account, edge] of [['x', ''], ['', 'a:x'], ['', 'x:y']]) {
    assert.equal(applyCommunityHover(graph, account, edge), false)
    graph.forEachEdge(function (_, attributes) {
      assert.equal(attributes.displayOpacity, attributes.opacity)
    })
  }
  graph.forEachNode(function (id) {
    graph.setNodeAttribute(id, 'matched', false)
  })
  assert.equal(applyCommunityHover(graph, 'a'), false)
})

test('prediction hover retains every member and its predicted edges', function () {
  const graph = new UndirectedGraph()
  for (const id of ['source', 'b', 'c', 'filtered'])
    graph.addNode(id, { matched: true })
  for (const [target, probability] of [['b', 0.5], ['c', 0.3]])
    graph.addUndirectedEdgeWithKey(target, 'source', target, {
      probability,
      predicted: true,
      opacity: 0.8,
    })
  assert.equal(applyCommunityHover(graph, 'b'), true)
  assert.equal(graph.getNodeAttribute('filtered', 'displayOpacity'), 1)
  assert.equal(graph.getEdgeAttribute('c', 'displayOpacity'), 0.85)
  assert.equal(graph.getEdgeAttribute('b', 'probability'), 0.5)
  assert.equal(graph.getEdgeAttribute('c', 'probability'), 0.3)
  assert.equal(graph.size, 2)
})

test('frequency core uses only qualified relationships in the visible range', function () {
  const nodes = ['a', 'b', 'c', 'x'].map(function (id) {
    return { id }
  })
  const frame = {
    nodes,
    core_numbers: {},
    snapshot_id: 'S04:S05',
    edges: [['a', 'b'], ['b', 'c'], ['c', 'x']].map(function ([u, v]) {
      return { id: `${u}:${v}`, u, v, transaction_count: 4 }
    }),
  }
  const layout = {
    positions: Object.fromEntries(nodes.map(function ({ id }, index) {
      return [id, { x: index, y: index }]
    })),
  }
  const witness = { u: 'a', v: 'b', frequency: 0.8 }
  const structure = {
    members: ['a', 'b', 'c'],
    evidence: { qualified_edges: [witness, { u: 'a', v: 'c', frequency: 1 }] },
  }
  const scene = observedScene(frame, layout, { structure })
  assert.deepEqual(scene.nodes.map(node => node.id), ['a', 'b', 'c'])
  assert.deepEqual(scene.edges.map(edge => edge.id), ['a:b'])
  assert.equal(scene.edges[0].frequencyEvidence, witness)

  const graph = new UndirectedGraph()
  for (const node of scene.nodes) graph.addNode(node.id, node)
  for (const edge of scene.edges)
    graph.addUndirectedEdgeWithKey(edge.id, edge.u, edge.v, edge)
  assert.equal(applyCommunityHover(graph, '', 'b:c'), false)
  assert.equal(applyCommunityHover(graph, 'c'), true)
  assert.equal(graph.getEdgeAttribute('a:b', 'displayDepth'), 'topEdges')
  assert.equal(graph.hasEdge('b:c'), false)
})
