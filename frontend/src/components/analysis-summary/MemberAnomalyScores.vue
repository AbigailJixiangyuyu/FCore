<script setup>
defineProps({
  scores: { type: Array, required: true },
})
const emit = defineEmits(['locate'])

function locateMember(id, hide) {
  emit('locate', id)
  hide()
}
</script>

<template>
  <el-popover trigger="click" placement="top-end" :width="245" :persistent="false">
    <template #reference>
      <el-button link type="primary" aria-label="Show community member anomaly scores">Scores</el-button>
    </template>
    <template #default="{ hide }">
      <div class="member-table" role="region" aria-label="Community member anomaly scores" tabindex="0">
        <table>
          <thead>
            <tr>
              <th scope="col">Node ID</th>
              <th scope="col" title="Combined SLADE anomaly score (0–1)">SLADE Score</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="member in scores"
              :key="member.account_id"
              class="member-locate-row"
              @click="locateMember(member.account_id, hide)"
            >
              <td>
                <button
                  type="button"
                  class="member-locate-button"
                  :aria-label="`Locate node ${member.account_id} on the graph`"
                  :title="`Locate node ${member.account_id} on the graph`"
                >{{ member.account_id }}</button>
              </td>
              <td>{{ member.score == null ? 'Unscored' : member.score.toFixed(4) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </el-popover>
</template>
