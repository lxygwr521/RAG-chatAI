<script setup lang="ts">
import { ref, nextTick, computed } from 'vue'
import FileUpload from './FileUpload.vue'
import FileItem from './FileItem.vue'
import { UploadFile } from './types';
const props = defineProps<{
  isGenerating?: boolean
}>()

const emit = defineEmits<{
  submit: [value: string, files: UploadFile[]]
  stop: []
}>()

const inputValue = ref('')
const fileUploadRef = ref<InstanceType<typeof FileUpload> | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const uploadedFiles = computed(() => fileUploadRef.value?.files ?? [])

function autoResize() {
  nextTick(() => {
    const el = textareaRef.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  })
}

async function handleSubmit() {
  const value = inputValue.value.trim()
  if (!value && uploadedFiles.value.length === 0) return
  emit('submit', value, uploadedFiles.value)
  inputValue.value = ''
  fileUploadRef.value?.clearFiles()
  textareaRef.value!.style.height = 'auto'
}

function handleStop() {
  emit('stop')
}

function handleRemoveFile(id: string) {
  fileUploadRef.value?.removeFile(id)
}
</script>

<template>
    <div class="input-wrapper">
      <!-- File list -->
      <Transition name="slide">
        <div v-if="uploadedFiles.length > 0" class="input-wrapper__files">
          <FileItem
            v-for="item in uploadedFiles"
            :key="item.id"
            :item="item"
            @remove="handleRemoveFile"
          />
        </div>
      </Transition>
        <textarea
          ref="textareaRef"
          v-model="inputValue"
          class="input-field"
          :placeholder="isGenerating ? '正在生成回答...' : '输入你的问题...'"
          :disabled="isGenerating"
          @input="autoResize"
          @keydown.enter.exact.prevent="handleSubmit"
        />

        <div class="input-wrapper__actions">
          <FileUpload
            v-if="!isGenerating"
            ref="fileUploadRef"
            class="chat-input__upload"
          />
          <button
            v-if="!isGenerating"
            type="button"
            class="submit-btn"
            :disabled="!inputValue.trim() && uploadedFiles.length === 0"
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
.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: $spacing-2;
  padding: $spacing-3 $spacing-4;
  background: $color-gray-50;
  border: 1px solid $color-gray-200;
  border-radius: $radius-xl;
}

.input-wrapper__files {
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-1;
}


.input-wrapper__actions {
  display: flex;
  justify-content: flex-end;
  gap: $spacing-2;
}

.input-field {
  width: 100%;
  max-height: 16rem; /* ~10 lines */
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

/* Slide transition */
.slide-enter-active,
.slide-leave-active {
  transition: opacity $transition-normal, transform $transition-normal;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY($spacing-2);
}
</style>
