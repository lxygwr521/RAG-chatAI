<script setup lang="ts">
import { useConversationStore } from '@/stores/conversation'
import { useMessageStore } from '@/stores/conversation'
import ConversationItem from './ConversationItem.vue'
import { NTooltip, NPopconfirm } from 'naive-ui'

const emit = defineEmits<{
  newChat: []
  deleteChat: [id: string]
  selectChat: [id: string]
}>()

const conversationStore = useConversationStore()
const messageStore = useMessageStore()

function handleNewChat() {
  const conv = conversationStore.createConversation()
  emit('newChat')
  emit('selectChat', conv.id)
}

function handleSelect(id: string) {
  conversationStore.switchConversation(id)
  emit('selectChat', id)
}

function handleDelete(id: string) {
  conversationStore.deleteConversation(id)
  messageStore.deleteConversationMessages(id)
  emit('deleteChat', id)
}

function handleClearAll() {
  conversationStore.clearAllConversations()
  messageStore.clearAllMessages()
}
</script>

<template>
  <aside class="sidebar">
    <!-- 顶部区域：Logo + 模型选择 -->
    <header class="sidebar__header " >
      <div class="flex justify-between">
        <div class="sidebar__brand">
        <div class="icon-cloud"></div>
        <span class="sidebar__brand-text">AI 对话</span>
      </div>
      <n-tooltip trigger="hover" placement="bottom">
        <template #trigger>
          <button
            type="button"
            class=" w-6 h-6 p-0 rounded-full bg-[#8b5cf6] text-white cursor-pointer hover:bg-[#7c3aed] focus:outline-none focus:ring-2 focus:ring-[#a78bfa] focus:ring-offset-2"
            aria-label="帮助"
          >
            <span class="text-[0.8125rem] font-semibold leading-1">?</span>
          </button>
        </template>
        如需测试其他模型，需要本地配置 apiKey
      </n-tooltip>
      </div>
    

      <div class="sidebar__model-select">
        <div class="icon-model"></div>
        <select
          v-model="conversationStore.selectedModel"
          class="sidebar__model-select-input"
          aria-label="选择模型"
        >
          <option value="mock">模拟数据模型</option>
          <option value="deepseek">DeepSeek</option>
        </select>
      </div>
    </header>

    <!-- 新建对话按钮 -->
    <div class="sidebar__new-chat">
      <button class="sidebar__new-chat-btn" @click="handleNewChat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        新建对话
      </button>
    </div>

    <!-- 会话列表 -->
    <div class="sidebar__list">
      <template v-if="conversationStore.conversations.length > 0">
        <ConversationItem
          v-for="conv in conversationStore.conversations"
          :key="conv.id"
          :conversation-id="conv.id"
          :title="conv.title"
          :is-active="conv.id === conversationStore.currentConversationId"
          @select="handleSelect"
          @delete="handleDelete"
        />
      </template>
      <div v-else class="sidebar__empty">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <span>暂无对话记录</span>
      </div>
    </div>

    <!-- 底部：清除全部 -->
    <footer class="sidebar__footer">
      <n-popconfirm
        v-if="conversationStore.conversations.length > 0"
        @positive-click="handleClearAll"
        positive-text="确认" negative-text="取消"
      >
        <template #trigger>
          <button class="sidebar__clear-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
            </svg>
            清除全部
          </button>
        </template>
        确定要清除所有对话记录吗？此操作不可撤销。
      </n-popconfirm>
    </footer>
  </aside>
</template>

<style scoped lang="scss">
.sidebar {
  display: flex;
  flex-direction: column;
  width: 30%;
  min-width: 240px;
  max-width: 360px;
  height: 100vh;
  background-color: $color-bg-secondary;
  border-right: 1px solid $color-border-light;

  &__header {
    display: flex;
    flex-direction: column;
    gap: $spacing-3;
    padding: $spacing-4 $spacing-4 $spacing-3;
    border-bottom: 1px solid $color-border-light;
  }

  &__brand {
    display: flex;
    align-items: center;
    gap: $spacing-2;
  }

  &__brand-text {
    font-size: $font-size-base;
    font-weight: $font-weight-semibold;
    color: $color-text-primary;
  }

  &__model-select {
    display: flex;
    align-items: center;
    gap: $spacing-2;
    padding: $spacing-2 $spacing-3;
    background-color: $color-bg-primary;
    border: 1px solid $color-border-light;
    border-radius: $radius-lg;
    cursor: pointer;
  }

  &__model-select-input {
    flex: 1;
    border: none;
    background: transparent;
    font-size: $font-size-sm;
    color: $color-text-primary;
    cursor: pointer;
    outline: none;

    appearance: none;
    -webkit-appearance: none;
  }

  &__new-chat {
    padding: $spacing-3 $spacing-3;
  }

  &__new-chat-btn {
    @include button-primary;
    width: 100%;
    justify-content: center;
    gap: $spacing-2;
    font-size: $font-size-sm;
    padding: $spacing-2 $spacing-4;
  }

  &__list {
    flex: 1;
    overflow-y: auto;
    padding-bottom: $spacing-2;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background-color: $color-gray-300;
      border-radius: $radius-full;
    }
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: $spacing-3;
    padding: $spacing-10 $spacing-4;
    color: $color-text-muted;
    font-size: $font-size-sm;
    text-align: center;
  }

  &__footer {
    padding: $spacing-3 $spacing-3;
    border-top: 1px solid $color-border-light;
  }

  &__clear-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: $spacing-2;
    width: 100%;
    padding: $spacing-2 $spacing-3;
    border: none;
    background: transparent;
    border-radius: $radius-lg;
    font-size: $font-size-sm;
    color: $color-text-tertiary;
    cursor: pointer;
    transition: color $transition-fast, background-color $transition-fast;

    &:hover {
      color: $color-error;
      background-color: rgba($color-error, 0.08);
    }
  }
}

// 暗色模式
:global(.dark) {
  .sidebar {
    background-color: $color-bg-dark;
    border-right-color: $color-border-dark;

    &__header {
      border-bottom-color: $color-border-dark;
    }

    &__brand-text {
      color: $color-text-dark-primary;
    }

    &__model-select {
      background-color: $color-bg-dark-secondary;
      border-color: $color-border-dark;
    }

    &__model-select-input {
      color: $color-text-dark-primary;
    }

    &__new-chat-btn {
      background-color: $color-primary-600;

      &:hover:not(:disabled) {
        background-color: $color-primary-500;
      }
    }

    &__list {
      &::-webkit-scrollbar-thumb {
        background-color: $color-border-dark;
      }
    }

    &__empty {
      color: $color-text-dark-tertiary;
    }

    &__footer {
      border-top-color: $color-border-dark;
    }

    &__clear-btn {
      color: $color-text-dark-tertiary;

      &:hover {
        color: $color-error;
        background-color: rgba($color-error, 0.15);
      }
    }
  }
}
</style>
