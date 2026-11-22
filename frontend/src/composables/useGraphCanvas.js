import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { formatCount } from '../domain/format.js'
import { probabilityLabel } from './workbenchContext.js'
import { applyCommunityHover } from '../graph/hover.js'
import { measureNodeLabels, placeNodeLabels } from '../graph/labels.js'
import { loadSigmaRenderer } from '../graph/sigmaRenderer.js'

export const DEFAULT_GRAPH_ZOOM = 150

export function useGraphCanvas(props, emit) {
  const container = ref(null)
  const overlayNodes = ref([])
  const failure = ref('')
  const tooltip = ref(null)
  const hovered = ref('')
  const hoveredEdge = ref('')
  const communityHovered = ref(false)
  let renderer = null
  let observer = null
  let disposed = false
  let sigma = null
  let keyboardIndex = -1
  let labelMetrics

  function updateOverlays() {
    if (!renderer || disposed) return
    const dimensions = renderer.getDimensions()
    const origin = container.value.getBoundingClientRect()
    dimensions.reservedBoxes = [
      ...container.value.closest('.graph-stage').querySelectorAll(
        '.graph-toolbar, .graph-stamp',
      ),
    ].map(function (element) {
      const box = element.getBoundingClientRect()
      return {
        left: box.left - origin.left,
        right: box.right - origin.left,
        top: box.top - origin.top,
        bottom: box.bottom - origin.top,
      }
    })
    const nodes = props.scene.nodes.map(function (node) {
      return {
        ...node,
        worldX: node.x,
        worldY: node.y,
        ...renderer.graphToViewport(node),
        hovered: hovered.value === node.id,
      }
    })
    const labels = placeNodeLabels(nodes, dimensions, props.labels, labelMetrics)
    overlayNodes.value = nodes.map(function (node) {
      return { ...node, labelBox: labels.get(node.id) }
    })
    emit('zoom-change', Math.round(100 / renderer.getCamera().getState().ratio))
  }
  
  function setHover(account = '', edgeId = '') {
    if (!renderer) return
    hovered.value = account
    hoveredEdge.value = edgeId
    communityHovered.value = applyCommunityHover(
      renderer.getGraph(),
      account,
      edgeId,
    )
    renderer.refresh()
  }
  
  function updateScene() {
    if (!renderer) return
    tooltip.value = null
    hovered.value = ''
    hoveredEdge.value = ''
    communityHovered.value = false
    renderer.setGraph(sigma.graph(props.scene))
    renderer.setCustomBBox(props.scene.bounds)
    renderer.refresh()
  }
  function zoom(factor) {
    if (!renderer) return
    const camera = renderer.getCamera()
    camera.animate(
      { ratio: Math.max(0.15, Math.min(3, camera.getState().ratio * factor)) },
      { duration: 180 },
    )
  }
  function fit() {
    renderer?.getCamera().reset({ duration: 180 })
  }
  function locate(account) {
    if (!renderer || !account || !renderer.getGraph().hasNode(account)) return
    const point = renderer.graphToFramedGraph(
      renderer.getGraph().getNodeAttributes(account),
    )
    renderer
      .getCamera()
      .animate(
        {
          x: point.x,
          y: point.y,
          ratio: Math.min(0.8, renderer.getCamera().getState().ratio),
        },
        { duration: 220 },
      )
  }
  function keyboard(event) {
    if (!renderer || !props.scene.nodes.length) return
    if (event.key === 'Enter' || event.key === ' ') {
      if (keyboardIndex < 0 || keyboardIndex >= props.scene.nodes.length) keyboardIndex = 0
      emit('select-account', props.scene.nodes[keyboardIndex].id)
    } else if (event.key.startsWith('Arrow')) {
      const forward = event.key === 'ArrowRight' || event.key === 'ArrowDown'
      keyboardIndex =
        (keyboardIndex + (forward ? 1 : -1) + props.scene.nodes.length) %
        props.scene.nodes.length
      const account = props.scene.nodes[keyboardIndex].id
      setHover(account)
      locate(account)
    } else if (event.key === 'Escape') {
      setHover()
      tooltip.value = null
    } else return
    event.preventDefault()
  }
  function showTooltip(text, event) {
    const dimensions = renderer.getDimensions()
    tooltip.value = {
      text,
      x: Math.max(8, Math.min(event.x + 12, dimensions.width - 268)),
      y: Math.min(event.y + 18, dimensions.height - 75),
    }
  }

  function bindEvents() {
    renderer.on('clickNode', function ({ node }) {
      emit('select-account', node)
    })
    renderer.on('enterNode', function ({ node, event }) {
      setHover(node)
      const attributes = renderer.getGraph().getNodeAttributes(node)
      showTooltip(
        `${node}${attributes.core_number !== undefined ? ` · Coreness ${attributes.core_number}` : ''}${attributes.query ? ' · Query node q' : ''}`,
        event,
      )
    })
    renderer.on('leaveNode', function () {
      setHover()
      tooltip.value = null
    })
    renderer.on('enterEdge', function ({ edge, event }) {
      setHover('', edge)
      const attributes = renderer.getGraph().getEdgeAttributes(edge)
      let text = `${attributes.u} — ${attributes.v}`
      if (attributes.predicted)
        text += ` · ${attributes.target_snapshot} link probability ${probabilityLabel(attributes.probability)} · ${attributes.currently_connected ? 'Connected' : 'Not connected'} in S12`
      else {
        const scope = attributes.aggregated
          ? `${attributes.observation_scope} total`
          : attributes.observation_scope
        text += ` · ${scope} · ${formatCount(attributes.transaction_count, 'interaction')}`
        const witness = attributes.frequencyEvidence
        if (witness)
          text += ` · Historical frequency ${witness.frequency.toFixed(3)} · ${witness.witness_start_snapshot_id}–${witness.witness_end_snapshot_id}`
      }
      showTooltip(text, event)
    })
    renderer.on('leaveEdge', function () {
      setHover()
      tooltip.value = null
    })
    renderer.on('afterRender', updateOverlays)
  }

  async function initialize() {
    failure.value = ''
    renderer?.kill()
    renderer = null
    try {
      sigma = await loadSigmaRenderer()
      if (disposed) return
      labelMetrics = measureNodeLabels(container.value)
      renderer = sigma.create(sigma.graph(props.scene), container.value, props.future)
      renderer.getCamera().setState({ ratio: 100 / DEFAULT_GRAPH_ZOOM })
      bindEvents()
      updateScene()
      locate(props.location?.accountId)
    } catch (error) {
      failure.value = `Could not load graph. ${error.message}`
      renderer?.kill()
      renderer = null
    }
  }

  onMounted(function () {
    observer = new ResizeObserver(function () {
      renderer?.resize()
    })
    observer.observe(container.value)
    initialize()
  })
  watch(function () {
    return props.scene
  }, updateScene)
  watch(function () {
    return props.labels
  }, updateOverlays)
  watch(
    () => props.location,
    location => locate(location?.accountId),
    { flush: 'post' },
  )
  onBeforeUnmount(function () {
    disposed = true
    observer?.disconnect()
    renderer?.kill()
    renderer = null
  })

  return {
    container, overlayNodes, failure, tooltip, hovered,
    hoveredEdge, communityHovered, initialize, keyboard, setHover, zoom, fit,
  }
}
