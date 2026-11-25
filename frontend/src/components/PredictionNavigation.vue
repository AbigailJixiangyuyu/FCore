<script setup>
import { useWorkbench } from '../composables/workbenchContext.js'

const { store, selectTime } = useWorkbench()
</script>

<template>
  <div
    v-if="store.stage === 'present' || store.stage === 'future'"
    class="prediction-actions"
    role="group"
    aria-label="Prediction navigation"
  >
    <el-button
      v-if="store.stage === 'present'"
      type="primary"
      class="full"
      @click="selectTime(store.presentIndex + 1)"
      >Go to Future Prediction →</el-button
    >
    <el-button v-else class="full" @click="selectTime(store.presentIndex)"
      >← Back to Current Search</el-button
    >
  </div>
</template>
