<script setup>
import { computed, ref, useTemplateRef } from 'vue'

const props = defineProps({
  id: { type: String, required: true },
  account: { type: String, required: true },
  coreNumbers: { type: Object, default: null },
  disabled: Boolean,
})
const k = defineModel({ type: Number })
const maxK = 10000
const input = useTemplateRef('input')
const showCoreness = ref(false)
const coreness = computed(function () {
  const numbers = props.coreNumbers
  return numbers && Object.hasOwn(numbers, props.account) ? numbers[props.account] : null
})
const canUseCoreness = computed(() => coreness.value !== null && coreness.value <= maxK)

function leaveInput({ currentTarget }) {
  if (!currentTarget.contains(document.activeElement)) showCoreness.value = false
}

function leaveFocus({ currentTarget, relatedTarget }) {
  if (!currentTarget.contains(relatedTarget)) showCoreness.value = false
}

function dismissCoreness() {
  input.value?.focus()
  showCoreness.value = false
}

function useCoreness() {
  if (!canUseCoreness.value) return
  k.value = coreness.value
  dismissCoreness()
}
</script>

<template>
  <div class="compact-field number-field">
    <label :for="id">Core k</label>
    <div
      class="query-core-input"
      @mouseenter="showCoreness = true"
      @mouseleave="leaveInput"
      @focusin="showCoreness = true"
      @focusout="leaveFocus"
      @keydown.esc="dismissCoreness"
    >
      <el-input-number
        :id="id"
        v-model="k"
        ref="input"
        :min="0"
        :max="maxK"
        :step="1"
        :precision="0"
        :controls="false"
        :disabled="disabled"
        @click="showCoreness = true"
      />
      <el-button
        v-if="showCoreness && canUseCoreness"
        class="coreness-option"
        size="small"
        native-type="button"
        @click="useCoreness"
      >Use coreness {{ coreness }} of vertex {{ account }}</el-button>
    </div>
  </div>
</template>
