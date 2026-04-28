<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  isGenerating?: boolean
}>()

const emit = defineEmits<{
  submit: [value: string]
  stop: []
}>()

const inputValue = ref('')

function handleSubmit() {
  const value = inputValue.value.trim()
  if (!value) return
  emit('submit', value)
  inputValue.value = ''
}

function handleStop() {
  emit('stop')
}
</script>

<template>
  <div class="chat-input">
    <div class="input-wrapper">
      <textarea
        v-model="inputValue"
        class="input-field"
        :placeholder="isGenerating ? '正在生成回答...' : '输入你的问题...'"
        :disabled="isGenerating"
        rows="1"
        @keydown.enter.exact.prevent="handleSubmit"
      />
      <button
        v-if="!isGenerating"
        type="button"
        class="submit-btn"
        :disabled="!inputValue.trim()"
        @click="handleSubmit"
      >
        发送
      </button>
      <button
        v-else
        type="button"
        class="stop-btn"
        @click="handleStop"
      >
        停止
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">

.chat-input {
  padding: $spacing-3 $spacing-5;
  border-top: 1px solid $color-gray-200;
  background: $color-bg-primary;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: $spacing-3;
  padding: $spacing-3 $spacing-4;
  background: $color-gray-50;
  border: 1px solid $color-gray-200;
  border-radius: $radius-xl;
}

.input-field {
  flex: 1;
  min-height: 1.5rem;
  padding: 0;
  background: transparent;
  font-size: $font-size-sm;
  color: $color-gray-800;
  line-height: $font-height-relaxed;
  resize: none;
  border: none;
  outline: none;

  &::placeholder {
    color: $color-gray-400;
  }
}

.submit-btn {
  flex-shrink: 0;
  padding: $spacing-2 $spacing-4;
  background: $color-primary-500;
  color: white;
  font-size: $font-size-sm;
  font-weight: $font-weight-medium;
  border: none;
  border-radius: $radius-lg;
  cursor: pointer;
  transition: background-color $transition-fast;

  &:hover:not(:disabled) {
    background: $color-primary-600;
  }

  &:disabled {
    background: $color-gray-300;
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: 2px solid $color-primary-400;
    outline-offset: 2px;
  }
}

.stop-btn {
  flex-shrink: 0;
  padding: $spacing-2 $spacing-4;
  background: $color-error;
  color: white;
  font-size: $font-size-sm;
  font-weight: $font-weight-medium;
  border: none;
  border-radius: $radius-lg;
  cursor: pointer;
  transition: background-color $transition-fast;

  &:hover {
    background: color.adjust($color-error, $lightness: -10%);
  }

  &:focus-visible {
    outline: 2px solid $color-error-light;
    outline-offset: 2px;
  }
}
</style>