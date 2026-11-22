<script setup>
import { computed } from 'vue'

import { formatNumber } from '../../domain/analysisSummary.js'

const props = defineProps({
  prediction: { type: Object, required: true },
})

const comparison = computed(() => props.prediction.comparison)
const keyNodes = computed(() => comparison.value?.key_nodes ?? [])
const changeLabels = {
  retained: '保留',
  added: '预计新增',
  exited: '预计退出',
}
</script>

<template>
  <div class="summary-line forecast-overview">
    <strong v-if="comparison">
      {{ prediction.observed_until }} 实际 {{ formatNumber(comparison.retained.length + comparison.exited.length) }} 人
      → {{ prediction.target_snapshot }} 预测 {{ formatNumber(prediction.members.length) }} 人
    </strong>
    <strong v-else>成员对照不可用</strong>
  </div>
  <template v-if="comparison">
    <dl class="summary-metrics forecast-metrics" aria-label="社区成员变化">
      <div v-for="(label, change) in changeLabels" :key="change">
        <dt>{{ label }}</dt>
        <dd>
          <el-popover v-if="comparison[change].length" trigger="click" placement="top" :width="235">
            <template #reference>
              <el-button link type="primary" :aria-label="`查看${label}节点`">
                {{ formatNumber(comparison[change].length) }}
              </el-button>
            </template>
            <ul class="forecast-member-list" :aria-label="`${label}节点 ID`" tabindex="0">
              <li v-for="id in comparison[change]" :key="id">{{ id }}</li>
            </ul>
          </el-popover>
          <template v-else>0</template>
        </dd>
      </div>
    </dl>
    <template v-if="keyNodes.length">
      <div class="summary-line forecast-key-nodes">
        <strong>关键节点</strong>
        <span class="summary-context">
          最高核数 {{ comparison.max_coreness }} · {{ formatNumber(keyNodes.length) }} 个节点
        </span>
      </div>
      <div
        class="member-table forecast-key-node-list"
        role="region"
        aria-label="关键节点核数"
        tabindex="0"
      >
        <table>
          <thead>
            <tr>
              <th scope="col">节点 ID</th>
              <th scope="col">成员状态</th>
              <th scope="col">{{ prediction.observed_until }} 实际核数</th>
              <th scope="col">{{ prediction.target_snapshot }} 预测核数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="node in keyNodes" :key="node.account_id">
              <td :title="node.account_id">{{ node.account_id }}</td>
              <td>{{ node.observed_coreness == null ? changeLabels.added : changeLabels.retained }}</td>
              <td>{{ formatNumber(node.observed_coreness) }}</td>
              <td>{{ formatNumber(node.predicted_coreness) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <p v-else class="summary-empty forecast-comparison-note" role="status">
      {{ prediction.target_snapshot }} 未形成预测社区。{{ prediction.message }}
    </p>
  </template>
  <p v-else class="summary-empty forecast-comparison-note" role="status">
    {{ prediction.message || '暂无可比较的预测结果。' }}
  </p>
</template>
