<script setup>
import en from 'element-plus/es/locale/lang/en'

import AnalysisWorkbench from './views/AnalysisWorkbench.vue'
</script>

<template>
  <el-config-provider :locale="en" size="small">
    <AnalysisWorkbench />
  </el-config-provider>
</template>
