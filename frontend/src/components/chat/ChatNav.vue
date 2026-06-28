<template>
  <div class="chat-nav" :class="{ collapsed: !isExpanded }">
    <button
      class="nav-toggle"
      :title="isExpanded ? '收起导航' : '展开导航'"
      @click="isExpanded = !isExpanded"
    >
      <svg
        v-if="isExpanded"
        xmlns="http://www.w3.org/2000/svg"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <polyline points="9 18 15 12 9 6" />
      </svg>
      <svg
        v-else
        xmlns="http://www.w3.org/2000/svg"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <polyline points="15 18 9 12 15 6" />
      </svg>
    </button>

    <div v-show="isExpanded" class="nav-body">
      <div class="nav-header">对话记录</div>
      <div class="nav-list" ref="navListRef">
        <div
          v-for="(item, index) in navItems"
          :key="item.timestamp"
          class="nav-item"
          :class="{ active: index === navActiveIndex }"
          @click="emit('scrollTo', item.timestamp)"
        >
          <span class="nav-preview">{{ item.preview }}</span>
        </div>
        <div v-if="navItems.length === 0" class="nav-empty">
          暂无对话记录
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Message } from './types'

const props = defineProps<{
  messages: Message[]
  activeIndex: number
}>()

const emit = defineEmits<{
  scrollTo: [timestamp: number]
}>()

const isExpanded = ref(true)
const navListRef = ref<HTMLElement | null>(null)

interface NavItem {
  timestamp: number
  role: 'user' | 'assistant'
  preview: string
}

const navItems = computed<NavItem[]>(() => {
  return props.messages
    .filter(msg => msg.role === 'user')
    .map(msg => {
      let preview = msg.content.replace(/\n/g, ' ').substring(0, 25)
      if (msg.content.length > 25) preview += '...'
      return {
        timestamp: msg.timestamp,
        role: msg.role,
        preview
      }
    })
})

// 将父组件的 activeIndex（全量消息索引）映射到仅含 user 消息的导航索引
const navActiveIndex = computed(() => {
  if (props.activeIndex < 0 || props.activeIndex >= props.messages.length) return -1
  // 从 activeIndex 向前查找最近的 user 消息
  for (let i = props.activeIndex; i >= 0; i--) {
    const msg = props.messages[i]
    if (msg?.role === 'user') {
      return navItems.value.findIndex(item => item.timestamp === msg.timestamp)
    }
  }
  return -1
})
</script>

<style scoped lang="scss">
.chat-nav {
  position: relative;
  display: flex;
  flex-direction: column;
  border-left: 1px solid #e5e7eb;
  background: #fafafa;
  transition: width 0.25s ease;
  width: 220px;
  flex-shrink: 0;

  &.collapsed {
    width: 36px;
  }
}

.nav-toggle {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  left: -14px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  z-index: 2;
  transition: color 0.2s;

  &:hover {
    color: #1f2937;
    border-color: #9ca3af;
  }
}

.nav-body {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.nav-header {
  padding: 12px 16px 8px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  flex-shrink: 0;
  border-bottom: 1px solid #e5e7eb;
}

.nav-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  cursor: pointer;
  transition: background 0.15s;
  border-left: 3px solid transparent;

  &:hover {
    background: #f3f4f6;
  }

  &.active {
    background: #eff6ff;
    border-left-color: #3b82f6;
  }
}

.nav-preview {
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

.nav-empty {
  padding: 24px 16px;
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
}

:global(.dark) {
  .chat-nav {
    border-left-color: #374151;
    background: #111827;
  }

  .nav-toggle {
    background: #1f2937;
    border-color: #4b5563;
    color: #9ca3af;

    &:hover {
      color: #e5e7eb;
      border-color: #6b7280;
    }
  }

  .nav-header {
    color: #9ca3af;
    border-bottom-color: #374151;
  }

  .nav-item {
    &:hover {
      background: #1f2937;
    }

    &.active {
      background: #1e3a5f;
      border-left-color: #60a5fa;
    }
  }

  .nav-preview {
    color: #9ca3af;
  }
}
</style>
