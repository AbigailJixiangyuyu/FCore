<script setup>
defineProps({
  query: { type: Object, required: true },
  empty: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无结果' },
})
</script>

<template>
  <div v-if="query.isFetching.value" class="request-state" role="status">
    <span class="loading-dot"></span>正在读取与计算…
  </div>
  <div v-else-if="query.isError.value" class="request-error" role="alert">
    <p>{{ query.error.value?.message || '请求失败，请重试' }}</p>
    <el-button plain @click="query.refetch()">重试</el-button>
  </div>
  <el-empty
    v-else-if="empty"
    :image-size="40"
    :description="emptyText"
    class="compact-empty"
  />
</template>
