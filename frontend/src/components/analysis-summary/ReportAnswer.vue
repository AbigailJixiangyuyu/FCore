<script setup>
import { computed, ref } from 'vue'
import { renderReportMarkdown } from '../../domain/reportMarkdown.js'

const props = defineProps({ content: { type: String, required: true }, thinking: String, thinkingDurationMs: Number, nodeLabels: Object })
const expanded = ref(false)
const hasAnswer = computed(() => props.thinkingDurationMs != null || Boolean(props.content.trim()))
const html = computed(() => renderReportMarkdown(props.content, props.nodeLabels))
const thinkingText = computed(() => props.thinking?.replace(/\bN\d{3,}\b/g, alias => props.nodeLabels?.[alias] ?? alias))
</script>

<template>
  <div class="report-answer">
    <div v-if="thinkingText" class="report-thinking">
      <button v-if="hasAnswer" type="button" class="report-thinking-toggle" :aria-expanded="expanded" @click="expanded = !expanded">
        {{ expanded ? '- Thinking:' : '+ Thinking' }}{{ expanded || thinkingDurationMs == null ? '' : ` ${(thinkingDurationMs / 1000).toFixed(1)}s` }}
      </button>
      <strong v-else>- Thinking:</strong>
      <span v-if="!hasAnswer || expanded">{{ thinkingText }}</span>
    </div>
    <div v-if="content" class="report-answer-body" v-html="html"></div>
  </div>
</template>
