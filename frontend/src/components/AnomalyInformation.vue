<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useWorkbench } from '../composables/workbenchContext.js'
import QueryState from './QueryState.vue'

const { store, anomalyQuery, anomalyResponse, anomalyResults, selectAnomaly } = useWorkbench()
const scoreEvidence = ref(null)
const selectedAccount = computed(function () {
  return anomalyResults.value.find(function (item) {
    return item.account_id === store.anomalyAccount
  })
})
const inspected = computed(() => selectedAccount.value ?? anomalyResults.value[0])

watch(selectedAccount, async function (account) {
  if (!account) return
  await nextTick()
  scoreEvidence.value?.scrollIntoView({ block: 'nearest' })
})
</script>

<template>
  <QueryState :query="anomalyQuery" />
  <template v-if="anomalyResponse">
    <div class="result-title">
      <h3>Top 10 Anomaly Scores</h3>
    </div>
    <el-empty
      v-if="!anomalyResults.length"
      :image-size="40"
      :description="anomalyResponse.message || 'No nodes with anomaly scores'"
      class="compact-empty"
    />
    <div
      v-else
      class="result-list compact-results account-anomaly-list"
      aria-label="Anomaly score ranking"
    >
      <div class="anomaly-list-header">
        <span>Rank</span>
        <span>Node ID</span>
        <span title="Higher unitless scores indicate a greater difference from past behavior and the state inferred from neighbors.">Anomaly Score (0–1)</span>
      </div>
      <button
        v-for="item in anomalyResults"
        :key="item.account_id"
        class="result-item"
        :class="{ active: item.account_id === store.anomalyAccount }"
        :aria-pressed="item.account_id === store.anomalyAccount"
        :aria-label="`Rank ${item.rank}, node ${item.account_id}, anomaly score ${item.score.toFixed(4)}`"
        :data-anomaly-account="item.account_id"
        @click="selectAnomaly(item)"
      >
        <span class="result-rank">{{
          String(item.rank).padStart(2, '0')
        }}</span>
        <span class="result-body"
          ><strong>{{ item.account_id }}</strong></span
        >
        <span class="result-score">{{ item.score.toFixed(4) }}</span>
      </button>
    </div>
    <section
      v-if="inspected"
      ref="scoreEvidence"
      class="anomaly-evidence"
      aria-labelledby="anomaly-evidence-title"
    >
      <h3 id="anomaly-evidence-title">{{ inspected.account_id }} · Score breakdown</h3>
      <div class="score-card">
        <small>SLADE score</small>
        <strong>{{ inspected.score.toFixed(4) }}<span> / 1</span></strong>
        <small>Unitless anomaly score</small>
      </div>
      <div class="slade-score-row">
        <span>Temporal contrast score</span>
        <strong
          >{{ inspected.temporal_contrast_score.toFixed(4)
          }}<small> / 2</small></strong
        >
      </div>
      <div class="slade-score-row">
        <span>Memory generation score</span>
        <strong
          >{{ inspected.memory_generation_score.toFixed(4)
          }}<small> / 2</small></strong
        >
      </div>
      <p class="helper">SLADE score = (temporal contrast + memory generation) / 4</p>
    </section>
  </template>
</template>
