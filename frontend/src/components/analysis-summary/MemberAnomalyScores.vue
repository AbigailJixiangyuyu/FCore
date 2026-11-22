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
      <el-button link type="primary">成员异常分数</el-button>
    </template>
    <template #default="{ hide }">
      <div class="member-table" role="region" aria-label="社区成员异常分数" tabindex="0">
        <table>
          <thead>
            <tr>
              <th scope="col">节点 ID</th>
              <th scope="col" title="SLADE 综合异常分，范围 0–1">SLADE 异常分</th>
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
                  :aria-label="`在图中定位节点 ${member.account_id}`"
                  :title="`在图中定位节点 ${member.account_id}`"
                >{{ member.account_id }}</button>
              </td>
              <td>{{ member.score == null ? '未评分' : member.score.toFixed(4) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </el-popover>
</template>
