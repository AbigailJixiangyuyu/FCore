<script setup>
import { useMutation } from '@tanstack/vue-query'
import { ElDialog } from 'element-plus'
import { shallowRef } from 'vue'
import 'element-plus/es/components/dialog/style/css'

import { importDataset } from '../api/system.js'
import { useWorkbench } from '../composables/workbenchContext.js'

const open = defineModel({ type: Boolean, required: true })
const { system, selectDataset } = useWorkbench()
const file = shallowRef(null)
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
    title="数据集新增"
    width="450px"
    append-to-body
    destroy-on-close
    :show-close="!isPending"
    :close-on-click-modal="false"
    :close-on-press-escape="!isPending"
    @closed="clearFile"
  >
    <div class="dataset-import">
      <p>选择一个 UTF-8 CSV 文件。首行为 <code>u,v,t</code>。</p>
      <pre>u,v,t
001,002,1767232805
001,002,1767232805
002,001,1767232806.125</pre>
      <p><code>u</code> 和 <code>v</code> 是无向连接的两个端点，顺序不限。<code>t</code> 为 Unix 秒时间戳，可带小数。毫秒请先除以 1000。</p>
      <input type="file" accept=".csv" aria-label="选择 CSV 文件" :disabled="isPending" @change="chooseFile" />
      <el-alert v-if="error" type="error" :title="error.message" :closable="false" />
    </div>
    <template #footer>
      <el-button :disabled="isPending" @click="open = false">取消</el-button>
      <el-button type="primary" :disabled="!file" :loading="isPending" @click="mutate(file)">
        导入
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

.dataset-import input {
  width: 100%;
  font: inherit;
}

.dataset-import input::file-selector-button {
  margin-right: 8px;
  padding: 5px 10px;
  border: 1px solid #cdd8e8;
  border-radius: 4px;
  background: #fff;
  color: #223755;
  font: inherit;
  cursor: pointer;
}
</style>
