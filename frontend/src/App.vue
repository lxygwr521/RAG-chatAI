<script setup lang="ts">
import ConversationSidebar from '@/components/layout/ConversationSidebar.vue'
import Chat from './pages/chat.vue'
import { useCopyCode } from '@/hooks/useCopyCode'

defineOptions({
  name: 'App'
})

useCopyCode()
</script>

<template>
  <div class="app-layout flex h-screen overflow-hidden">
    <ConversationSidebar />
    <Chat class="flex-1 min-w-0" />
  </div>
</template>

<style scoped>
</style>
