<script setup lang="ts">
import { computed } from 'vue'
import { useConversationStore } from '@/stores/conversation'
import { NTooltip, NPopconfirm } from 'naive-ui'

interface Props {
  conversationId: string
  title: string
  isActive: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  select: [id: string]
  delete: [id: string]
}>()

const conversationStore = useConversationStore()

const formattedDate = computed(() => {
  const conv = conversationStore.conversations.find(c => c.id === props.conversationId)
  if (!conv) return ''
  const date = new Date(conv.createdAt)
  const now = new Date()
  const isToday = date.toDateString() === now.toDateString()
  if (isToday) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
})
</script>

<template>
  <div
    class="conversation-item"
    :class="{ 'conversation-item--active': isActive }"
    @click="emit('select', conversationId)"
  >
    <div class="conversation-item__content">
      <span class="conversation-item__title">{{ title }}</span>
      <span class="conversation-item__date">{{ formattedDate }}</span>
    </div>

    <n-tooltip trigger="hover" placement="left">
      <template #trigger>
        <button
          class="conversation-item__delete"
          @click.stop="emit('delete', conversationId)"
          aria-label="删除对话"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
            <path d="M10 11v6M14 11v6" />
            <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" />
          </svg>
        </button>
      </template>
      删除对话
    </n-tooltip>
  </div>
</template>

<style scoped lang="scss">
.conversation-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-3 $spacing-4;
  margin: $spacing-1 $spacing-2;
  border-radius: $radius-lg;
  cursor: pointer;
  transition: background-color $transition-fast;
  gap: $spacing-2;

  &:hover {
    background-color: $color-gray-100;

    .conversation-item__delete {
      opacity: 1;
    }
  }

  &--active {
    background-color: rgba($color-primary-500, 0.1);

    .conversation-item__title {
      color: $color-primary-600;
      font-weight: $font-weight-medium;
    }

    &:hover {
      background-color: rgba($color-primary-500, 0.15);
    }
  }

  &__content {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
    min-width: 0;
  }

  &__title {
    font-size: $font-size-sm;
    color: $color-text-primary;
    @include text-ellipsis;
    line-height: $line-height-normal;
  }

  &__date {
    font-size: $font-size-xs;
    color: $color-text-tertiary;
  }

  &__delete {
    opacity: 0;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border: none;
    background: transparent;
    border-radius: $radius-md;
    color: $color-text-tertiary;
    cursor: pointer;
    transition: color $transition-fast, background-color $transition-fast;

    &:hover {
      color: $color-error;
      background-color: rgba($color-error, 0.1);
    }
  }
}

// 暗色模式
:global(.dark) {
  .conversation-item {
    &:hover {
      background-color: $color-bg-dark-tertiary;
    }

    &--active {
      background-color: rgba($color-primary-400, 0.15);

      .conversation-item__title {
        color: $color-primary-400;
      }

      &:hover {
        background-color: rgba($color-primary-400, 0.2);
      }
    }

    &__title {
      color: $color-text-dark-primary;
    }

    &__date {
      color: $color-text-dark-tertiary;
    }

    &__delete {
      color: $color-text-dark-tertiary;

      &:hover {
        color: $color-error;
        background-color: rgba($color-error, 0.15);
      }
    }
  }
}
</style>
