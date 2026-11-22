export function applyCommunityHover(graph, account = '', edgeId = '') {
  const members = new Set(
    graph.filterNodes(function (_, attributes) {
      return attributes.matched
    }),
  )
  function isCommunityEdge(source, target, attributes) {
    return attributes.internal !== false && members.has(source) && members.has(target)
  }
  let active = members.has(account)
  if (edgeId && graph.hasEdge(edgeId)) {
    const [source, target] = graph.extremities(edgeId)
    active = isCommunityEdge(source, target, graph.getEdgeAttributes(edgeId))
  }
  graph.forEachNode(function (id) {
    const highlighted = active && members.has(id)
    graph.mergeNodeAttributes(id, {
      displayOpacity: active && !highlighted ? 0.25 : 1,
      displayDepth: highlighted ? 'topNodes' : 'nodes',
    })
  })
  graph.forEachEdge(function (id, attributes, source, target) {
    const highlighted = active && isCommunityEdge(source, target, attributes)
    let opacity = attributes.opacity
    if (active) opacity = highlighted ? 0.85 : 0.045
    graph.mergeEdgeAttributes(id, {
      displayOpacity: opacity,
      displayDepth: highlighted ? 'topEdges' : 'edges',
    })
  })
  return active
}
