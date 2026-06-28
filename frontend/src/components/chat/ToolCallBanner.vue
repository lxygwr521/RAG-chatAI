<script setup lang="ts">
import { computed } from 'vue'

interface ToolCallStep {
  tool_call_id: string
  tool_name: string
  arguments: Record<string, unknown>
  result?: string
  success?: boolean
}

const props = defineProps<{
  toolCalls: ToolCallStep[]
}>()

const visible = computed(() => props.toolCalls && props.toolCalls.length > 0)
</script>

<template>
  <div v-if="visible" class="tool-calls-banner">
    <div class="tool-calls-title">🔧 工具调用</div>
    <div
      v-for="tc in toolCalls"
      :key="tc.tool_call_id"
      class="tool-call-item"
    >
      <div class="tool-call-header">
        <span class="tool-call-name">{{ tc.tool_name }}</span>
        <span
          v-if="tc.result !== undefined"
          class="tool-call-status"
          :class="tc.success ? 'success' : 'fail'"
        >
          {{ tc.success ? '✓' : '✗' }}
        </span>
        <span v-else class="tool-call-status running">⏳</span>
      </div>
      <div class="tool-call-args">
        <code>{{ JSON.stringify(tc.arguments, null, 0).substring(0, 120) }}{{ JSON.stringify(tc.arguments).length > 120 ? '...' : '' }}</code>
      </div>
      <div v-if="tc.result" class="tool-call-result">
        {{ tc.result.substring(0, 200) }}{{ tc.result.length > 200 ? '...' : '' }}
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.tool-calls-banner {
  margin-top: $spacing-3;
  padding: $spacing-3;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: $radius-lg;
}

.tool-calls-title {
  font-size: $font-size-xs;
  font-weight: $font-weight-semibold;
  color: #0369a1;
  margin-bottom: $spacing-2;
}

.tool-call-item {
  padding: $spacing-2;
  background: white;
  border: 1px solid #e0f2fe;
  border-radius: $radius-md;
  margin-bottom: $spacing-2;

  &:last-child {
    margin-bottom: 0;
  }
}

.tool-call-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $spacing-1;
}

.tool-call-name {
  font-size: $font-size-xs;
  font-weight: $font-weight-semibold;
  color: #0c4a6e;
  font-family: $font-family-mono;
}

.tool-call-status {
  font-size: $font-size-xs;

  &.success { color: $color-success; }
  &.fail { color: $color-error; }
  &.running { color: $color-warning; }
}

.tool-call-args {
  font-size: 0.7rem;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.tool-call-result {
  margin-top: $spacing-1;
  font-size: $font-size-xs;
  color: #334155;
  padding: $spacing-1 $spacing-2;
  background: #f8fafc;
  border-radius: $radius-sm;
  max-height: 4rem;
  overflow-y: auto;
}
</style>
