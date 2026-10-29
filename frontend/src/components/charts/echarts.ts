// Tree-shaken ECharts build: only the chart types and components VoltBharat uses.
import { BarChart, LineChart, MapChart, PieChart, ScatterChart } from 'echarts/charts'
import {
  AriaComponent, DataZoomComponent, GeoComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent,
  TooltipComponent, VisualMapComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart, LineChart, MapChart, PieChart, ScatterChart, AriaComponent, DataZoomComponent, GeoComponent, GridComponent,
  LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent, VisualMapComponent, CanvasRenderer,
])

export { echarts }
export type { EChartsCoreOption as EChartsOption } from 'echarts/core'
