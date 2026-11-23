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
    aria-label="Prediction navigation"
  >
    <el-button
      v-if="store.stage === 'present'"
      type="primary"
      class="full"
      @click="selectTime(FUTURE_INDEX)"
      >Go to Future Prediction →</el-button
    >
    <el-button v-else class="full" @click="selectTime(PRESENT_INDEX)"
      >← Back to Current Search</el-button
    >
  </div>
</template>
