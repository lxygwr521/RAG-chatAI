<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AssistantMessageProps } from './types'
import { renderMarkdownText } from '@/utils/markdown'
import ToolCallBanner from './ToolCallBanner.vue'

const props = defineProps<{
  message: AssistantMessageProps
}>()

// Tool calls stored as an internal property during Agent execution
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const toolCalls = computed(() => {
  const msg = props.message as any
  return msg._toolCalls ?? []
})

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
      <!-- Tool Calls (Agent intermediate steps) -->
      <ToolCallBanner :tool-calls="toolCalls" />

      <!-- RAG Citations -->
      <div v-if="message.citations && message.citations.length > 0" class="assistant-msg-citations">
        <div class="citations-title">📚 引用来源</div>
        <div
          v-for="(cite, idx) in message.citations"
          :key="cite.chunk_id"
          class="citation-item"
        >
          <span class="citation-index">[{{ idx + 1 }}]</span>
          <span class="citation-doc">{{ cite.document }}</span>
          <span class="citation-snippet">"{{ cite.snippet }}"</span>
        </div>
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

.assistant-msg-citations {
  margin-top: $spacing-3;
  padding: $spacing-3;
  background: $color-gray-50;
  border: 1px solid $color-gray-200;
  border-radius: $radius-lg;
}

.citations-title {
  font-size: $font-size-xs;
  font-weight: $font-weight-semibold;
  color: $color-gray-600;
  margin-bottom: $spacing-2;
}

.citation-item {
  display: flex;
  gap: $spacing-2;
  font-size: $font-size-xs;
  color: $color-gray-500;
  margin-bottom: $spacing-1;

  &:last-child {
    margin-bottom: 0;
  }
}

.citation-index {
  font-weight: $font-weight-semibold;
  color: $color-primary-500;
  flex-shrink: 0;
}

.citation-doc {
  font-weight: $font-weight-medium;
  color: $color-gray-700;
  flex-shrink: 0;
}

.citation-snippet {
  color: $color-gray-500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

</style>
