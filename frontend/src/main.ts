import { createPinia } from 'pinia'
import '@/style.css'
import '@/styles/markdown.css'

import App from './App.vue'
const app = createApp(App)
import { createDiscreteApi } from 'naive-ui'

const { message } = createDiscreteApi(['message'])
window.$message = message   // 挂载到全局
export const pinia = createPinia()
app.use(pinia)

app.mount('#app')
