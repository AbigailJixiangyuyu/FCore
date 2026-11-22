<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useWorkbench } from '../composables/workbenchContext.js'
import { HISTORY_LENGTH, LAST_HISTORICAL_SNAPSHOT_ID, snapshotId } from '../domain/timeline.js'

defineProps({
  snapshots: { type: Array, required: true },
})

const { store, selectHistoryRange } = useWorkbench()
const lastIndex = HISTORY_LENGTH - 1
const boundaries = ['start', 'end']
const preview = ref(null)
const committedRange = computed(() =>
  store.stage === 'history' ? [store.historyStartIndex, store.historyEndIndex] : null,
)
const selection = computed(() => preview.value ?? committedRange.value)
const selectionStyle = computed(() => {
  if (!selection.value) return {}
  const [start, end] = selection.value
  return {
    left: `${(start / HISTORY_LENGTH) * 100}%`,
    right: `${((lastIndex - end) / HISTORY_LENGTH) * 100}%`,
  }
})
const caption = computed(() => {
  if (!selection.value) return `历史 · S01—${LAST_HISTORICAL_SNAPSHOT_ID}`
  const [start, end] = selection.value
  const range = start === end ? snapshotId(start) : `${snapshotId(start)}—${snapshotId(end)}`
  return `历史 · ${range} · ${end - start + 1} 个快照`
})

// Dragging only changes the local selection. The workbench reads the committed range.
let gesture = null

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function shiftRange([start, end], step) {
  const shift = clamp(step, -start, lastIndex - end)
  return [start + shift, end + shift]
}

function horizontalStep(event) {
  if (event.altKey || event.ctrlKey || event.metaKey) return 0
  if (event.key === 'ArrowLeft') return -1
  if (event.key === 'ArrowRight') return 1
  return 0
}

function beginDrag(event) {
  if (event.button !== 0 || !event.isPrimary || gesture) return
  const rail = event.currentTarget
  const bounds = rail.getBoundingClientRect()
  if (!bounds.width) return
  const handle = event.target.closest('[data-boundary]')
  const selectedRange = event.target.closest('.history-selection')
  const mode = handle?.dataset.boundary ?? (selectedRange ? 'move' : 'draw')
  gesture = {
    rail,
    mode,
    pointerId: event.pointerId,
    originX: event.clientX,
    lastX: event.clientX,
    left: bounds.left,
    cellWidth: bounds.width / HISTORY_LENGTH,
    range: committedRange.value,
  }
  const control = handle ?? selectedRange
  control?.focus({ preventScroll: true })
  rail.setPointerCapture(event.pointerId)
  window.addEventListener('keydown', onDragKeydown)
  window.addEventListener('blur', cancelDrag)
}

function moveDrag(event) {
  if (event.pointerId !== gesture?.pointerId) return
  gesture.lastX = event.clientX
  const { originX, left, cellWidth, mode, range } = gesture
  const delta = event.clientX - originX
  if (!preview.value && Math.abs(delta) < 4) return

  if (mode === 'draw') {
    const first = clamp(Math.floor((originX - left) / cellWidth), 0, lastIndex)
    const last = clamp(Math.floor((event.clientX - left) / cellWidth), 0, lastIndex)
    preview.value = [Math.min(first, last), Math.max(first, last)]
    return
  }

  const [start, end] = range
  const step = Math.round(delta / cellWidth)
  if (mode === 'start') preview.value = [clamp(start + step, 0, end), end]
  else if (mode === 'end') preview.value = [start, clamp(end + step, start, lastIndex)]
  else preview.value = shiftRange(range, step)
}

function finishDrag(event) {
  if (event.pointerId !== gesture?.pointerId) return
  moveDrag(event)
  const range = preview.value
  cancelDrag()
  if (range) selectHistoryRange(...range)
}

function cancelDrag() {
  if (!gesture) return
  const { rail, pointerId } = gesture
  gesture = null
  preview.value = null
  if (rail.hasPointerCapture(pointerId)) rail.releasePointerCapture(pointerId)
  window.removeEventListener('keydown', onDragKeydown)
  window.removeEventListener('blur', cancelDrag)
}

function cancelPointerDrag(event) {
  if (event.pointerId === gesture?.pointerId) cancelDrag()
}

function onDragKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    cancelDrag()
    return
  }
  if (gesture?.mode !== 'move') return
  const step = horizontalStep(event)
  if (!step) return
  event.preventDefault()
  const range = preview.value ?? gesture.range
  const next = shiftRange(range, step)
  if (next[0] === range[0]) return
  preview.value = next
  // Continue pointer movement from this range so releasing does not undo the key step.
  gesture.range = next
  gesture.originX = gesture.lastX
}

function shiftSelection(event) {
  if (gesture || event.defaultPrevented || !committedRange.value) return
  const step = horizontalStep(event)
  if (!step) return
  event.preventDefault()
  const range = committedRange.value
  const next = shiftRange(range, step)
  if (next[0] !== range[0]) selectHistoryRange(...next)
}

function adjustBoundary(event, boundary) {
  if (gesture || !committedRange.value) return
  const [start, end] = committedRange.value
  const isStart = boundary === 'start'
  const current = isStart ? start : end
  const min = isStart ? 0 : start
  const max = isStart ? end : lastIndex
  let next
  switch (event.key) {
    case 'ArrowLeft':
    case 'ArrowDown':
      next = Math.max(min, current - 1)
      break
    case 'ArrowRight':
    case 'ArrowUp':
      next = Math.min(max, current + 1)
      break
    case 'Home':
      next = min
      break
    case 'End':
      next = max
      break
    default:
      return
  }
  event.preventDefault()
  if (next !== current) selectHistoryRange(isStart ? next : start, isStart ? end : next)
}

watch([() => store.stage, committedRange], cancelDrag)
onBeforeUnmount(cancelDrag)
</script>

<template>
  <div
    class="historical-timeline"
    role="group"
    aria-label="历史快照"
    :style="{ '--history-length': HISTORY_LENGTH }"
    @keydown="shiftSelection"
  >
    <div class="history-caption">
      <span>{{ caption }}</span>
      <span v-if="preview" class="history-preview">预览</span>
    </div>
    <div
      class="history-track"
      :class="{ 'is-previewing': preview }"
      @pointerdown="beginDrag"
      @pointermove="moveDrag"
      @pointerup="finishDrag"
      @pointercancel="cancelPointerDrag"
      @lostpointercapture="cancelPointerDrag"
    >
      <div class="history-track-cells" title="拖动框选历史区间" aria-hidden="true">
        <span v-for="meta in snapshots" :key="meta.snapshot_id"></span>
      </div>
      <div
        v-if="selection"
        class="history-selection"
        :style="selectionStyle"
        :tabindex="committedRange ? 0 : -1"
        role="group"
        aria-label="平移历史区间"
        aria-keyshortcuts="ArrowLeft ArrowRight"
        title="拖动或按左右键平移历史区间"
      >
        <div
          v-for="(boundary, index) in boundaries"
          :key="boundary"
          class="history-handle"
          :class="`history-handle--${boundary}`"
          :data-boundary="boundary"
          role="slider"
          :tabindex="committedRange ? 0 : -1"
          :aria-hidden="committedRange ? undefined : 'true'"
          :aria-label="boundary === 'start' ? '历史区间起点' : '历史区间终点'"
          :aria-valuemin="boundary === 'start' ? 0 : selection[0]"
          :aria-valuemax="boundary === 'start' ? selection[1] : lastIndex"
          :aria-valuenow="selection[index]"
          :aria-valuetext="snapshotId(selection[index])"
          :title="boundary === 'start' ? '拖动调整起点' : '拖动调整终点'"
          @keydown="adjustBoundary($event, boundary)"
        ></div>
      </div>
    </div>
    <div class="history-ticks">
      <button
        v-for="meta in snapshots"
        :key="meta.snapshot_id"
        type="button"
        :class="{ 'in-range': selection && meta.index >= selection[0] && meta.index <= selection[1] }"
        :aria-label="`查看 ${meta.snapshot_id} 单快照`"
        :aria-pressed="committedRange?.[0] === meta.index && committedRange?.[1] === meta.index"
        @click="selectHistoryRange(meta.index, meta.index)"
      >
        {{ meta.snapshot_id }}
      </button>
    </div>
  </div>
</template>
