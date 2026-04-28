<template>
  <header class="flex items-center justify-between gap-4 px-5 py-3 bg-[#f7f7f6] border-b border-[#ebebea] min-h-13 box-border">
    <!-- 左侧：Logo + 标题 -->
    <div class="flex items-center gap-2 min-w-0 cursor-pointer" @click="handleNav()">
      <div class="icon-cloud"></div>
      <h1 class="m-0 text-base font-bold text-[#1a1a1a] leading-[1.35] whitespace-nowrap overflow-hidden text-ellipsis">
        MVP Vue3 大模型单轮 AI 对话
      </h1>
    </div>

    <!-- 右侧：模型选择 + 帮助按钮 -->
    <div class="flex items-center gap-2 shrink-0">
      <span class="text-sm text-[#374151] whitespace-nowrap">当前模型：</span>

      <!-- 选择框包装器 -->
      <div class="select-wrapper relative flex items-center gap-1.5 px-2 py-[0.35rem] bg-white border border-[#e5e7eb] rounded-lg min-w-44">
        <div class="icon-model"></div>
        <select
          v-model="selectedModel"
          class=" flex-1 w-[200px] py-0.5 pr-5 border-none bg-transparent text-sm text-[#111827] cursor-pointer outline-none"
          aria-label="选择模型"
        >  
          
          <option
            v-for="opt in modelOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </select>

      </div>

      <!-- 帮助按钮 -->
      <button
        type="button"
        class=" w-6 h-6 p-0 rounded-full bg-[#8b5cf6] text-white cursor-pointer hover:bg-[#7c3aed] focus:outline-none focus:ring-2 focus:ring-[#a78bfa] focus:ring-offset-2"
        title="帮助"
        aria-label="帮助"
      >
        <span class="text-[0.8125rem] font-semibold leading-1">?</span>
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface ModelOption {
  value: string
  label: string
}

const modelOptions: ModelOption[] = [
  { value: 'mock', label: '模拟数据模型' },
  { value: 'deepseek', label: 'DeepSeek' },

]

const selectedModel = ref(modelOptions[0]!.value)

function handleNav() {
  console.log('跳转github')
}
</script>

<style scoped>
/* Tailwind 无法覆盖的样式 */
.select-wrapper select {
  appearance: none;
  -webkit-appearance: none;
}

</style>
