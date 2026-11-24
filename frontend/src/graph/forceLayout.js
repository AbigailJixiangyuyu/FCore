import { UndirectedGraph } from 'graphology'
import forceAtlas2 from 'graphology-layout-forceatlas2'
import noverlap from 'graphology-layout-noverlap'
import { boundsOf, compareIds, LAYOUT_VERSION } from './layoutReference.js'

function seededRandom(seed) {
  let state = seed >>> 0
  return function () {
    state += 0x6d2b79f5
    let value = Math.imul(state ^ (state >>> 15), 1 | state)
    value ^= value + Math.imul(value ^ (value >>> 7), 61 | value)
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296
  }
}

function componentsOf(graph) {
  const remaining = new Set(graph.nodes())
  const components = []
  for (const start of graph.nodes()) {
    if (!remaining.delete(start)) continue
    const members = [start]
    for (let index = 0; index < members.length; index++) {
      for (const neighbor of graph.neighbors(members[index]).sort(compareIds)) {
        if (remaining.delete(neighbor)) members.push(neighbor)
      }
    }
    components.push(members.sort(compareIds))
  }
  return components.sort(function (a, b) {
    return b.length - a.length || compareIds(a[0], b[0])
  })
}

function layoutComponent(members, graph, random) {
  const component = new UndirectedGraph()
  const columns = Math.ceil(Math.sqrt(members.length))
  members.forEach(function (id, index) {
    component.addNode(id, {
      x: 12 * (index % columns) + random(),
      y: 12 * Math.floor(index / columns) + random(),
      size: 1,
    })
  })
  graph.forEachEdge(function (key, attributes, source, target) {
    if (component.hasNode(source) && component.hasNode(target))
      component.addEdge(source, target)
  })
  forceAtlas2.assign(component, {
    iterations: 500,
    settings: {
      linLogMode: true,
      adjustSizes: true,
      edgeWeightInfluence: 0,
      scalingRatio: 10,
      gravity: 1,
      slowDown: 1,
      barnesHutOptimize: false,
    },
  })
  const extent = boundsOf(
    component.nodes().map(function (id) {
      return component.getNodeAttributes(id)
    }),
    0,
  )
  const span = Math.max(extent.x[1] - extent.x[0], extent.y[1] - extent.y[0], 1)
  const scale = Math.max(100, Math.sqrt(members.length) * 32) / span
  component.forEachNode(function (id, attributes) {
    component.mergeNodeAttributes(id, {
      x: (attributes.x - extent.x[0]) * scale,
      y: (attributes.y - extent.y[0]) * scale,
      size: 4,
    })
  })
  // Distinct seeded starting positions also prevent Noverlap's random tie jitter.
  const occupied = new Set()
  component.forEachNode(function (id, attributes) {
    let key = `${Math.fround(attributes.x)}:${Math.fround(attributes.y)}`
    while (occupied.has(key)) {
      attributes.x += 0.01 + random() * 0.01
      attributes.y += 0.01 + random() * 0.01
      key = `${Math.fround(attributes.x)}:${Math.fround(attributes.y)}`
    }
    occupied.add(key)
  })
  noverlap.assign(component, {
    maxIterations: 500,
    settings: { margin: 2, ratio: 1, gridSize: 10, speed: 3 },
  })
  const positions = Object.fromEntries(
    component.nodes().map(function (id) {
      const { x, y } = component.getNodeAttributes(id)
      if (!Number.isFinite(x) || !Number.isFinite(y))
        throw new Error('The graph layout returned invalid coordinates')
      return [id, { x, y }]
    }),
  )
  return { positions, bounds: boundsOf(positions, 12) }
}

