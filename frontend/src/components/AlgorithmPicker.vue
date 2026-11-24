<script setup>
import { algorithmLabel } from '../domain/algorithms.js'

defineProps({
  algorithms: { type: Object, required: true },
  label: { type: String, required: true },
})
const selected = defineModel({ type: String, required: true })
</script>

<template>
  <section class="algorithm-picker">
    <h3>Model Selection</h3>
    <el-radio-group v-model="selected" class="paper-options" :aria-label="label">
      <el-radio
        v-for="(algorithm, id) in algorithms"
        :key="id"
        :value="id"
        :title="algorithm.paperTitle"
      >
        {{ algorithmLabel(algorithm) }}<span class="visually-hidden">. {{ algorithm.paperTitle }}</span>
      </el-radio>
    </el-radio-group>
  </section>
</template>
