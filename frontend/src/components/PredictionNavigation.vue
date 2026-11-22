<script setup>
import { useWorkbench } from '../composables/workbenchContext.js'
import { FUTURE_INDEX, PRESENT_INDEX } from '../domain/timeline.js'

const { store, selectTime } = useWorkbench()
</script>

<template>
  <div
    v-if="store.stage !== 'history'"
    class="prediction-actions"
    role="group"
    aria-label="预测视图导航"
  >
    <el-button
      v-if="store.stage === 'present'"
      type="primary"
      class="full"
      @click="selectTime(FUTURE_INDEX)"
      >进行预测 →</el-button
    >
    <el-button v-else class="full" @click="selectTime(PRESENT_INDEX)"
      >← 返回现在</el-button
    >
  </div>
</template>
