<script setup>
import { useWorkbench } from '../composables/workbenchContext.js'

const account = defineModel({ type: String, required: true })
const { anomalyResults, anomalyQuery } = useWorkbench()
const rankingLoading = anomalyQuery.isFetching

function selectRankedAccount(id) {
  account.value = id
}
</script>

<template>
  <div class="compact-field account-field">
    <label for="query-account-id">Query node</label>
    <el-input id="query-account-id" v-model="account" placeholder="ID" />
    <el-dropdown
      trigger="click"
      :disabled="!anomalyResults.length"
      @command="selectRankedAccount"
    >
      <el-button
        size="small"
        :loading="rankingLoading"
      >
        Anomaly Scores
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="item in anomalyResults"
            :key="item.account_id"
            :command="item.account_id"
          >
            #{{ item.rank }} · {{ item.account_id }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>
