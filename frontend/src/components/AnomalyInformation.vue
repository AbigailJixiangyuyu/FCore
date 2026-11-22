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
      <h3>账户异常程度排名 · Top-10</h3>
    </div>
    <el-empty
      v-if="!anomalyResults.length"
      :image-size="40"
      :description="anomalyResponse.message || '当前没有可评分账户'"
      class="compact-empty"
    />
    <div
      v-else
      class="result-list compact-results account-anomaly-list"
      aria-label="账户异常程度排名"
    >
      <div class="anomaly-list-header">
        <span>排名</span>
        <span>账户 ID</span>
        <span title="无单位。分数越高，账户的交互状态与自身过去及邻域推断的状态差异越大。此分数不是概率。">异常分（0–1）</span>
      </div>
      <button
        v-for="item in anomalyResults"
        :key="item.account_id"
        class="result-item"
        :class="{ active: item.account_id === store.anomalyAccount }"
        :aria-pressed="item.account_id === store.anomalyAccount"
        :aria-label="`第 ${item.rank} 名，账户 ${item.account_id}，异常分 ${item.score.toFixed(4)}`"
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
      <h3 id="anomaly-evidence-title">{{ inspected.account_id }} · 评分依据</h3>
      <div class="score-card">
        <small>SLADE 综合分数</small>
        <strong>{{ inspected.score.toFixed(4) }}<span> / 1</span></strong>
        <small>异常程度 · 非欺诈概率</small>
      </div>
      <div class="slade-score-row">
        <span>时间对比分数</span>
        <strong
          >{{ inspected.temporal_contrast_score.toFixed(4)
          }}<small> / 2</small></strong
        >
      </div>
      <div class="slade-score-row">
        <span>记忆生成分数</span>
        <strong
          >{{ inspected.memory_generation_score.toFixed(4)
          }}<small> / 2</small></strong
        >
      </div>
      <p class="helper">综合分数 =（时间对比 + 记忆生成）/ 4</p>
    </section>
  </template>
</template>