function scatterIsolates(isolates, positions, edges, random) {
  if (!isolates.length) return
  const cellSize = 2
  const cellAt = (x, y) => `${Math.floor(x / cellSize)},${Math.floor(y / cellSize)}`
  const occupied = new Set()
  function reserveSpace(x, y, margin) {
    const lastCol = Math.floor((x + margin) / cellSize)
    const lastRow = Math.floor((y + margin) / cellSize)
    for (let col = Math.floor((x - margin) / cellSize); col <= lastCol; col++) {
      const dx = Math.max(col * cellSize - x, x - (col + 1) * cellSize, 0)
      for (let row = Math.floor((y - margin) / cellSize); row <= lastRow; row++) {
        const dy = Math.max(row * cellSize - y, y - (row + 1) * cellSize, 0)
        if (dx * dx + dy * dy <= margin * margin) occupied.add(`${col},${row}`)
      }
    }
  }
  const connected = Object.values(positions)
  for (const point of connected) reserveSpace(point.x, point.y, 12)

  // Reserve cells along transfers so an isolated vertex appears in open space.
  for (const [u, v] of edges) {
    const a = positions[u]
    const dx = positions[v].x - a.x
    const dy = positions[v].y - a.y
    const steps = Math.ceil(Math.hypot(dx, dy) / cellSize)
    for (let i = 1; i < steps; i++) {
      reserveSpace(a.x + dx * i / steps, a.y + dy * i / steps, 2.5)
    }
  }

  const { x, y } = boundsOf(positions, 0)
  const center = { x: (x[0] + x[1]) / 2, y: (y[0] + y[1]) / 2 }
  // Give narrow graphs and graphs made entirely of isolates a two-dimensional area.
  const minimumSpan = 32 * Math.sqrt(isolates.length)
  const width = Math.max(minimumSpan, (x[1] - x[0]) * 0.85)
  const height = Math.max(minimumSpan, (y[1] - y[0]) * 0.85)
  for (const [id] of isolates) {
    let scale = 0.72
    for (let attempt = 0; ; attempt++) {
      // Search the interior first, then widen the search if it is already full.
      if (attempt > 0 && attempt % 128 === 0) scale *= 1.4
      const point = {
        x: center.x + width * scale * (random() - 0.5),
        y: center.y + height * scale * (random() - 0.5),
      }
      const cell = cellAt(point.x, point.y)
      if (occupied.has(cell)) continue
      positions[id] = point
      reserveSpace(point.x, point.y, 12)
      break
    }
  }
}

export function computeLayout(reference) {
  const graph = new UndirectedGraph()
  for (const id of reference.nodes) graph.addNode(id)
  for (const [source, target] of reference.edges) graph.addEdge(source, target)
  const random = seededRandom(20261116)
  const components = componentsOf(graph)
  const blocks = components
    .filter(function (members) {
      return members.length > 1
    })
    .map(function (members) {
      return layoutComponent(members, graph, random)
    })
  const positions = Object.create(null)
  const totalArea = blocks.reduce(function (area, block) {
    return (
      area +
      (block.bounds.x[1] - block.bounds.x[0]) *
        (block.bounds.y[1] - block.bounds.y[0])
    )
  }, 0)
  const shelfWidth = Math.max(
    Math.sqrt(totalArea) * 1.4,
    ...blocks.map(function (block) {
      return block.bounds.x[1] - block.bounds.x[0]
    }),
    100,
  )
  let cursorX = 0
  let cursorY = 0
  let rowHeight = 0
  for (const block of blocks) {
    const width = block.bounds.x[1] - block.bounds.x[0]
    const height = block.bounds.y[1] - block.bounds.y[0]
    if (cursorX > 0 && cursorX + width > shelfWidth) {
      cursorX = 0
      cursorY += rowHeight + 20
      rowHeight = 0
    }
    for (const [id, point] of Object.entries(block.positions)) {
      positions[id] = {
        x: point.x - block.bounds.x[0] + cursorX,
        y: point.y - block.bounds.y[0] + cursorY,
      }
    }
    cursorX += width + 20
    rowHeight = Math.max(rowHeight, height)
  }
  const isolated = components.filter(function (members) {
    return members.length === 1
  })
  scatterIsolates(isolated, positions, reference.edges, random)
  return { positions, bounds: boundsOf(positions), version: LAYOUT_VERSION }
}
