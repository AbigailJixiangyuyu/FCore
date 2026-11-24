export const LAYOUT_VERSION = 'history-fa2-linlog-500-noverlap-v3'

export function compareIds(a, b) {
  return a < b ? -1 : Number(a > b)
}

export function normalizeReference(frame, current = frame) {
  const nodes = [
    ...new Set(
      [...frame.nodes, ...current.nodes].map(function (node) {
        return node.id
      }),
    ),
  ].sort(compareIds)
  const known = new Set(nodes)
  const pairs = new Set()
  const referenceEdges = frame.nodes.length ? frame.edges : current.edges
  for (const edge of referenceEdges) {
    const { u, v } = edge
    if (!known.has(u) || !known.has(v))
      throw new Error('The layout reference contains an edge with an unknown endpoint')
    if (u === v) continue
    pairs.add(JSON.stringify([u, v].sort(compareIds)))
  }
  return {
    nodes,
    edges: [...pairs].sort().map(function (pair) {
      return JSON.parse(pair)
    }),
  }
}

export async function referenceFingerprint(reference) {
  const bytes = new TextEncoder().encode(JSON.stringify(reference))
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return [...new Uint8Array(digest)]
    .map(function (byte) {
      return byte.toString(16).padStart(2, '0')
    })
    .join('')
}

export function boundsOf(positions, padding = 24) {
  const points = Object.values(positions)
  if (!points.length) return { x: [-50, 50], y: [-50, 50] }
  const xs = points.map(function (point) {
    return point.x
  })
  const ys = points.map(function (point) {
    return point.y
  })
  return {
    x: [Math.min(...xs) - padding, Math.max(...xs) + padding],
    y: [Math.min(...ys) - padding, Math.max(...ys) + padding],
  }
}
