import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import '@/style.css'
import '@/styles/markdown.css'

import App from './App.vue'
const app = createApp(App)
import { createDiscreteApi } from 'naive-ui'

const { message } = createDiscreteApi(['message'])
window.$message = message   // 挂载到全局
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)
app.use(pinia)

app.mount('#app')
