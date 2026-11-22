<script setup>
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import AnalysisWorkbench from './views/AnalysisWorkbench.vue'
</script>

<template>
  <el-config-provider :locale="zhCn" size="small">
    <AnalysisWorkbench />
  </el-config-provider>
</template>
