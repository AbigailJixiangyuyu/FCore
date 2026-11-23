<script setup>
import { useMutation } from '@tanstack/vue-query'
import { ElDialog } from 'element-plus'
import { shallowRef, useTemplateRef } from 'vue'
import 'element-plus/es/components/dialog/style/css'

import { importDataset } from '../api/system.js'
import { useWorkbench } from '../composables/workbenchContext.js'

const open = defineModel({ type: Boolean, required: true })
const { system, selectDataset } = useWorkbench()
const file = shallowRef(null)
const fileInput = useTemplateRef('file-input')
const { isPending, error, reset, mutate } = useMutation({
  mutationFn: async function (chosenFile) {
    const dataset = await importDataset(chosenFile)
    await system.refreshDatasets()
    return dataset
  },
  onSuccess: function (dataset) {
    selectDataset(dataset)
    open.value = false
  },
})

function chooseFile(event) {
  file.value = event.target.files[0] || null
  reset()
}

function clearFile() {
  file.value = null
  reset()
}
</script>

<template>
  <ElDialog
    v-model="open"
    title="Load Dataset"
    width="450px"
    append-to-body
    destroy-on-close
    :show-close="!isPending"
    :close-on-click-modal="false"
    :close-on-press-escape="!isPending"
    @closed="clearFile"
  >
    <div class="dataset-import">
      <p>Choose one UTF-8 CSV file with the header <code>u,v,t</code>.</p>
      <pre>u,v,t
001,002,1767232805
001,002,1767232805
002,001,1767232806.125</pre>
      <p>Enter the two endpoints of an undirected edge as <code>u</code> and <code>v</code>, in either order. Use Unix seconds for <code>t</code>. Fractional seconds are allowed. Divide millisecond timestamps by 1,000 before uploading.</p>
      <div class="dataset-file-picker">
        <input ref="file-input" type="file" accept=".csv" hidden :disabled="isPending" @change="chooseFile" />
        <el-button :disabled="isPending" @click="fileInput?.click()">Choose CSV</el-button>
        <span aria-live="polite">{{ file?.name || 'No file selected' }}</span>
      </div>
      <el-alert v-if="error" type="error" :title="error.message" :closable="false" />
    </div>
    <template #footer>
      <el-button :disabled="isPending" @click="open = false">Cancel</el-button>
      <el-button type="primary" :disabled="!file" :loading="isPending" @click="mutate(file)">
        Import
      </el-button>
    </template>
  </ElDialog>
</template>

<style scoped>
.dataset-import {
  display: grid;
  gap: 10px;
  overflow-wrap: anywhere;
}

.dataset-import p {
  margin: 0;
  line-height: 1.5;
}

.dataset-import pre {
  margin: 0;
  padding: 8px 10px;
  border: 1px solid #dce4ef;
  border-radius: 4px;
  background: #f3f6fa;
  color: #223755;
  line-height: 1.5;
}

.dataset-file-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dataset-file-picker .el-button {
  flex-shrink: 0;
}

.dataset-file-picker span {
  min-width: 0;
}
</style>
