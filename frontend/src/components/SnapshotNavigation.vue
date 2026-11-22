<script setup>
import { ArrowDown, Plus } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import { useWorkbench } from '../composables/workbenchContext.js'
import DatasetImportDialog from './DatasetImportDialog.vue'
import HistoryRangeSelector from './HistoryRangeSelector.vue'
import QueryState from './QueryState.vue'

const { store, system, dataset, catalog, selectDataset, selectTime } = useWorkbench()
const importOpen = ref(false)
const datasets = system.datasets
const snapshots = computed(function () {
  return catalog.data.value?.snapshots || []
})
const history = computed(() => snapshots.value.filter((meta) => meta.kind === 'history'))
const stageStops = computed(() => snapshots.value.filter((meta) => meta.kind !== 'history'))
const snapshotMinutes = computed(function () {
  return dataset.value?.snapshot_minutes.toLocaleString('zh-CN') ?? '—'
})
function datasetLabel(item) {
  if (item?.dataset_id === 'email-eu-core-dept3') return 'EmailDept3'
  if (item?.dataset_id === 'synthetic-small') return '合成样例'
  return item?.name
}
</script>

<template>
  <section class="panel time-navigation" aria-label="快照时间导航">
    <div class="time-navigation-settings">
      <span class="panel-number">01</span>
      <el-dropdown trigger="click" placement="bottom-start" @command="selectDataset">
        <el-button class="time-setting-button" :title="datasetLabel(dataset)">
          数据集选择<ArrowDown class="time-setting-caret" aria-hidden="true" />
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="item in datasets"
              :key="item.dataset_id"
              :command="item"
              :aria-current="item.dataset_id === store.datasetId ? 'true' : undefined"
            >
              {{ datasetLabel(item) }}
              <span v-if="item.dataset_id === store.datasetId" class="dataset-current">当前</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-popover trigger="click" placement="bottom-start" :width="190">
        <template #reference>
          <el-button class="time-setting-button">
            时间粒度选择<ArrowDown class="time-setting-caret" aria-hidden="true" />
          </el-button>
        </template>
        <div class="snapshot-granularity">
          <span>当前粒度</span>
          <strong>{{ snapshotMinutes }} 分钟／快照</strong>
        </div>
      </el-popover>
      <el-button class="time-setting-button" :icon="Plus" @click="importOpen = true">
        数据集新增
      </el-button>
      <DatasetImportDialog v-model="importOpen" />
    </div>
    <QueryState v-if="!snapshots.length" :query="catalog" />
    <div v-else class="time-axis">
      <HistoryRangeSelector :key="store.datasetId" :snapshots="history" />
      <button
        v-for="meta in stageStops"
        :key="meta.snapshot_id"
        type="button"
        class="time-stage"
        :class="`time-stage--${meta.kind}`"
        :aria-pressed="meta.index === store.timeIndex"
        @click="selectTime(meta.index)"
      >
        <span>{{ meta.kind === 'present' ? '现在' : '未来' }}</span>
        <strong>{{ meta.snapshot_id }}</strong>
      </button>
    </div>
  </section>
</template>
