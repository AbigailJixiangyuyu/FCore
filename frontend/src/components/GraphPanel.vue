<script setup>
import { computed, ref, shallowRef, watch } from 'vue'
import { DEFAULT_GRAPH_ZOOM } from '../composables/useGraphCanvas.js'
import { useGraphLayout } from '../composables/useGraphLayout.js'
import { usePeriodicCommunity } from '../composables/workbench/usePeriodicCommunity.js'
import { currentAlgorithms, useWorkbench } from '../composables/workbenchContext.js'
import { formatCount } from '../domain/format.js'
import {
  forecastNodeColors, futureScene, graphEdgeColor, locatedAccountColor, observedScene,
} from '../graph/scene.js'
import GraphCanvas from './GraphCanvas.vue'
import QueryState from './QueryState.vue'

const workbench = useWorkbench()
const {
  store,
  context,
  ready,
  snapshot,
  present,
  snapshotQuery,
  queryResult,
  currentWindow,
  layoutReference,
  patternResult,
  patternResponse,
  selected,
  anomalyResults,
  matchingPrediction,
  activePredictionModel,
  predictionRequest,
  predictionMessage,
  focusAccount,
} = workbench
const { periodic, communityFrame, pendingEndpoint } = usePeriodicCommunity(workbench)
const canvas = ref(null)
const zoom = ref(DEFAULT_GRAPH_ZOOM)
const labels = ref(true)
const { layout, loading, error, retry } = useGraphLayout(
  layoutReference,
  present,
  context,
  ready,
)
const future = computed(function () {
  return store.stage === 'future'
})
const overview = computed(function () {
  if (!store.analysisRunId) return true
  return store.stage === 'history' && store.pattern === 'temporal_core' && !selected.value
})
const showPrediction = computed(() => future.value && !overview.value)
const usesCurrentWindow = computed(function () {
  return store.stage === 'present' && store.currentAlgorithm === 'tccs'
})
const rangeLabel = computed(function () {
  if (store.stage === 'history') return store.historyRangeLabel
  return currentWindow.value ? store.currentWindowLabel : ''
})
const periodicStamp = computed(function () {
  const view = periodic.value
  if (!view || view.state === null) return ''
  const status = view.state === 1 ? 'formed' : 'absent'
  return `${view.end} · ${view.k}-core ${status}`
})
const location = computed(function () {
  if (store.stage !== 'present') return null
  const request = store.graphLocation
  if (request?.source === 'anomaly' && !anomalyResults.value.length) return null
  return request
})
const standaloneLocation = computed(function () {
  if (overview.value) return null
  const request = location.value
  if (request?.source === 'anomaly' && !selected.value?.members.includes(request.accountId))
    return request
  return null
})
const graphStamp = computed(function () {
  if (overview.value) {
    if (future.value) return 'S12 · Observed graph'
    return `${rangeLabel.value || 'S12'} · Full graph`
  }
  if (showPrediction.value) {
    const result = matchingPrediction.value
    return result
      ? `${result.target_snapshot} / PREDICTED · Threshold ${result.threshold.toFixed(2)}`
      : `${store.futureSnapshotId} / PREDICTED`
  }
  if (standaloneLocation.value) return 'S12 / OBSERVED'
  if (periodicStamp.value) return periodicStamp.value
  if (rangeLabel.value) return `${rangeLabel.value} / AGGREGATED`
  return 'S12 / OBSERVED'
})
const observedQuery = computed(function () {
  if (overview.value || standaloneLocation.value) return snapshotQuery.value
  if (store.stage === 'history') {
    if (!selected.value) return patternResult
    return pendingEndpoint.value || snapshotQuery.value
  }
  return !selected.value || usesCurrentWindow.value ? queryResult : snapshotQuery.value
})
const scene = computed(function () {
  if (!layout.value) return null
  if (overview.value) {
    return observedScene(snapshot.value, layout.value, {
      overview: true,
      location: location.value,
      rangeLabel: rangeLabel.value,
    })
  }
  if (showPrediction.value) return futureScene(matchingPrediction.value, layout.value)
  if (standaloneLocation.value)
    return observedScene(snapshot.value, layout.value, { location: standaloneLocation.value })

  const structure = selected.value
  if (!structure) return null
  if (periodic.value) {
    return observedScene(communityFrame.value, layout.value, {
      structure,
      anchor: store.historyAnchor,
    })
  }
  const frame = usesCurrentWindow.value ? currentWindow.value : snapshot.value
  let anchor = store.currentAnchor
  if (store.stage === 'history')
    anchor = store.pattern === 'burst' ? store.historyParameters.account : store.historyAnchor
  return observedScene(frame, layout.value, {
    structure,
    anchor,
    location: location.value,
    rangeLabel: rangeLabel.value,
  })
})
const sceneKey = computed(function () {
  const base = `${store.datasetId}:${layout.value?.key || 'pending'}`
  if (overview.value) return `overview:${base}`
  if (showPrediction.value) {
    const { account, k, horizon } = store.futureParameters
    const identity = [account, k, horizon, activePredictionModel.value?.model_version]
    return `future:${base}:${JSON.stringify(identity)}`
  }
  if (standaloneLocation.value) return `anomaly:${base}:${standaloneLocation.value.accountId}`
  return `structure:${base}:${store.stage}:${selected.value?.membership_hash}`
})
const retainedScene = shallowRef(null)
watch(
  [scene, sceneKey],
  function ([nextScene, key], previous) {
    if (nextScene || key !== previous?.[1]) retainedScene.value = nextScene
  },
  { immediate: true },
)
const legend = computed(function () {
  if (!scene.value?.nodes.length) return []
  if (showPrediction.value) {
    return [
      { label: 'Added nodes', color: forecastNodeColors.added },
      { label: 'Retained nodes', color: forecastNodeColors.retained },
      { label: 'Query node q', color: forecastNodeColors.query },
    ]
  }
  const items = []
  if (!overview.value && !standaloneLocation.value) {
    const structure = selected.value
    const label = structure.method === currentAlgorithms.pkmc.method
      ? `Global ${structure.parameters.max_core}-core`
      : structure.label
    items.push({ label, color: structure.color })
  }
  const request = location.value
  if (request) items.push({ label: `Node ${request.accountId}`, color: locatedAccountColor })
  return items
})
const emptyText = computed(function () {
  if (overview.value) return 'No nodes in this range'
  if (standaloneLocation.value) return 'This node is absent from the current snapshot'
  if (!selected.value) return patternResponse.value?.message || 'No matching community'
  if (periodic.value?.outsideSearch) return 'This snapshot is outside the mining range'
  if (periodic.value?.state === 0) return `No ${periodic.value.k}-core formed in this snapshot`
  if (periodic.value?.state === null) return 'No periodic community status for this snapshot'
  return 'No community members in this range'
})
</script>

