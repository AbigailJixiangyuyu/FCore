import * as echarts from 'echarts/core'
import { BarChart, BoxplotChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  GridComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  BoxplotChart,
  LineChart,
  ScatterChart,
  GridComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
  CanvasRenderer,
])

export { echarts }
