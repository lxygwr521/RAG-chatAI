<script setup lang="ts">
import { type UploadFile } from './types'

const props = defineProps<{
  item: UploadFile
  disableDelete?:Boolean
}>()

const emit = defineEmits<{
  remove: [id: string]
}>()

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getBadgeColor(): string {
  return '#6b7280'
}
</script>

<template>
  <div class="file-item" >
    <!-- TODO Image preview for completed image files -->
    <div v-if= "item.file.type.startsWith('image/') && item.url" class="file-item__preview">
      <img :src="item.url" :alt="item.file.name" />
    </div>

    <!-- Type badge for non-image or uploading/error files -->
    <div
      class="file-item__badge"
      :style="{ backgroundColor: getBadgeColor() }"
    >
      <span>{{ item.file.name.split('.').pop()?.toUpperCase() }}</span>
    </div>

    <!-- File info -->
    <div class="file-item__info">
      <div class="file-item__name">{{ item.file.name }}</div>


      <!-- Done: show file size -->
      <div  class="file-item__size">
        {{ formatSize(item.file.size) }}
      </div>
    </div>

    <!-- Delete button -->
    <button v-if="!disableDelete"
      type="button"
      class="file-item__delete"
      @click="emit('remove', item.id)"
    >
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M10.5 3.5V10.5M3.5 3.5V10.5M1.5 3.5H12.5M5.5 3.5V2.5C5.5 2 6 1.5 6.5 1.5H7.5C8 1.5 8.5 2 8.5 2.5V3.5M5.5 6.5V9.5M8.5 6.5V9.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
  </div>
</template>

<style scoped lang="scss">
.file-item {
  display: flex;
  align-items: center;
  gap: $spacing-2;
  padding: $spacing-2 $spacing-3;
  background: $color-gray-50;
  border: 1px solid $color-gray-200;
  border-radius: $radius-lg;
  transition: border-color $transition-fast, background-color $transition-fast;

  &--error {
    border-color: $color-error-light;
    background: rgba($color-error, 0.04);
  }

  &--done {
    border-color: $color-success-light;
  }
}

.file-item__preview {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: $radius-md;
  overflow: hidden;
  flex-shrink: 0;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.file-item__badge {
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
    letter-spacing: 0.02em;
  }
}

.file-item__info {
  flex: 1;
  min-width: 0;
}

.file-item__name {
  font-size: $font-size-xs;
  color: $color-gray-700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.file-item__progress-bar {
  height: 3px;
  background: $color-gray-200;
  border-radius: $radius-full;
  margin-top: $spacing-1;
  overflow: hidden;

  .file-item__progress-fill {
    height: 100%;
    background: $color-primary-500;
    border-radius: $radius-full;
    transition: width 200ms ease-out;
  }
}

.file-item__error {
  font-size: $font-size-xs;
  color: $color-error;
  margin-top: 2px;
}

.file-item__size {
  font-size: $font-size-xs;
  color: $color-gray-400;
  margin-top: 2px;
}

.file-item__delete {
  flex-shrink: 0;
  width: 1.5rem;
  height: 1.5rem;
  border: none;
  background: transparent;
  color: $color-gray-400;
  border-radius: $radius-md;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color $transition-fast, background-color $transition-fast;

  &:hover {
    color: $color-error;
    background: rgba($color-error, 0.08);
  }
}
</style>
