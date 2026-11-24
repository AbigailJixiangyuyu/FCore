<script setup>
import { ChatDotRound, DocumentAdd, Position } from '@element-plus/icons-vue'
import { computed, defineAsyncComponent, nextTick, ref, watch } from 'vue'

import { useWorkbench } from '../../composables/workbenchContext.js'
import { useLifecycleReport } from '../../composables/workbench/useLifecycleReport.js'
import { evidenceMethodName, reportStages } from '../../domain/reportEvidence.js'

const ReportAnswer = defineAsyncComponent(() => import('./ReportAnswer.vue'))

const {
  stage, slots, ready, canSubmit, submit, generating, report, error,
  busy, canAsk, canSend, answering, question, ask, retry, turns, pendingTurn, replyError,
} = useLifecycleReport(useWorkbench())
const reportArea = ref(null)
const reportText = computed(() => report.value?.content ?? '')

async function scrollToLatest() {
  const area = reportArea.value
  if (!area) return
  await nextTick()
  area.scrollTop = area.scrollHeight
}

watch([reportText, () => report.value?.thinking, () => pendingTurn.value?.thinking, () => pendingTurn.value?.answer, replyError], () => {
  const area = reportArea.value
  if ((busy.value || replyError.value) && area && area.scrollHeight - area.scrollTop - area.clientHeight <= 8) {
    scrollToLatest()
  }
})
watch(busy, (active) => {
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
      <h2 id="report-summary-title" class="section-title">
        <ChatDotRound aria-hidden="true" />
        LLM-Assisted Interpretation
      </h2>
    </div>
    <div class="report-evidence-bar" role="group" aria-label="Report evidence">
      <ul class="report-evidence" aria-live="polite">
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
      <el-button size="small" :icon="DocumentAdd" :disabled="!canSubmit || busy" @click="submit">
        {{ slots[stage] ? 'Update' : 'Submit' }}
      </el-button>
    </div>
    <div ref="reportArea" class="report-content" role="log" aria-label="Report and discussion" :aria-busy="busy">
      <p v-if="report?.initial_prompt" class="report-text report-question report-opening">{{ report.initial_prompt }}</p>
      <p v-if="error" class="report-error" role="alert">{{ error }}</p>
      <ReportAnswer v-if="reportText || report?.thinking" :content="reportText" :thinking="report.thinking" :thinking-duration-ms="report.thinkingDurationMs" :node-labels="report.node_labels" />
      <p v-else-if="generating" class="report-status">
        Generating report<span class="report-status-dots" aria-hidden="true">...</span>
      </p>
      <template v-if="!generating">
        <div v-for="(turn, index) in turns" :key="index" class="report-turn">
          <p class="report-text report-question">{{ turn.question }}</p>
          <ReportAnswer :content="turn.answer" :thinking="turn.thinking" :thinking-duration-ms="turn.thinkingDurationMs" :node-labels="report.node_labels" />
        </div>
        <div v-if="pendingTurn" class="report-turn">
          <p class="report-text report-question">{{ pendingTurn.question }}</p>
          <ReportAnswer v-if="pendingTurn.answer || pendingTurn.thinking" :content="pendingTurn.answer" :thinking="pendingTurn.thinking" :thinking-duration-ms="pendingTurn.thinkingDurationMs" :node-labels="report.node_labels" />
          <p v-else-if="answering" class="report-status">Thinking…</p>
          <div v-if="replyError" class="report-reply-error">
            <p class="report-error" role="alert">{{ replyError }}</p>
            <el-button size="small" text :disabled="busy || !canAsk" @click="retry">Retry</el-button>
          </div>
        </div>
      </template>
    </div>
    <form class="report-composer" aria-label="Message FCore" @submit.prevent="ask">
      <el-input
        :model-value="generating ? '' : question" type="textarea" :autosize="{ minRows: 1, maxRows: 3 }" resize="none"
        :aria-label="canAsk ? 'Follow-up question' : 'Optional question for the report'"
        :readonly="generating"
        :placeholder="canAsk ? 'Ask about this report…' : 'Ask FCore'"
        @update:model-value="question = $event"
        @keydown="onQuestionKeydown"
      />
      <el-button
        size="small"
        type="primary"
        native-type="submit"
        :icon="Position"
        :disabled="!canSend"
        :title="!ready ? 'Submit evidence from at least one stage to send.' : undefined"
        :loading="busy"
      >
        Send
      </el-button>
    </form>
  </section>
</template>
