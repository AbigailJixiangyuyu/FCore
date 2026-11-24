<script setup>
import { computed } from 'vue'
import { renderReportMarkdown } from '../../domain/reportMarkdown.js'

const props = defineProps({ content: { type: String, required: true }, nodeLabels: Object })
const html = computed(() => renderReportMarkdown(props.content, props.nodeLabels))
</script>

<template>
  <div class="report-answer" v-html="html"></div>
</template>
