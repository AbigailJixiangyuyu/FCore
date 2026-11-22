<script setup>
import { ref } from 'vue'

const emit = defineEmits(['submit'])
const error = ref('')

function clearError() {
  error.value = ''
}

function submit() {
  clearError()
  emit('submit')
}

function showError({ target }) {
  if (error.value) return

  const label = target.labels?.[0]?.textContent.trim() || 'This field'
  const { rangeUnderflow, rangeOverflow, stepMismatch } = target.validity
  if (rangeUnderflow) error.value = `${label} must be at least ${target.min}.`
  else if (rangeOverflow) error.value = `${label} must be at most ${target.max}.`
  else if (stepMismatch) error.value = `Use a step of ${target.step} for ${label}.`
  else error.value = `Enter a valid number for ${label}.`
  target.focus()
}
</script>

<template>
  <form
    class="control-parameters"
    @input="clearError"
    @invalid.capture.prevent="showError"
    @submit.prevent="submit"
  >
    <slot :clearError="clearError" />
    <p v-if="error" class="request-error" role="alert">{{ error }}</p>
  </form>
</template>
