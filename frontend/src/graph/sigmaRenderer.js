function sceneGraph(UndirectedGraph, scene) {
  const graph = new UndirectedGraph({ allowSelfLoops: false })
  for (const node of scene.nodes)
    graph.addNode(node.id, {
      ...node,
      label: node.id,
      displayOpacity: 1,
      displayDepth: 'nodes',
    })
  for (const edge of scene.edges)
    graph.addUndirectedEdgeWithKey(edge.id, edge.u, edge.v, {
      ...edge,
      displayOpacity: edge.opacity,
      displayDepth: 'edges',
    })
  return graph
}

export async function loadSigmaRenderer() {
  const [sigma, graphology, rendering] = await Promise.all([
    import('sigma'),
    import('graphology'),
    import('sigma/rendering'),
  ])
  return {
    graph(scene) {
      return sceneGraph(graphology.UndirectedGraph, scene)
    },
    create(graph, container, future) {
      return new sigma.default(graph, container, {
        settings: {
          renderLabels: false,
          renderEdgeLabels: false,
          enableEdgeEvents: true,
          stagePadding: 28,
          minCameraRatio: 0.15,
          maxCameraRatio: 3,
          enableCameraRotation: false,
          enableCameraMouseRotation: false,
          autoRescaleContent: 'nodes',
          itemSizesReference: 'screen',
          enableNodeDrag: false,
        },
        primitives: {
          edges: {
            paths: [rendering.pathLine()],
            layers: [
              future
                ? rendering.layerDashed({
                    dashSize: { value: 16 },
                    gapSize: { value: 11 },
                    solidExtremities: true,
                  })
                : rendering.layerPlain(),
            ],
          },
        },
        styles: {
          nodes: [
            sigma.DEFAULT_STYLES.nodes,
            {
              size: { attribute: 'size' },
              color: { attribute: 'color' },
              opacity: { attribute: 'displayOpacity' },
              depth: { attribute: 'displayDepth' },
              backdropVisibility: 'hidden',
              label: '',
            },
          ],
          edges: [
            sigma.DEFAULT_STYLES.edges,
            {
              path: 'straight',
              size: { attribute: 'size' },
              opacity: { attribute: 'displayOpacity' },
              depth: { attribute: 'displayDepth' },
              color: { attribute: 'color' },
              label: '',
            },
          ],
        },
      })
    },
  }
}
