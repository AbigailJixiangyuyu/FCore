<script setup>
import { computed, nextTick, ref, watch } from 'vue'

import { useWorkbench } from '../../composables/workbenchContext.js'
import { useLifecycleReport } from '../../composables/workbench/useLifecycleReport.js'
import { reportStages } from '../../domain/reportEvidence.js'

const {
  stage, slots, count, canSubmit, submit, generating, generate, report, error,
  busy, canAsk, answering, question, ask, retry, turns, pendingTurn, replyError,
} = useLifecycleReport(useWorkbench())
const reportArea = ref(null)
const reportText = computed(() => displayText(report.value?.content ?? ''))
const canSend = computed(() => canAsk.value && !busy.value && !!question.value.trim())

function displayText(content) {
  const labels = report.value?.node_labels
  return content.replace(/\bN\d{3,}\b/g, alias => labels?.[alias] ?? alias)
}

async function scrollToLatest() {
  const area = reportArea.value
  if (!area) return
  await nextTick()
  area.scrollTop = area.scrollHeight
}

watch([reportText, () => pendingTurn.value?.answer, replyError], () => {
  const area = reportArea.value
  if ((busy.value || replyError.value) && area && area.scrollHeight - area.scrollTop - area.clientHeight <= 8) {
    scrollToLatest()
  }
})
watch(answering, (active) => {
  if (active) scrollToLatest()
})

function onQuestionKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  ask()
}
</script>

<template>
  <section class="summary-column report-summary" aria-labelledby="report-summary-title">
    <div class="summary-heading">
      <h2 id="report-summary-title">LLM-based Report</h2>
      <span class="summary-context" aria-live="polite">{{ count }}/3 submitted</span>
    </div>
    <dl class="report-slots" aria-label="Submitted evidence">
      <div v-for="(label, key) in reportStages" :key="key"
        :class="{ 'is-active': key === stage, 'is-submitted': !!slots[key] }">
        <dt>{{ label }}</dt>
        <dd v-if="slots[key]">{{ slots[key].method }} · {{ slots[key].window }}</dd>
        <dd v-else>Not submitted</dd>
      </div>
    </dl>
    <div class="report-actions">
      <el-button size="small" :disabled="!canSubmit" @click="submit">Submit Evidence</el-button>
      <el-button size="small" type="primary" :loading="generating" :disabled="count !== 3 || busy" @click="generate">
        Generate Report
      </el-button>
    </div>
    <div ref="reportArea" class="report-content" role="log" aria-label="Report and discussion" :aria-busy="busy">
      <p v-if="error" class="report-error" role="alert">{{ error }}</p>
      <p v-if="reportText" class="report-text">{{ reportText }}</p>
      <p v-else-if="generating" class="report-status">Generating the joint report…</p>
      <p v-else-if="!error && count < 3" class="report-status">Run an analysis and submit evidence from each stage.</p>
      <p v-else-if="!error" class="report-status">All three stages are ready to analyze.</p>
      <template v-if="!generating">
        <div v-for="(turn, index) in turns" :key="index" class="report-turn">
          <p class="report-text report-question">{{ turn.question }}</p>
          <p class="report-text report-answer">{{ displayText(turn.answer) }}</p>
        </div>
        <div v-if="pendingTurn" class="report-turn">
          <p class="report-text report-question">{{ pendingTurn.question }}</p>
          <p v-if="pendingTurn.answer" class="report-text report-answer">{{ displayText(pendingTurn.answer) }}</p>
          <p v-else-if="answering" class="report-status">Thinking…</p>
          <div v-if="replyError" class="report-reply-error">
            <p class="report-error" role="alert">{{ replyError }}</p>
            <el-button size="small" text :disabled="busy || !canAsk" @click="retry">Retry</el-button>
          </div>
        </div>
      </template>
    </div>
    <form class="report-composer" @submit.prevent="ask">
      <el-input
        v-model="question" type="textarea" :rows="1" resize="none"
        aria-label="Follow-up question" :disabled="!canAsk || generating"
        :placeholder="report?.legacy ? 'Generate a report to ask a question' : 'Ask about this report…'"
        @keydown="onQuestionKeydown"
      />
      <el-button size="small" type="primary" native-type="submit" :disabled="!canSend">Send</el-button>
    </form>
  </section>
</template>
