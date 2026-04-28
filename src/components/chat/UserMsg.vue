<script setup lang="ts">
import type { UserMessageProps } from './types'

defineProps<{
  message: UserMessageProps
}>()
</script>

<template>
  <div class="user-msg-item">
    <div class="user-msg-avatar">
      <div class="avatar-icon avatar-icon--user">👤</div>
    </div>
    <div class="user-msg-content">
      <div class="user-msg-bubble">
        {{ message.content }}
      </div>
      <div class="user-msg-time">
        {{ new Date(message.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.user-msg-item {
  display: flex;
  flex-direction: row-reverse;
  gap: $spacing-3;
  padding: $spacing-4 $spacing-5;
  max-width: 100%;
}

.user-msg-avatar {
  flex-shrink: 0;
}

.avatar-icon {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: $radius-full;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: $font-size-lg;

  &--user {
    background: $color-gray-100;
  }
}

.user-msg-content {
  max-width: 70%;
  text-align: right;
}

.user-msg-bubble {
  display: inline-block;
  padding: $spacing-3 $spacing-4;
  border-radius: $radius-xl;
  font-size: $font-size-sm;
  line-height: $font-height-relaxed;
  word-break: break-all;
  background: $color-primary-500;
  color: white;
  border-bottom-right-radius: $radius-sm;
}

.user-msg-time {
  margin-top: $spacing-1;
  font-size: $font-size-xs;
  color: $color-gray-400;
}
</style>
