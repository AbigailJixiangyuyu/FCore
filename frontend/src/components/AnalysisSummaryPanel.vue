<script setup>
import { computed } from 'vue'

import { matchesContext } from '../api/analysis.js'
import { useWorkbench } from '../composables/workbenchContext.js'
import { summarizeRisk } from '../domain/analysisSummary.js'
import AnalysisReport from './analysis-summary/AnalysisReport.vue'
import DatasetStatistics from './analysis-summary/DatasetStatistics.vue'
import ResultAnalysis from './analysis-summary/ResultAnalysis.vue'
import '../styles/analysis-summary.css'

const { store, context, selected, metric, evidenceResult, anomalyResponse } =
  useWorkbench()

const track = computed(function () {
  if (store.stage !== 'history' || !selected.value || !evidenceResult.isSuccess.value) return null
  const response = evidenceResult.data.value
  if (!matchesContext(response, context.value) || response.metric !== metric.value) return null
  return response.series.find(item => item.membership_hash === selected.value.membership_hash)
})

const risk = computed(function () {
  const structure = selected.value
  const response = anomalyResponse.value
  if (store.stage !== 'present' || !structure || response?.status !== 'ok') return null
  if (response.snapshot_id !== structure.observed_until) return null
  return summarizeRisk(structure.members, response.accounts, store.anomalyAccount)
})

</script>

<template>
  <section class="panel analysis-summary" aria-label="05 分析概览">
    <DatasetStatistics />
    <ResultAnalysis :track="track" :risk="risk" />
    <AnalysisReport :track="track" :risk="risk" />
  </section>
</template>
