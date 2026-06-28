<script setup lang="ts">
defineProps<{
  questions: string[]
}>()

const emit = defineEmits<{
  select: [question: string]
}>()
</script>

<template>
  <div class="quick-questions">
    <div class="quick-questions__label">试试这样问：</div>
    <div class="quick-questions__list">
      <button
        v-for="q in questions"
        :key="q"
        type="button"
        class="quick-btn"
        @click="emit('select', q)"
      >
        {{ q }}
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">

.quick-questions {
  padding: $spacing-2 $spacing-5 $spacing-4;
}

.quick-questions__label {
  margin-bottom: $spacing-3;
  font-size: $font-size-sm;
  color: $color-gray-500;
}

.quick-questions__list {
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-2;
}

.quick-btn {
  padding: $spacing-2 $spacing-3;
  border: 1px solid $color-gray-200;
  border-radius: $radius-full;
  background: $color-bg-primary;
  font-size: $font-size-sm;
  color: $color-gray-600;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    border-color: $color-primary-500;
    color: $color-primary-500;
    background: $color-primary-50;
  }

  &:focus-visible {
    outline: 2px solid $color-primary-500;
    outline-offset: 2px;
  }
}
</style>
