<script setup lang="ts">
defineProps<{
  message?: string
}>()
</script>

<template>
  <div class="no-data">
    <div class="no-data__icon">
      <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="32" cy="32" r="30" stroke="currentColor" stroke-width="2" stroke-dasharray="4 4" opacity="0.3"/>
        <path d="M20 28C20 26.8954 20.8954 26 22 26H42C43.1046 26 44 26.8954 44 28V30C44 31.1046 43.1046 32 42 32H22C20.8954 32 20 31.1046 20 30V28Z" fill="currentColor" opacity="0.5"/>
        <path d="M24 38H40M24 42H36" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.3"/>
      </svg>
    </div>
    <p class="no-data__text">{{ message || '开始对话吧' }}</p>
  </div>
</template>

<style scoped lang="scss">

.no-data {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: $spacing-8;
}

.no-data__icon {
  color: $color-gray-400;
  margin-bottom: $spacing-4;
}

.no-data__text {
  font-size: $font-size-base;
  color: $color-gray-400;
}

// 暗色模式支持
:global(.dark) {
  .no-data__icon {
    color: $color-gray-600;
  }

  .no-data__text {
    color: $color-gray-500;
  }
}
</style>
