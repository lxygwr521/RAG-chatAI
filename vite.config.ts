import { fileURLToPath, URL } from 'node:url'
import raw from 'vite-raw-plugin'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'
import AutoImport from 'unplugin-auto-import/vite'

// https://vite.dev/config/
export default defineConfig({
  server: {
    port: 3000,
  },
  plugins: [
    raw({
      fileRegex: /\.md$/
    }),
    vue(),
  
    vueDevTools(),
    tailwindcss(),
    AutoImport({
      imports: ['vue', 'pinia'],
      dts: 'src/auto-import.d.ts',
      eslintrc: { enabled: true },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "sass:color";
@use "@/styles/_variables.scss" as *;
`,
        silenceDeprecations: ['import'],
      }
    }
  },
})
