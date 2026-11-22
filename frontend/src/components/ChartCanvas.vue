<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: Number, default: 150 },
  label: { type: String, required: true },
  interactive: { type: Boolean, default: false },
})
const emit = defineEmits(['select-index'])
const container = ref(null)
let chart = null
let observer = null
let disposed = false
const failure = ref('')

function renderOption(option) {
  if (!chart) return
  const settings = { ...option }
  if (typeof option.tooltip?.formatter === 'function') {
    settings.tooltip = {
      ...option.tooltip,
      formatter(...args) {
        const text = option.tooltip.formatter(...args)
        if (typeof text !== 'string' || !text) return text
        const label = document.createElement('div')
        label.textContent = text
        label.style.whiteSpace = 'pre-wrap'
        return label
      },
    }
  }
  chart.setOption(settings, { notMerge: true })
}

onMounted(async function () {
  try {
    const { echarts } = await import('../charts/runtime.js')
    if (disposed) return
    const { fontFamily, fontSize } = getComputedStyle(container.value)
    const textStyle = { fontFamily, fontSize: Number.parseFloat(fontSize), fontWeight: 'normal' }
    chart = echarts.init(container.value, {
      textStyle,
      categoryAxis: { axisLabel: textStyle },
      valueAxis: { axisLabel: textStyle },
      tooltip: { textStyle, renderMode: 'html', confine: true, className: 'chart-tooltip' },
    }, { locale: 'EN' })
    renderOption(props.option)
    chart.getZr().on('click', function (event) {
      if (
        !props.interactive ||
        !chart.containPixel('grid', [event.offsetX, event.offsetY])
      )
        return
      const index = chart.convertFromPixel({ xAxisIndex: 0 }, event.offsetX)
      if (Number.isFinite(index)) emit('select-index', Math.round(index))
    })
    observer = new ResizeObserver(function () {
      chart?.resize()
    })
    observer.observe(container.value)
  } catch (error) {
    failure.value = `Could not load chart. ${error.message}`
  }
})
watch(
  function () {
    return props.option
  },
  renderOption,
  { deep: true },
)
onBeforeUnmount(function () {
  disposed = true
  observer?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div v-if="failure" class="request-error" role="alert">{{ failure }}</div>
  <div
    v-else
    ref="container"
    class="chart-canvas"
    :style="{ height: `${height}px` }"
    role="img"
    :aria-label="label"
  ></div>
</template>
