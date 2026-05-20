<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AssistantMessageProps } from './types'
import { renderMarkdownText } from '@/utils/markdown'

const props = defineProps<{
  message: AssistantMessageProps
}>()

defineEmits<{
  stop: [value: boolean]
}>()

const rawContent = computed(() => props.message.content)
const displayedContent = ref('')

let rafId: number | null = null
watch(rawContent, (val) => {
  if (rafId !== null) return
  rafId = requestAnimationFrame(() => {
    displayedContent.value = renderMarkdownText(val)
    rafId = null
  })
}, { immediate: true })
</script>

<template>
  <div class="assistant-msg-item">
    <div class="assistant-msg-avatar">
      <div class="avatar-icon avatar-icon--assistant">🤖</div>
    </div>
    <div class="assistant-msg-content">
      <div class="markdown-wrapper" v-html="displayedContent">

      </div>
      <div class="assistant-msg-time">
        {{ new Date(message.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.assistant-msg-item {
  display: flex;
  flex-direction: row;
  gap: $spacing-3;
  padding: $spacing-4 $spacing-5;
  max-width: 100%;
}

.assistant-msg-avatar {
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

  &--assistant {
    background: $color-primary-100;
  }
}

.assistant-msg-content {
  max-width: 100%;

}


.assistant-msg-time {
  margin-top: $spacing-1;
  font-size: $font-size-xs;
  color: $color-gray-400;
}

</style>