<template>
  <section class="panel graph-panel" aria-label="Graph exploration">
    <div class="panel-heading">
      <h2><span class="panel-number">03</span>Graph</h2>
      <span class="count-chip">{{
        scene
          ? `${formatCount(scene.nodes.length, 'node')} · ${formatCount(scene.edges.length, showPrediction ? 'predicted edge' : 'edge')}`
          : 'No graph data'
      }}</span>
    </div>
    <div
      class="graph-stage"
      :data-layout-state="error ? 'error' : layout ? 'ready' : 'loading'"
    >
      <span
        class="graph-stamp"
        :class="{ 'periodic-stamp': periodicStamp, 'is-formed': periodic?.state === 1 }"
        aria-live="polite"
      >{{ graphStamp }}</span>
      <div class="graph-toolbar" role="group" aria-label="Graph display tools">
        <template v-if="standaloneLocation">
          <el-button text @click="store.graphLocation = null">Back to Community</el-button>
          <span class="tool-divider"></span>
        </template>
        <el-button text aria-label="Zoom out" @click="canvas?.zoom(1.25)"
          >−</el-button
        >
        <output aria-label="Zoom level">{{ zoom }}%</output>
        <el-button text aria-label="Zoom in" @click="canvas?.zoom(0.8)"
          >＋</el-button
        >
        <span class="tool-divider"></span>
        <el-button text @click="canvas?.fit()">Fit</el-button>
        <el-button text :aria-pressed="labels" @click="labels = !labels"
          >Labels</el-button
        >
      </div>
      <GraphCanvas
        v-if="retainedScene?.nodes.length"
        :key="sceneKey"
        ref="canvas"
        :class="{ 'scene-hidden': !scene }"
        :inert="!scene"
        :aria-hidden="!scene"
        :scene="retainedScene"
        :scene-key="sceneKey"
        :future="showPrediction"
        :labels="labels"
        :layout-key="layout?.key || ''"
        :location="location"
        @select-account="focusAccount"
        @zoom-change="zoom = $event"
      />
      <div v-if="showPrediction && !matchingPrediction?.members.length" class="prediction-empty">
        <QueryState v-if="predictionRequest" :query="predictionRequest" />
        <el-empty v-else :image-size="52" :description="predictionMessage" />
      </div>
      <div v-else-if="layoutReference.isError.value" class="graph-failure">
        <QueryState :query="layoutReference" />
      </div>
      <div v-else-if="error" class="graph-failure" role="alert">
        <p>Graph layout failed. {{ error }}</p>
        <el-button plain @click="retry">Retry</el-button>
      </div>
      <p v-else-if="loading || !layout" class="request-state" role="status">
        <span class="loading-dot"></span>Computing layout…
      </p>
      <div v-else-if="!showPrediction && !scene?.nodes.length" class="prediction-empty">
        <QueryState :query="observedQuery" empty :empty-text="emptyText" />
      </div>
    </div>
    <div v-if="scene?.nodes.length" class="graph-bottom">
      <div class="graph-legend">
        <span v-for="item in legend" :key="item.label"
          ><i class="group-dot" :style="{ '--group': item.color }"></i
          >{{ item.label }}</span
        >
        <span v-if="scene.edges.length">
          <i
            class="legend-line"
            :class="{ predicted: showPrediction }"
            :style="{ color: graphEdgeColor }"
          ></i>
          {{ showPrediction ? 'Link probability' : 'Observed edges' }}
        </span>
      </div>
    </div>
  </section>
</template>
