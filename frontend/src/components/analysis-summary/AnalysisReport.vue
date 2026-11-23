<script setup>
import { computed, nextTick, ref, watch } from 'vue'

import { useWorkbench } from '../../composables/workbenchContext.js'
import { useLifecycleReport } from '../../composables/workbench/useLifecycleReport.js'
import { evidenceMethodName, reportStages } from '../../domain/reportEvidence.js'

const {
  stage, slots, ready, canSubmit, submit, generating, report, error,
  busy, canAsk, canSend, answering, question, ask, retry, turns, pendingTurn, replyError,
} = useLifecycleReport(useWorkbench())
const questionPlaceholder = computed(() => {
  if (!ready.value) return 'Submit one result from each stage.'
  return canAsk.value ? 'Ask about this report…' : 'Ask FCore'
})
const reportArea = ref(null)
const reportText = computed(() => displayText(report.value?.content ?? ''))

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
watch(busy, (active) => {
  if (active) scrollToLatest()
})

function submitComposer() {
  if (ready.value) return ask()
  submit()
}

function onQuestionKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  submitComposer()
}
</script>

<template>
  <section class="summary-column report-summary" aria-labelledby="report-summary-title">
    <div class="summary-heading">
      <h2 id="report-summary-title">LLM-Assisted Interpretation</h2>
      <el-button v-if="ready && canSubmit" class="report-update" size="small" @click="submit">Update Evidence</el-button>
    </div>
    <div ref="reportArea" class="report-content" role="log" aria-label="Report and discussion" :aria-busy="busy">
      <p v-if="report?.initial_prompt" class="report-text report-question report-opening">{{ report.initial_prompt }}</p>
      <p v-if="error" class="report-error" role="alert">{{ error }}</p>
      <p v-if="reportText" class="report-text report-answer">{{ reportText }}</p>
      <p v-else-if="generating" class="report-status">
        Generating the full-cycle report<span class="report-status-dots" aria-hidden="true">...</span>
      </p>
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
    <form class="report-composer" @submit.prevent="submitComposer">
      <ul v-if="!canAsk && !generating" class="report-evidence" aria-label="Report evidence" aria-live="polite">
        <li
          v-for="(label, key) in reportStages"
          :key="key"
          :class="{ submitted: slots[key], active: stage === key }"
          :title="slots[key] ? `${evidenceMethodName(slots[key])} · ${slots[key].window}` : undefined"
        >
          <strong>{{ label }}</strong>
          <template v-if="slots[key]">
            <span class="report-evidence-method">{{ evidenceMethodName(slots[key]) }}</span>
            <span class="report-evidence-window">{{ slots[key].window }}</span>
          </template>
          <span v-else-if="stage === key && canSubmit">Ready</span>
        </li>
      </ul>
      <el-input
        :model-value="generating ? '' : question" type="textarea" :autosize="{ minRows: 1, maxRows: 3 }" resize="none"
        :aria-label="canAsk ? 'Follow-up question' : 'Optional question for the report'"
        :readonly="!ready || generating"
        :placeholder="generating ? undefined : questionPlaceholder"
        @update:model-value="question = $event"
        @keydown="onQuestionKeydown"
      />
      <el-button size="small" type="primary" native-type="submit" :disabled="ready ? !canSend : !canSubmit" :loading="busy">
        {{ ready ? 'Send' : 'Submit' }}
      </el-button>
    </form>
  </section>
</template>
