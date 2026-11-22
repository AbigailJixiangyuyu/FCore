import { boundsOf } from './layoutReference.js'

export const locatedAccountColor = '#cc7048'
export const graphEdgeColor = '#888888'

function unorderedPairKey(u, v) {
  return JSON.stringify(u < v ? [u, v] : [v, u])
}

export function observedScene(frame, layout, { structure, anchor, location, rangeLabel, overview = false }) {
  if (!frame || (!overview && !structure && !location)) return null

  const members = new Set(structure?.members)
  const color = overview ? '#9cb0cb' : structure?.color || '#477be7'
  const qualifiedEdges = structure?.evidence?.qualified_edges
  const frequencies = qualifiedEdges && new Map(qualifiedEdges.map(function (edge) {
    return [unorderedPairKey(edge.u, edge.v), edge]
  }))
  const included = frame.nodes.filter(function (node) {
    return overview || (structure ? members.has(node.id) : node.id === location.accountId)
  })
  const degrees = new Map(included.map(node => [node.id, 0]))
  const edges = []
  for (const edge of frame.edges) {
    const { u, v } = edge
    if (!degrees.has(u) || !degrees.has(v)) continue
    const frequencyEvidence = frequencies?.get(unorderedPairKey(u, v))
    if (frequencies && !frequencyEvidence) continue
    edges.push({ ...edge, internal: !overview, frequencyEvidence })
    degrees.set(u, degrees.get(u) + 1)
    degrees.set(v, degrees.get(v) + 1)
  }
  const nodes = included.map(function (node) {
    const position = layout.positions[node.id]
    if (!position) throw new Error(`The layout has no position for node ${node.id}`)
    const matched = members.has(node.id)
    const focused = node.id === anchor
    const located = node.id === location?.accountId
    let size = overview ? 3.5 : 4.5
    if (focused) size = 6
    if (located) size = 8
    return {
      ...node,
      ...position,
      size,
      color: located ? locatedAccountColor : color,
      matched,
      focused: focused || located,
      located,
      anomaly: located && location.source === 'anomaly',
      degree: degrees.get(node.id),
      core_number: frame.core_numbers[node.id],
    }
  })
  return {
    nodes,
    edges: edges.map(function (edge) {
      return {
        ...edge,
        observation_scope: rangeLabel || frame.snapshot_id,
        aggregated: !!rangeLabel,
        size: overview ? 0.55 : 0.85,
        opacity: overview ? 0.25 : 0.32,
        color: graphEdgeColor,
      }
    }),
    bounds: overview ? layout.bounds : boundsOf(nodes),
  }
}

export const forecastNodeColors = {
  added: '#d64550',
  retained: '#315ed1',
  query: '#793dbd',
}

export function futureScene(prediction, layout) {
  if (!prediction?.members.length) return null
  const { members, account, edges, target_snapshot, comparison } = prediction
  const added = new Set(comparison?.added)
  const degrees = new Map(members.map(id => [id, 0]))
  for (const { u, v } of edges) {
    degrees.set(u, degrees.get(u) + 1)
    degrees.set(v, degrees.get(v) + 1)
  }
  const nodes = members.map(function (id) {
    const query = id === account
    const membership = added.has(id) ? 'added' : 'retained'
    return {
      id,
      ...layout.positions[id],
      size: query ? 7 : 4.5,
      color: forecastNodeColors[query ? 'query' : membership],
      query,
      focused: query,
      matched: true,
      degree: degrees.get(id),
    }
  })
  return {
    nodes,
    edges: edges.map(function ({ u, v, probability, currently_connected }) {
      return {
        id: `predicted:${unorderedPairKey(u, v)}`,
        u,
        v,
        predicted: true,
        probability,
        currently_connected,
        target_snapshot,
        size: 0.8 + probability,
        color: graphEdgeColor,
        opacity: 0.65,
      }
    }),
    bounds: boundsOf(nodes),
  }
}
