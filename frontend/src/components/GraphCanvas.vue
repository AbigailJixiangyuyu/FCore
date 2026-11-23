<script setup>
import { computed } from 'vue'

import { useGraphCanvas } from '../composables/useGraphCanvas.js'
import { formatCount } from '../domain/format.js'

const props = defineProps({
  scene: { type: Object, required: true },
  sceneKey: { type: String, required: true },
  layoutKey: { type: String, required: true },
  location: { type: Object, default: null },
  future: { type: Boolean, default: false },
  labels: { type: Boolean, default: true },
})
const emit = defineEmits(['select-account', 'zoom-change'])
const {
  container, overlayNodes, failure, tooltip, hovered,
  hoveredEdge, communityHovered, initialize, keyboard, setHover, zoom, fit,
} = useGraphCanvas(props, emit)
defineExpose({ zoom, fit })

const accessibleSummary = computed(function () {
  const vertices = formatCount(props.scene.nodes.length, 'vertex', 'vertices')
  const edges = formatCount(props.scene.edges.length, props.future ? 'predicted edge' : 'undirected edge')
  return `${vertices}, ${edges}. Use the arrow keys to move focus and Enter to select a vertex.`
})
</script>

<template>
  <div
    class="graph-renderer"
    :class="{ 'community-hover': communityHovered }"
    tabindex="0"
    role="application"
    :data-node-count="scene.nodes.length"
    :data-edge-count="scene.edges.length"
    :data-scene-key="sceneKey"
    :data-layout-key="layoutKey"
    :data-hovered-account="hovered"
    :data-hovered-edge="hoveredEdge"
    :aria-label="accessibleSummary"
    @keydown="keyboard"
    @blur="setHover()"
  >
    <div ref="container" class="sigma-container"></div>
    <div v-if="failure" class="graph-failure" role="alert">
      <p>{{ failure }}</p>
      <p class="helper">This graph requires WebGL 2.</p>
      <el-button plain @click="initialize">Retry</el-button>
    </div>
    <div v-else class="graph-overlays" aria-hidden="true">
      <span
        v-for="node in overlayNodes"
        :key="node.id"
        class="account-hit"
        :class="{
          focused: node.focused,
          hovered: node.hovered,
        }"
        :style="{ left: `${node.x}px`, top: `${node.y}px` }"
        :data-account="node.id"
        :data-matched="node.matched"
        :data-located="!!node.located"
        :data-anomaly="!!node.anomaly"
        :data-x="node.x.toFixed(2)"
        :data-y="node.y.toFixed(2)"
        :data-world-x="node.worldX"
        :data-world-y="node.worldY"
      >
        <span
          v-if="node.labelBox"
          class="account-label"
          :style="{
            left: `${node.labelBox.left - node.x}px`,
            top: `${node.labelBox.top - node.y}px`,
          }"
          >{{ node.id }}</span
        >
      </span>
    </div>
    <div
      v-if="tooltip"
      class="graph-tooltip"
      :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
    >
      {{ tooltip.text }}
    </div>
  </div>
</template>
