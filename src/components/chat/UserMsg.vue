<script setup lang="ts">
import type {UserMessageProps} from './types'

defineProps<{
  message: UserMessageProps
}>()

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getBadgeColor(type: string): string {
  const map: Record<string, string> = {
    'image/jpeg': '#8b5cf6',
    'image/png': '#8b5cf6',
    'application/pdf': '#ef4444',
    'text/plain': '#6b7280',
  }
  return map[type] ?? '#3b82f6'
}
</script>

<template>
  <div class="user-msg-item">
    <div class="user-msg-avatar">
      <div class="avatar-icon avatar-icon--user">👤</div>
    </div>
    <div class="user-msg-content">
      <!-- File attachments -->
      <div v-if="message.files && message.files.length > 0" class="user-msg-files">
        <FileItem v-for="file in message.files" :key="file.id" :item="file" :disable-delete="true" />
      </div>

      <!-- Text content -->
      <div v-if="message.content" class="user-msg-bubble">
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

.user-msg-files {
  display: flex;
  flex-direction: column;
  gap: $spacing-1;
  align-items: flex-end;
  margin-bottom: $spacing-2;
}

.user-msg-file {
  display: flex;
  align-items: center;
  gap: $spacing-2;
  padding: $spacing-2 $spacing-3;
  background: $color-gray-50;
  border: 1px solid $color-gray-200;
  border-radius: $radius-lg;
  max-width: 18rem;
  overflow: hidden;
}

.user-msg-file__image {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: $radius-md;
  object-fit: cover;
  flex-shrink: 0;
}

.user-msg-file__badge {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  span {
    font-size: 0.5rem;
    font-weight: $font-weight-bold;
    color: white;
  }
}

.user-msg-file__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.user-msg-file__name {
  font-size: $font-size-xs;
  color: $color-gray-700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.user-msg-file__size {
  font-size: $font-size-xs;
  color: $color-gray-400;
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
