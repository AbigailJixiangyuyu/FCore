import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import elementPlus from './plugins/elementPlus.js'
import './styles/element-plus.css'
import './styles/main.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    },
    mutations: { retry: false },
  },
})

createApp(App)
  .use(createPinia())
  .use(VueQueryPlugin, { queryClient })
  .use(elementPlus)
  .mount('#app')
