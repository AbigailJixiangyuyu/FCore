<script setup>
defineProps({
  query: { type: Object, required: true },
  empty: { type: Boolean, default: false },
  emptyText: { type: String, default: 'No results' },
})
</script>

<template>
  <div v-if="query.isFetching.value" class="request-state" role="status">
    <span class="loading-dot"></span>Loading…
  </div>
  <div v-else-if="query.isError.value" class="request-error" role="alert">
    <p>{{ query.error.value?.message || 'Request failed. Try again.' }}</p>
    <el-button plain @click="query.refetch()">Retry</el-button>
  </div>
  <el-empty
    v-else-if="empty"
    :image-size="40"
    :description="emptyText"
    class="compact-empty"
  />
</template>
